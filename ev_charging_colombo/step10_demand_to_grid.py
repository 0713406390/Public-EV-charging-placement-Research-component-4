"""
STEP 10 — Assign demand points to grid cells and aggregate raw demand.

Reads:  data/phase2_grid_cells.geojson     (Step 8)
        data/phase2_demand_points.geojson  (Step 9)
Saves:  data/phase2_grid_raw_demand.geojson

Run:  python step10_demand_to_grid.py [--force]
"""

import argparse

import geopandas as gpd

from config import F_GRID_CELLS, F_DEMAND_PTS, F_GRID_RAW


def main(force: bool = False) -> None:
    if F_GRID_RAW.exists() and not force:
        print(f"[skip] Raw grid demand already cached -> {F_GRID_RAW}")
        return

    gdf_grid = gpd.read_file(F_GRID_CELLS)
    gdf_demand = gpd.read_file(F_DEMAND_PTS)

    # Spatial join: which points does each cell CONTAIN?
    joined = gpd.sjoin(
        gdf_grid, gdf_demand[["ev_demand", "geometry"]],
        how="left", predicate="contains",
    )

    # Total raw demand per cell (merge keeps ALL cells, even zero-demand ones)
    demand_per_cell = joined.groupby("grid_id")["ev_demand"].sum().rename("raw_demand")
    gdf_grid_raw = gdf_grid.merge(demand_per_cell, on="grid_id", how="left")
    gdf_grid_raw["raw_demand"] = gdf_grid_raw["raw_demand"].fillna(0)

    gdf_grid_raw.to_file(F_GRID_RAW, driver="GeoJSON")
    print(f"[done] Raw demand mapped to {len(gdf_grid_raw)} grid cells "
          f"(total demand = {gdf_grid_raw['raw_demand'].sum():.0f}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 10: demand -> grid")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)