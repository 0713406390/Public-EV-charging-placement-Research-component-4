"""
STEP 4 — Download water bodies and build the flood-risk exclusion zone.

Reads:    data/study_area_boundary.geojson (Step 1)
Saves:    data/water_bodies.geojson     (raw rivers/canals/waterbodies)
          data/flood_risk_zone.geojson  (single dissolved 50 m buffer)

Run:  python step4_water_flood.py [--force]
"""

import argparse

import geopandas as gpd
import osmnx as ox

from config import (TAGS_WATER, TARGET_CRS, FLOOD_BUFFER_M,
                    F_WATER, F_FLOOD, load_study_polygon, dissolve_geometry)


def main(force: bool = False) -> None:
    if F_WATER.exists() and F_FLOOD.exists() and not force:
        print(f"[skip] Water data already cached -> {F_WATER}")
        return

    study_area = load_study_polygon()

    print("Extracting water bodies (rivers, canals) for flood-risk proxy...")
    gdf_water = ox.features_from_polygon(study_area, tags=TAGS_WATER)
    gdf_water = gdf_water.reset_index()

    # Keep polygons and lines (drop stray points)
    gdf_water = gdf_water[
        gdf_water.geom_type.isin(["Polygon", "MultiPolygon", "LineString", "MultiLineString"])
    ].copy()
    gdf_water = gdf_water.to_crs(TARGET_CRS)

    # Keep the dataset small & clean
    keep = [c for c in ("element_type", "osmid", "name", "natural", "waterway", "geometry")
            if c in gdf_water.columns]
    gdf_water = gdf_water[keep]
    gdf_water.to_file(F_WATER, driver="GeoJSON")

    # Buffer = "High Flood Risk Zone"
    # (canals like St. Sebastian Canal flood heavily into adjacent streets)
    print(f"Buffering water bodies by {FLOOD_BUFFER_M} m...")
    flood_polygon = dissolve_geometry(gdf_water.buffer(FLOOD_BUFFER_M))
    gdf_flood = gpd.GeoDataFrame(geometry=[flood_polygon], crs=TARGET_CRS)
    gdf_flood.to_file(F_FLOOD, driver="GeoJSON")

    print(f"[done] Flood-risk exclusion zone created ({FLOOD_BUFFER_M} m buffer from water).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 4: water & flood zone")
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    main(parser.parse_args().force)