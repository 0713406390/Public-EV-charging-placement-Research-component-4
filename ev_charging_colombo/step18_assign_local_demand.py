"""
STEP 18 — Attach the smoothed demand of the surrounding grid cell to each candidate.

Reads:  data/phase3_candidates_power_dist.geojson (Step 17)
        data/phase2_integrated_grid.geojson       (Phase 2, Step 13)
Saves:  data/phase3_candidates_with_demand.geojson (adds 'local_demand')

Run:  python step18_assign_local_demand.py [--force]
"""

import argparse

import geopandas as gpd

from config import F_POWER_DIST, F_GRID_FINAL, F_WITH_DEMAND


def main(force: bool = False) -> None:
    if F_WITH_DEMAND.exists() and not force:
        print(f"[skip] Demand-assigned candidates already cached -> {F_WITH_DEMAND}")
        return

    gdf = gpd.read_file(F_POWER_DIST)
    gdf_grid = gpd.read_file(F_GRID_FINAL)

    joined = gpd.sjoin(
        gdf, gdf_grid[["grid_id", "smoothed_demand", "geometry"]],
        how="left", predicate="intersects",
    )

    # A point can technically touch 2 clipped cells -> keep the first match
    joined = (joined
              .sort_index()
              .drop_duplicates(subset=joined.geometry.name, keep="first")
              .drop(columns=["index_right"], errors="ignore"))

    joined = joined.rename(columns={"smoothed_demand": "local_demand"})
    joined["local_demand"] = joined["local_demand"].fillna(0)

    joined.to_file(F_WITH_DEMAND, driver="GeoJSON")
    print(f"[done] Local demand assigned to {len(joined)} candidates "
          f"(max = {joined['local_demand'].max():.4f}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 18: local demand per candidate")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)