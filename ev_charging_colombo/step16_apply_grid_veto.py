"""
STEP 16 — Enforce the Phase 2 grid veto on the Phase 1 candidates (Novelty #1).

Reads:  data/phase1_candidates_colombo.geojson  (Phase 1, Step 6)
        data/phase2_integrated_grid.geojson     (Phase 2, Step 13)
Saves:  data/phase3_surviving_candidates.geojson

Rule: any candidate falling inside a cell with grid_feasibility == 0
      (Red/Orange grid-risk zone) is removed permanently.

Run:  python step16_apply_grid_veto.py [--force]
"""

import argparse

import geopandas as gpd

from config import F_CANDIDATES, F_GRID_FINAL, F_SURVIVORS


def main(force: bool = False) -> None:
    if F_SURVIVORS.exists() and not force:
        print(f"[skip] Surviving candidates already cached -> {F_SURVIVORS}")
        return

    gdf_candidates = gpd.read_file(F_CANDIDATES).to_crs("EPSG:32644")
    gdf_grid = gpd.read_file(F_GRID_FINAL).to_crs("EPSG:32644")

    vetoed_cells = gdf_grid[gdf_grid["grid_feasibility"] == 0.0]

    if len(vetoed_cells):
        in_veto = gpd.sjoin(
            gdf_candidates, vetoed_cells[["geometry"]],
            how="inner", predicate="intersects",
        )
        vetoed_ids = in_veto.index.unique()
        gdf_survivors = gdf_candidates[~gdf_candidates.index.isin(vetoed_ids)].copy()
    else:
        # No vetoed cells exist -> everyone survives
        vetoed_ids = []
        gdf_survivors = gdf_candidates.copy()

    gdf_survivors = gdf_survivors.reset_index(drop=True)
    gdf_survivors.to_file(F_SURVIVORS, driver="GeoJSON")

    print(f"Started with {len(gdf_candidates)} candidates.")
    print(f"Vetoed {len(vetoed_ids)} candidates due to Red/Orange Grid Risk.")
    print(f"[done] Proceeding to score {len(gdf_survivors)} surviving candidates.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 16: apply grid veto")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)