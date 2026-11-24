"""
STEP 4 — Download water bodies and build the flood-risk exclusion zone.
"""

import argparse
import geopandas as gpd
import osmnx as ox
from shapely.validation import make_valid

from config import (
    TAGS_WATER, TARGET_CRS, FLOOD_BUFFER_M,
    F_WATER, F_FLOOD, load_study_polygon, dissolve_geometry
)


def main(force: bool = False) -> None:
    if F_WATER.exists() and F_FLOOD.exists() and not force:
        print(f"[skip] Water data already cached -> {F_WATER}")
        return

    study_area = load_study_polygon()

    print("Extracting water bodies (rivers, canals, wetlands) for flood-risk exclusion...")
    gdf_water = ox.features_from_polygon(study_area, tags=TAGS_WATER).reset_index()

    gdf_water = gdf_water[
        gdf_water.geom_type.isin(["Polygon", "MultiPolygon", "LineString", "MultiLineString"])
    ].copy()
    gdf_water = gdf_water.to_crs(TARGET_CRS)
    gdf_water["geometry"] = gdf_water.geometry.apply(make_valid)

    keep = [c for c in ("element_type", "osmid", "name", "natural", "waterway", "geometry")
            if c in gdf_water.columns]
    gdf_water = gdf_water[keep]
    gdf_water.to_file(F_WATER, driver="GeoJSON")

    print(f"Buffering water bodies by {FLOOD_BUFFER_M} m for flood exclusion...")
    buffered = gdf_water.geometry.buffer(FLOOD_BUFFER_M)
    flood_polygon = dissolve_geometry(gpd.GeoSeries(buffered, crs=TARGET_CRS))
    gdf_flood = gpd.GeoDataFrame(
        {"hazard_type": ["Flood"], "buffer_m": [FLOOD_BUFFER_M]},
        geometry=[flood_polygon],
        crs=TARGET_CRS,
    )
    gdf_flood.to_file(F_FLOOD, driver="GeoJSON")
    print(f"[done] Flood exclusion zone created ({FLOOD_BUFFER_M} m buffer).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 4: water & flood exclusion zone")
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    main(parser.parse_args().force)