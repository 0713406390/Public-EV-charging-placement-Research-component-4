"""
STEP 23 — Build the final phased rollout plan.

Reads:  data/phase4_station_selection.csv   (Step 22)
        data/phase3_scored_candidates.geojson (Phase 3, Step 19)
Saves:  data/component4_final_phased_plan.geojson  <-- for dashboard integration

Each selected candidate gets: station_id (S01...), Phase, Recommended_Capacity,
and the marginal gain that justified its selection.

Run:  python step23_phased_plan.py [--force]
"""

import argparse

import pandas as pd
import geopandas as gpd

from config import CAPACITY_MAP, F_SELECTION, F_SCORED, F_FINAL_PLAN


def main(force: bool = False) -> None:
    if F_FINAL_PLAN.exists() and not force:
        print(f"[skip] Final plan already cached -> {F_FINAL_PLAN}")
        return

    sel = pd.read_csv(F_SELECTION)
    gdf_candidates = gpd.read_file(F_SCORED).to_crs("EPSG:32644")

    # Pull the chosen candidate rows (positional) IN DEPLOYMENT ORDER.
    # The selection CSV is the single source of truth — no dedup tricks.
    gdf_plan = gdf_candidates.iloc[sel["cand_row"].to_numpy()].copy()
    gdf_plan = gdf_plan.reset_index(drop=True)

    gdf_plan["station_id"] = sel["station_id"].to_numpy()
    gdf_plan["Phase"] = sel["phase"].to_numpy()
    gdf_plan["seq_in_phase"] = sel["seq_in_phase"].to_numpy()
    gdf_plan["gain"] = sel["gain"].to_numpy()
    gdf_plan["Recommended_Capacity"] = gdf_plan["Phase"].map(CAPACITY_MAP)

    print("\nFinal phased rollout plan:")
    print(gdf_plan[["station_id", "Phase", "Recommended_Capacity",
                    "Suitability_Score", "gain"]].to_string(index=False))

    gdf_plan.to_file(F_FINAL_PLAN, driver="GeoJSON")
    print(f"\n[done] Final phased rollout plan exported -> {F_FINAL_PLAN}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 23: build final phased plan")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)