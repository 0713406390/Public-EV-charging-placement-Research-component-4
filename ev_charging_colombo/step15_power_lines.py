"""
STEP 15 — Download power distribution lines from OpenStreetMap.

Reads:  data/study_area_boundary.geojson (Phase 1, Step 1 — no re-download!)
Saves:  data/phase3_power_lines.geojson (projected to EPSG:32644, metres)

Run:  python step15_power_lines.py [--force]
"""

import argparse

import geopandas as gpd
import osmnx as ox

from config import TAGS_POWER, TARGET_CRS, F_POWER, load_study_polygon, sanitize_for_geojson


def main(force: bool = False) -> None:
    if F_POWER.exists() and not force:
        print(f"[skip] Power lines already cached -> {F_POWER}")
        return

    study_area = load_study_polygon()

    print("Downloading power line infrastructure from OpenStreetMap...")
    gdf_power = ox.features_from_polygon(study_area, tags=TAGS_POWER)
    gdf_power = gdf_power.reset_index()

    # Keep only lines, project to metres
    gdf_power = gdf_power[gdf_power.geom_type.isin(["LineString", "MultiLineString"])].copy()
    gdf_power = gdf_power.to_crs(TARGET_CRS)

    # Optional refinement: keep only LOW/MEDIUM-voltage distribution lines
    # (uncomment if transmission lines are polluting the proximity score):
    # if "voltage" in gdf_power.columns:
    #     gdf_power["voltage_num"] = pd.to_numeric(gdf_power["voltage"], errors="coerce")
    #     gdf_power = gdf_power[gdf_power["voltage_num"].fillna(0) <= 33000]

    keep = [c for c in ("element_type", "osmid", "name", "voltage", "power", "geometry")
            if c in gdf_power.columns]
    gdf_power = sanitize_for_geojson(gdf_power[keep])

    gdf_power.to_file(F_POWER, driver="GeoJSON")
    print(f"[done] Saved {len(gdf_power)} power line segments -> {F_POWER}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 15: download power lines")
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    main(parser.parse_args().force)