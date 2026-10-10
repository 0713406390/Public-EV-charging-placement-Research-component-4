"""
STEP 9 — Demand points (dasymetric EV demand).

Reads:  data/demand_points_real.geojson  IF YOUR TEAMMATE'S FILE EXISTS
        -> must contain a numeric 'ev_demand' column (any CRS, auto-reprojected)
Otherwise: SIMULATES placeholder points so the pipeline runs end-to-end.

Saves:  data/phase2_demand_points.geojson

Run:  python step9_demand_points.py [--force]
"""

import argparse

import numpy as np
import geopandas as gpd
from shapely.geometry import Point

from config import (TARGET_CRS, N_SIM_DEMAND_POINTS,
                    F_DEMAND_REAL, F_DEMAND_PTS, load_study_polygon)


def simulate_placeholder(boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """=== PLACEHOLDER — the 'REPLACE THIS BLOCK' from the original script.
    Swap in real data simply by saving it as data/demand_points_real.geojson."""
    print("[warn] No real demand data found — SIMULATING placeholder points.")
    np.random.seed(42)
    minx, miny, maxx, maxy = boundary.total_bounds
    xs = np.random.uniform(minx, maxx, N_SIM_DEMAND_POINTS)
    ys = np.random.uniform(miny, maxy, N_SIM_DEMAND_POINTS)
    return gpd.GeoDataFrame(
        {"ev_demand": np.random.randint(1, 5, N_SIM_DEMAND_POINTS)},
        geometry=[Point(x, y) for x, y in zip(xs, ys)],
        crs=TARGET_CRS,
    )


def main(force: bool = False) -> None:
    if F_DEMAND_PTS.exists() and not force:
        print(f"[skip] Demand points already cached -> {F_DEMAND_PTS}")
        return

    if F_DEMAND_REAL.exists():
        print(f"[info] Real demand data found -> {F_DEMAND_REAL}")
        gdf_demand = gpd.read_file(F_DEMAND_REAL).to_crs(TARGET_CRS)
        if "ev_demand" not in gdf_demand.columns:
            raise ValueError("Real demand file must contain an 'ev_demand' column.")
    else:
        boundary = gpd.GeoDataFrame(geometry=[load_study_polygon()], crs=TARGET_CRS)
        gdf_demand = simulate_placeholder(boundary)

    gdf_demand.to_file(F_DEMAND_PTS, driver="GeoJSON")
    print(f"[done] Saved {len(gdf_demand)} demand points -> {F_DEMAND_PTS}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 9: demand points")
    parser.add_argument("--force", action="store_true", help="re-extract even if cached")
    main(parser.parse_args().force)