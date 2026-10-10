"""
STEP 12 — Grid risk zones (Component 3: substation constraint polygons).

Reads:  data/grid_risk_zones_real.geojson  IF YOUR TEAMMATE'S FILE EXISTS
        -> must contain a 'risk_zone' column with values Red / Orange / Amber
Otherwise: SIMULATES placeholder zones derived from the study-area bounds.

Saves:  data/phase2_grid_risk_zones.geojson

Run:  python step12_grid_risk_zones.py [--force]
"""

import argparse

import geopandas as gpd
from shapely.geometry import box

from config import TARGET_CRS, F_RISK_REAL, F_RISK_ZONES, load_study_polygon


def simulate_placeholder(boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """=== PLACEHOLDER — the 'REPLACE THIS BLOCK' from the original script.
    NOTE: zones are derived from the REAL boundary bounds so they always land
    inside the study area. (The original hard-coded box(375000, 344500, ...)
    had a northing far north of Colombo, so the veto never triggered!)"""
    print("[warn] No real grid-risk data found — SIMULATING placeholder zones.")
    minx, miny, maxx, maxy = boundary.total_bounds
    w, h = maxx - minx, maxy - miny

    return gpd.GeoDataFrame(
        {
            "risk_zone": ["Red", "Orange", "Amber"],
            "geometry": [
                box(minx + 0.45 * w, miny + 0.45 * h,
                    minx + 0.55 * w, miny + 0.55 * h),   # centre of study area
                box(minx + 0.15 * w, miny + 0.60 * h,
                    minx + 0.25 * w, miny + 0.70 * h),   # north-west area
                box(minx + 0.65 * w, miny + 0.15 * h,
                    minx + 0.78 * w, miny + 0.28 * h),   # south-east area
            ],
        },
        crs=TARGET_CRS,
    )


def main(force: bool = False) -> None:
    if F_RISK_ZONES.exists() and not force:
        print(f"[skip] Risk zones already cached -> {F_RISK_ZONES}")
        return

    if F_RISK_REAL.exists():
        print(f"[info] Real grid-risk data found -> {F_RISK_REAL}")
        gdf_risk = gpd.read_file(F_RISK_REAL).to_crs(TARGET_CRS)
        if "risk_zone" not in gdf_risk.columns:
            raise ValueError("Real risk file must contain a 'risk_zone' column "
                             "(values: Red / Orange / Amber).")
    else:
        boundary = gpd.GeoDataFrame(geometry=[load_study_polygon()], crs=TARGET_CRS)
        gdf_risk = simulate_placeholder(boundary)

    gdf_risk.to_file(F_RISK_ZONES, driver="GeoJSON")
    print(f"[done] Saved {len(gdf_risk)} risk zones -> {F_RISK_ZONES}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 12: grid risk zones")
    parser.add_argument("--force", action="store_true", help="re-extract even if cached")
    main(parser.parse_args().force)