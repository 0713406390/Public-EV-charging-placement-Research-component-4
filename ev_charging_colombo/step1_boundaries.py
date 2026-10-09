"""
STEP 1 — Download the administrative boundaries of the study area.

Saves: data/study_area_boundaries.geojson  (the 4 polygons)
       data/study_area_boundary.geojson    (1 dissolved polygon)

Run:  python step1_boundaries.py [--force]
"""

import argparse

import geopandas as gpd
import osmnx as ox

from config import PLACES, F_BOUNDARIES, F_STUDY_POLYGON, dissolve_geometry


def main(force: bool = False) -> None:
    if F_BOUNDARIES.exists() and F_STUDY_POLYGON.exists() and not force:
        print(f"[skip] Boundaries already cached -> {F_BOUNDARIES}")
        return

    print("Fetching administrative boundaries...")
    gdf_boundaries = ox.geocode_to_gdf(PLACES)

    # Keep only useful columns so the GeoJSON stays small
    keep = [c for c in ("display_name", "name") if c in gdf_boundaries.columns] + ["geometry"]
    gdf_boundaries = gdf_boundaries[keep]

    # Raw 4 polygons (kept in EPSG:4326 — standard for GeoJSON)
    gdf_boundaries.to_file(F_BOUNDARIES, driver="GeoJSON")

    # Single dissolved polygon every other step will use
    study_polygon = dissolve_geometry(gdf_boundaries)
    gpd.GeoDataFrame(geometry=[study_polygon], crs=gdf_boundaries.crs).to_file(
        F_STUDY_POLYGON, driver="GeoJSON"
    )

    print(f"[done] Saved {F_BOUNDARIES.name} and {F_STUDY_POLYGON.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 1: download study-area boundaries")
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    main(parser.parse_args().force)