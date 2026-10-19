"""
STEP 23 — Build the FINAL phased rollout plan.

Reads:  data/phase4_station_selection.csv       (Step 22)
        data/phase3_scored_candidates.geojson   (Phase 3, Step 19)
Saves:  data/FINAL_Phased_EV_Plan_Colombo.geojson  <-- ultimate output (dashboard)

Each station gets: station_id (S01...), Deployment_Phase, seq_in_phase,
Recommended_Capacity, and the marginal gain that justified it.

Run:  python step23_phased_plan.py [--force]
"""

import argparse

import pandas as pd
import geopandas as gpd

from config import CAPACITY_MAP, F_SELECTION, F_SCORED, F_FINAL_PLAN, F_METRICS


def main(force: bool = False) -> None:
    if F_FINAL_PLAN.exists() and not force:
        print(f"[skip] Final plan already cached -> {F_FINAL_PLAN}")
        return

    sel = pd.read_csv(F_SELECTION)
    if sel.empty:
        raise RuntimeError(
            "Station selection is empty. Step 22 selected zero stations, so there is no phased plan to build. "
            f"Check {F_METRICS} and upstream demand/feasibility inputs, then rerun step22_greedy_optimizer.py --force."
        )
    gdf_candidates = gpd.read_file(F_SCORED).to_crs("EPSG:32644")

    # Deployment order = row order of the selection CSV (single source of truth)
    gdf_plan = gdf_candidates.iloc[sel["cand_row"].to_numpy()].copy().reset_index(drop=True)

    gdf_plan["station_id"] = sel["station_id"].to_numpy()
    gdf_plan["Deployment_Phase"] = sel["phase"].to_numpy()
    gdf_plan["seq_in_phase"] = sel["seq_in_phase"].to_numpy()
    gdf_plan["gain"] = sel["gain"].to_numpy()
    gdf_plan["Recommended_Capacity"] = gdf_plan["Deployment_Phase"].map(CAPACITY_MAP)

    print("\nFinal phased rollout plan:")
    print(gdf_plan[["station_id", "Deployment_Phase", "Recommended_Capacity",
                    "Suitability_Score", "gain"]].to_string(index=False))

    gdf_plan.to_file(F_FINAL_PLAN, driver="GeoJSON")
    print(f"\nSuccess! Final phased plan exported -> {F_FINAL_PLAN}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 23: final phased plan")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)