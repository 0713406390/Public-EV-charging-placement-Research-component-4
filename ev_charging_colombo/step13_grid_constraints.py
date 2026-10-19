"""
STEP 13 — Apply ALL hazard constraints to the grid (multi-hazard feasibility).

Combines (worst case wins):
    A. Electrical grid risk  (Step 12):  Red/Orange -> 0.0, Amber -> 0.5
    B. Landslide susceptibility (Step 12b): High -> 0.0, Moderate -> 0.5
    No overlap with either   -> 1.0

final grid_feasibility = min(risk_feasibility, landslide_feasibility)

Downstream phases read only 'grid_feasibility', so the Phase 3 veto and the
Phase 4 optimizer pick up landslides with NO further code changes.

Run:  python step13_grid_constraints.py [--force]
"""

import argparse

import geopandas as gpd
import pandas as pd

from config import (RISK_SEVERITY, LANDSLIDE_FEASIBILITY,
                    F_GRID_SMOOTH, F_RISK_ZONES, F_LANDSLIDE_ZONES, F_GRID_FINAL)

RISK_RANK = {"Red": 0, "Orange": 1, "Amber": 2}
RISK_FROM_RANK = {v: k for k, v in RISK_RANK.items()}

LAND_RANK = {"High": 0, "Moderate": 1, "Low": 2}
LAND_FROM_RANK = {v: k for k, v in LAND_RANK.items()}


def worst_zone_per_cell(gdf_grid, gdf_zones, value_col, rank_map):
    """Spatial join cells x hazard polygons -> rank of the WORST zone per cell.
    Returns None if there are no zones / no overlaps."""
    if gdf_zones is None or len(gdf_zones) == 0:
        return None
    joined = gpd.sjoin(gdf_grid[["grid_id", "geometry"]],
                       gdf_zones[[value_col, "geometry"]],
                       how="inner", predicate="intersects")
    if len(joined) == 0:
        return None
    joined["rank"] = joined[value_col].map(rank_map)
    return (joined.groupby("grid_id")["rank"].min()
            .reset_index())


def main(force: bool = False) -> None:
    if F_GRID_FINAL.exists() and not force:
        print(f"[skip] Integrated grid already cached -> {F_GRID_FINAL}")
        return

    gdf_grid = gpd.read_file(F_GRID_SMOOTH)

    # --- A. Electrical grid risk (existing behaviour) -----------------------
    gdf_risk = gpd.read_file(F_RISK_ZONES)
    worst_risk = worst_zone_per_cell(gdf_grid, gdf_risk, "risk_zone", RISK_RANK)
    if worst_risk is not None:
        worst_risk["risk_zone"] = worst_risk["rank"].map(RISK_FROM_RANK)
        worst_risk["risk_feas"] = worst_risk["risk_zone"].map(RISK_SEVERITY)
        gdf_grid = gdf_grid.merge(worst_risk[["grid_id", "risk_zone", "risk_feas"]],
                                  on="grid_id", how="left")
    gdf_grid["risk_zone"] = gdf_grid.get("risk_zone", pd.Series(index=gdf_grid.index)) \
        .fillna("None")
    gdf_grid["risk_feas"] = gdf_grid.get("risk_feas", pd.Series(index=gdf_grid.index)) \
        .fillna(1.0)

    # --- B. Landslide susceptibility (NEW) -----------------------------------
    if F_LANDSLIDE_ZONES.exists():
        gdf_lands = gpd.read_file(F_LANDSLIDE_ZONES)
        gdf_lands["susceptibility"] = gdf_lands["susceptibility"] \
            .astype(str).str.strip().str.capitalize()
    else:
        gdf_lands = None
    worst_land = worst_zone_per_cell(gdf_grid, gdf_lands, "susceptibility", LAND_RANK)
    if worst_land is not None:
        worst_land["landslide_zone"] = worst_land["rank"].map(LAND_FROM_RANK)
        worst_land["landslide_feas"] = worst_land["landslide_zone"] \
            .map(LANDSLIDE_FEASIBILITY)
        gdf_grid = gdf_grid.merge(
            worst_land[["grid_id", "landslide_zone", "landslide_feas"]],
            on="grid_id", how="left")
    gdf_grid["landslide_zone"] = gdf_grid.get("landslide_zone",
                                              pd.Series(index=gdf_grid.index)).fillna("None")
    gdf_grid["landslide_feas"] = gdf_grid.get("landslide_feas",
                                              pd.Series(index=gdf_grid.index)).fillna(1.0)

    # --- Combine: worst case wins (TAF Novelty #1, now multi-hazard) ---------
    gdf_grid["grid_feasibility"] = gdf_grid[["risk_feas", "landslide_feas"]].min(axis=1)

    # --- Report (useful table for the thesis) --------------------------------
    n = len(gdf_grid)
    v_risk = int(((gdf_grid["risk_feas"] == 0) & (gdf_grid["landslide_feas"] > 0)).sum())
    v_land = int(((gdf_grid["landslide_feas"] == 0) & (gdf_grid["risk_feas"] > 0)).sum())
    v_both = int(((gdf_grid["risk_feas"] == 0) & (gdf_grid["landslide_feas"] == 0)).sum())
    v_soft = int((gdf_grid["grid_feasibility"] == 0.5).sum())

    print(f"[done] Multi-hazard constraints applied to {n} cells:")
    print(f"       vetoed by grid risk only : {v_risk}")
    print(f"       vetoed by landslide only : {v_land}")
    print(f"       vetoed by both hazards   : {v_both}")
    print(f"       penalised (worst = 0.5)  : {v_soft}")
    print(f"       fully feasible           : {n - v_risk - v_land - v_both - v_soft}")

    gdf_final = gdf_grid.reset_index(drop=True)
    gdf_final.to_file(F_GRID_FINAL, driver="GeoJSON")
    print(f"Phase 2 Complete. Multi-hazard grid saved for Phase 3 -> {F_GRID_FINAL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 13: multi-hazard constraints")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)