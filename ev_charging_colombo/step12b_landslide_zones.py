"""
STEP 12b — Landslide hazard zones (multi-hazard extension to the grid veto).

Builds a landslide susceptibility layer from the BEST available source:

  1. data/landslide_hazard_zones_real.geojson   — digitized NBRO zonation polygons
     (must contain a 'susceptibility' column: High / Moderate / Low)
  2. data/landslide_inventory_real.csv          — historic event points
     (NASA Global Landslide Catalog / DesInventar; lon/lat columns auto-detected,
      buffered by LANDSLIDE_BUFFER_M)
  3. AUTO — terrain slope proxy from the Copernicus GLO-30 DEM (no API key):
     slope >= SLOPE_HIGH_DEG -> High, SLOPE_MODERATE_DEG..HIGH -> Moderate

Saves: data/landslide_hazard_zones.geojson   (polygons, 'susceptibility' column)
       data/landslide_slope_degrees.tif      (slope raster — source 3 only, single-tile areas)

NOTE: For flat coastal Colombo the DEM proxy typically finds NO susceptible
cells — the veto layer is then inactive and Step 13 treats it as 1.0
everywhere. That is a valid, reportable result.

Run:  python step12b_landslide_zones.py [--force]
"""

import argparse
import math

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape

from config import (TARGET_CRS, LANDSLIDE_FEASIBILITY, LANDSLIDE_BUFFER_M,
                    SLOPE_HIGH_DEG, SLOPE_MODERATE_DEG,
                    F_LANDSLIDE_REAL, F_LANDSLIDE_INVENTORY,
                    F_LANDSLIDE_ZONES, F_SLOPE_RASTER, load_study_polygon)


# ----------------------------------------------------------------------
# Source 1 — digitized zonation polygons (e.g. NBRO maps traced in QGIS)
# ----------------------------------------------------------------------
def load_real_zones() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(F_LANDSLIDE_REAL).to_crs(TARGET_CRS)
    if "susceptibility" not in gdf.columns:
        raise ValueError(f"{F_LANDSLIDE_REAL.name} must contain a "
                         f"'susceptibility' column with values "
                         f"{list(LANDSLIDE_FEASIBILITY)}.")
    gdf["susceptibility"] = gdf["susceptibility"].astype(str).str.strip().str.capitalize()
    bad = ~gdf["susceptibility"].isin(LANDSLIDE_FEASIBILITY)
    if bad.any():
        raise ValueError("Unknown susceptibility values: "
                         f"{sorted(gdf.loc[bad, 'susceptibility'].unique())}")
    print(f"[info] Using digitized zonation polygons ({len(gdf)} features).")
    return gdf[["susceptibility", "geometry"]]


# ----------------------------------------------------------------------
# Source 2 — historic event points (NASA GLC / DesInventar CSV)
# ----------------------------------------------------------------------
def load_inventory_zones(study_poly) -> gpd.GeoDataFrame:
    df = pd.read_csv(F_LANDSLIDE_INVENTORY)
    cols = {c.lower(): c for c in df.columns}

    lon_col = next((cols[c] for c in ("longitude", "lon", "lng", "x") if c in cols), None)
    lat_col = next((cols[c] for c in ("latitude", "lat", "y") if c in cols), None)
    if lon_col is None or lat_col is None:
        raise ValueError("Inventory CSV must have longitude/latitude columns "
                         "(any common naming: lon/lng/x, lat/y).")

    df = df[pd.to_numeric(df[lon_col], errors="coerce").notna()
            & pd.to_numeric(df[lat_col], errors="coerce").notna()]

    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
                           crs="EPSG:4326").to_crs(TARGET_CRS)

    if "susceptibility" in cols:
        vals = pts[cols["susceptibility"]].astype(str).str.strip().str.capitalize()
    else:
        vals = pd.Series("Moderate", index=pts.index)   # unknown severity -> penalty, not veto

    gdf = gpd.GeoDataFrame({"susceptibility": vals},
                           geometry=pts.buffer(LANDSLIDE_BUFFER_M), crs=TARGET_CRS)
    gdf = gdf[gdf.intersects(study_poly)]
    print(f"[info] Buffered {len(pts)} historic event points by {LANDSLIDE_BUFFER_M} m.")
    return gdf[["susceptibility", "geometry"]]


# ----------------------------------------------------------------------
# Source 3 — automatic DEM slope proxy (Copernicus GLO-30, AWS open data)
# ----------------------------------------------------------------------
def copernicus_tile_urls(minx, miny, maxx, maxy):
    urls = []
    for lat in range(math.floor(miny), math.floor(maxy) + 1):
        for lon in range(math.floor(minx), math.floor(maxx) + 1):
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            tag = (f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_"
                   f"{ew}{abs(lon):03d}_00_DEM")
            urls.append(f"https://copernicus-dem-30m.s3.amazonaws.com/{tag}/{tag}.tif")
    return urls


def slope_proxy_zones(study_poly_utm):
    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.features import shapes as rio_shapes

    minx, miny, maxx, maxy = gpd.GeoSeries([study_poly_utm], crs=TARGET_CRS) \
        .to_crs("EPSG:4326").total_bounds
    urls = copernicus_tile_urls(minx, miny, maxx, maxy)
    print(f"[info] Downloading Copernicus GLO-30 DEM tile(s): {len(urls)}")

    zone_gdfs, slope_saved = [], False

    for url in urls:
        try:
            with rasterio.open(url) as src:
                tb = src.bounds
                wx0, wy0 = max(minx, tb.left), max(miny, tb.bottom)
                wx1, wy1 = min(maxx, tb.right), min(maxy, tb.top)
                if wx0 >= wx1 or wy0 >= wy1:
                    continue
                win = from_bounds(wx0, wy0, wx1, wy1, transform=src.transform)
                arr = src.read(1, window=win, masked=True)
                tr = src.window_transform(win)
                tile_crs = src.crs
        except Exception as e:
            raise RuntimeError(f"Could not read DEM tile {url} "
                               f"(internet needed for source 3): {e}") from e

        dem = np.where(np.ma.getmaskarray(arr), np.nan,
                       arr.filled(np.nan).astype("float64"))
        if np.isnan(dem).all():
            continue

        # Cell size in metres (DEM is geographic; local-scale approximation)
        lat_mid = 0.5 * (wy0 + wy1)
        dx_m = abs(tr.a) * 111_320.0 * math.cos(math.radians(lat_mid))
        dy_m = abs(tr.e) * 110_574.0

        gy, gx = np.gradient(dem, dy_m, dx_m)
        slope = np.degrees(np.arctan(np.hypot(gx, gy)))

        # Cache the slope raster (our study area fits one tile)
        if not slope_saved and len(urls) == 1:
            with rasterio.open(F_SLOPE_RASTER, "w", driver="GTiff",
                               height=slope.shape[0], width=slope.shape[1],
                               count=1, dtype="float32", crs=tile_crs,
                               transform=tr, nodata=float("nan")) as dst:
                dst.write(slope.astype("float32"), 1)
            slope_saved = True
            print(f"[info] Slope raster cached -> {F_SLOPE_RASTER}")

        # Classify + polygonize ONLY susceptible cells (flat cells stay empty)
        classes = [
            ("High", slope >= SLOPE_HIGH_DEG),
            ("Moderate", (slope >= SLOPE_MODERATE_DEG) & (slope < SLOPE_HIGH_DEG)),
        ]
        for label, mask in classes:
            mask = mask & ~np.isnan(slope)
            if not mask.any():
                continue
            polys = [shape(g) for g, v in
                     rio_shapes(mask.astype("uint8"), mask=mask, transform=tr) if v == 1]
            z = gpd.GeoDataFrame({"susceptibility": [label] * len(polys)},
                                 geometry=polys, crs=tile_crs).to_crs(TARGET_CRS)
            zone_gdfs.append(z)

    if not zone_gdfs:
        return gpd.GeoDataFrame({"susceptibility": pd.Series(dtype="object")},
                                geometry=[], crs=TARGET_CRS), slope_saved

    gdf = pd.concat(zone_gdfs, ignore_index=True)
    gdf = gpd.clip(gdf, gpd.GeoSeries([study_poly_utm], crs=TARGET_CRS))
    gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
    return gdf[["susceptibility", "geometry"]], slope_saved


def main(force: bool = False) -> None:
    if F_LANDSLIDE_ZONES.exists() and not force:
        print(f"[skip] Landslide zones already cached -> {F_LANDSLIDE_ZONES}")
        return

    study_poly = load_study_polygon()

    if F_LANDSLIDE_REAL.exists():
        gdf_zones = gpd.clip(load_real_zones(),
                             gpd.GeoSeries([study_poly], crs=TARGET_CRS))
    elif F_LANDSLIDE_INVENTORY.exists():
        gdf_zones = load_inventory_zones(study_poly)
    else:
        print("[warn] No landslide data files found — building DEM slope proxy.")
        gdf_zones, _ = slope_proxy_zones(study_poly)

    if len(gdf_zones) == 0:
        print("[warn] No landslide-susceptible area detected inside the study boundary.")
        print("       (Expected for flat coastal Colombo — the veto layer is inactive;")
        print("       Step 13 will treat landslide feasibility as 1.0 everywhere.)")
        return

    # One (dissolved) polygon per class -> clean spatial joins downstream
    gdf_zones = gdf_zones.dissolve(by="susceptibility", as_index=False).reset_index(drop=True)
    gdf_zones.to_file(F_LANDSLIDE_ZONES, driver="GeoJSON")

    print(f"[done] Landslide hazard zones saved -> {F_LANDSLIDE_ZONES}")
    print(f"       Classes present: {sorted(gdf_zones['susceptibility'].unique())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 12b: landslide hazard zones")
    parser.add_argument("--force", action="store_true", help="rebuild even if cached")
    main(parser.parse_args().force)