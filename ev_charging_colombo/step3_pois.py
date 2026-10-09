"""
STEP 3 — Download fuel stations and structured-parking POIs.

Reads:    data/study_area_boundary.geojson (Step 1)
Saves:    data/pois_fuel_parking.geojson   (projected points, EPSG:32644)

Run:  python step3_pois.py [--force]
"""

import argparse

import geopandas as gpd
import osmnx as ox

from config import TAGS_POIS, TARGET_CRS, F_POIS, load_study_polygon


def main(force: bool = False) -> None:
    if F_POIS.exists() and not force:
        print(f"[skip] POIs already cached -> {F_POIS}")
        return

    study_area = load_study_polygon()

    print("Extracting fuel stations and parking lots...")
    gdf_pois = ox.features_from_polygon(study_area, tags=TAGS_POIS)

    # Flatten the (element_type, osmid) MultiIndex into normal columns
    gdf_pois = gdf_pois.reset_index()

    # Keep only point geometries (drop polygon footprints for simplicity)
    gdf_pois = gdf_pois[gdf_pois.geom_type == "Point"].copy()

    # Project to the same CRS as the road network
    gdf_pois = gdf_pois.to_crs(TARGET_CRS)

    # Fill missing names / types safely
    if "name" not in gdf_pois.columns:
        gdf_pois["name"] = "Unknown POI"
    gdf_pois["name"] = gdf_pois["name"].fillna("Unknown POI")

    if "amenity" not in gdf_pois.columns:
        gdf_pois["amenity"] = "unknown"
    gdf_pois["poi_type"] = gdf_pois["amenity"].fillna("unknown")

    # Keep the dataset small & clean
    gdf_pois = gdf_pois[["element_type", "osmid", "name", "poi_type", "geometry"]]
    gdf_pois.to_file(F_POIS, driver="GeoJSON")

    print(f"[done] Found {len(gdf_pois)} potential POI candidates (fuel/parking).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 3: download POIs")
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    main(parser.parse_args().force)