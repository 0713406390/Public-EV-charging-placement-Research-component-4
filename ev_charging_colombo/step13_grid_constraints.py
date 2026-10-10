"""
STEP 13 — Apply grid constraints (TAF Novelty #1: the hard veto).

Reads:  data/phase2_grid_smoothed_demand.geojson (Step 11)
        data/phase2_grid_risk_zones.geojson      (Step 12)
Saves:  data/phase2_integrated_grid.geojson  <-- FINAL Phase 2 output for Phase 3

Feasibility rules:
    intersects Red or Orange zone -> 0.0  (vetoed)
    intersects Amber zone         -> 0.5  (penalty, used in Phase 3)
    no overlap                    -> 1.0  (fully feasible)

Run:  python step13_grid_constraints.py [--force]
"""

import argparse

import geopandas as gpd

from config import RISK_SEVERITY, F_GRID_SMOOTH, F_RISK_ZONES, F_GRID_FINAL


def main(force: bool = False) -> None:
    if F_GRID_FINAL.exists() and not force:
        print(f"[skip] Integrated grid already cached -> {F_GRID_FINAL}")
        return

    gdf_grid = gpd.read_file(F_GRID_SMOOTH)
    gdf_risk = gpd.read_file(F_RISK_ZONES)

    # 1. Which cells intersect a risk zone? ('left' keeps risk-free cells as NaN)
    joined = gpd.sjoin(
        gdf_grid, gdf_risk[["risk_zone", "geometry"]],
        how="left", predicate="intersects",
    )

    # 2. Map zone severity -> feasibility multiplier (NaN -> 1.0)
    joined["grid_feasibility"] = joined["risk_zone"].map(RISK_SEVERITY).fillna(1.0)

    # 3. If a cell overlaps SEVERAL zones, keep the WORST case
    #    (the original script kept duplicate rows for such cells)
    joined = joined.sort_values("grid_feasibility")
    gdf_final = (joined.drop_duplicates(subset="grid_id", keep="first")
                 .drop(columns=["index_right"], errors="ignore")
                 .reset_index(drop=True))
    gdf_final["risk_zone"] = gdf_final["risk_zone"].fillna("None")

    # 4. Report
    n_vetoed = int((gdf_final["grid_feasibility"] == 0.0).sum())
    n_amber = int((gdf_final["grid_feasibility"] == 0.5).sum())
    n_feasible = len(gdf_final) - n_vetoed - n_amber
    print(f"[done] Grid constraints applied: {n_vetoed} cells vetoed (Red/Orange), "
          f"{n_amber} penalised (Amber), {n_feasible} fully feasible.")

    gdf_final.to_file(F_GRID_FINAL, driver="GeoJSON")
    print(f"Phase 2 Complete. Grid saved for Phase 3 -> {F_GRID_FINAL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 13: apply grid constraints")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)