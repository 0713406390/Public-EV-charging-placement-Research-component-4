"""
STEP 21 — Pre-compute the candidate × grid-cell distance matrix.

Reads:  data/phase3_scored_candidates.geojson (Phase 3, Step 19)
        data/phase2_integrated_grid.geojson   (Phase 2, Step 13)
Saves:  data/phase4_distance_matrix.npz
        Contains: dist [n_candidates x n_feasible_cells], cand_xy, grid_xy,
                  cand_osmid (identity check), grid_id (demand alignment).

This is the expensive step — caching it lets you re-tune the optimizer
(theta, DT, K, spacing) by re-running ONLY steps 22-24.

Run:  python step21_distance_matrix.py [--force]
"""

import argparse

import numpy as np
import geopandas as gpd

from config import F_SCORED, F_GRID_FINAL, F_DIST_MATRIX


def main(force: bool = False) -> None:
    if F_DIST_MATRIX.exists() and not force:
        print(f"[skip] Distance matrix already cached -> {F_DIST_MATRIX}")
        return

    gdf_candidates = gpd.read_file(F_SCORED).to_crs("EPSG:32644")
    gdf_grid = gpd.read_file(F_GRID_FINAL).to_crs("EPSG:32644")

    # Only feasible cells (grid_feasibility > 0, incl. Amber 0.5) can receive demand
    gdf_feasible = gdf_grid[gdf_grid["grid_feasibility"] > 0].copy()

    print(f"Calculating distance matrix for {len(gdf_candidates)} candidates "
          f"x {len(gdf_feasible)} feasible grid cells...")

    cand_xy = np.column_stack([gdf_candidates.geometry.x, gdf_candidates.geometry.y])
    grid_xy = np.column_stack([gdf_feasible.geometry.centroid.x,
                               gdf_feasible.geometry.centroid.y])

    # Fully vectorised pairwise distances (no Python loop)
    dx = cand_xy[:, 0][:, None] - grid_xy[:, 0][None, :]
    dy = cand_xy[:, 1][:, None] - grid_xy[:, 1][None, :]
    dist_matrix = np.hypot(dx, dy)

    np.savez_compressed(
        F_DIST_MATRIX,
        dist=dist_matrix,
        cand_xy=cand_xy,
        grid_xy=grid_xy,
        cand_osmid=gdf_candidates["osmid"].astype(str).to_numpy(),
        grid_id=gdf_feasible["grid_id"].to_numpy(),
    )

    print(f"[done] Matrix computed ({dist_matrix.shape[0]} x {dist_matrix.shape[1]}) "
          f"and cached -> {F_DIST_MATRIX}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 21: distance matrix")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)