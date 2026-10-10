"""
STEP 19 — Normalize all criteria and compute the Weighted-Sum suitability score.

Reads:  data/phase3_candidates_with_demand.geojson (Step 18)
Saves:  data/phase3_scored_candidates.geojson  <-- FINAL Phase 3 output for Phase 4

Criteria:
    norm_demand     higher is better     (weight W_DEMAND)
    norm_traffic    higher is better     (weight W_TRAFFIC)
    norm_grid_prox  closer is better     (weight W_GRID_PROX)
                    1.0 if dist <= 50 m, linear decay to 0.0 at 200 m

Tuning: change the weights in config.py and re-run ONLY this step.

Run:  python step19_normalize_score.py [--force]
"""

import argparse

import numpy as np
import pandas as pd
import geopandas as gpd

from config import (W_DEMAND, W_TRAFFIC, W_GRID_PROX,
                    GRID_PROX_FULL_M, GRID_PROX_ZERO_M,
                    F_WITH_DEMAND, F_SCORED)


def min_max_normalize(series: pd.Series) -> pd.Series:
    """Scale strictly between 0 and 1 (safe against constant series)."""
    span = series.max() - series.min()
    if pd.isna(span) or span == 0:
        return pd.Series(0.0, index=series.index)
    return (series - series.min()) / span


def grid_proximity_score(dist_m: pd.Series) -> pd.Series:
    """1.0 at/below FULL threshold, 0.0 at/above ZERO threshold,
    linear decay in between (JRC guidance)."""
    span = GRID_PROX_ZERO_M - GRID_PROX_FULL_M
    return np.clip(1.0 - (dist_m - GRID_PROX_FULL_M) / span, 0.0, 1.0)


def main(force: bool = False) -> None:
    if F_SCORED.exists() and not force:
        print(f"[skip] Scored candidates already cached -> {F_SCORED}")
        return

    gdf = gpd.read_file(F_WITH_DEMAND)

    # --- 1. Normalize demand (higher = better) ---------------------------
    gdf["norm_demand"] = min_max_normalize(gdf["local_demand"])

    # --- 2. Normalize traffic / betweenness (higher = better) ------------
    gdf["betweenness"] = gdf["betweenness"].fillna(0)
    gdf["norm_traffic"] = min_max_normalize(gdf["betweenness"])

    # --- 3. Grid proximity (closer = better, with decay) ------------------
    gdf["norm_grid_prox"] = grid_proximity_score(gdf["dist_to_grid_m"])

    print("All criteria normalized to 0-1 scale.")

    # --- 4. Weighted Sum Model (Map Algebra) -------------------------------
    gdf["Suitability_Score"] = (
        W_DEMAND * gdf["norm_demand"]
        + W_TRAFFIC * gdf["norm_traffic"]
        + W_GRID_PROX * gdf["norm_grid_prox"]
    )

    # --- 5. Rank and report -------------------------------------------------
    gdf = gdf.sort_values("Suitability_Score", ascending=False).reset_index(drop=True)
    gdf["rank"] = range(1, len(gdf) + 1)

    print("\nTop 5 Candidate Locations for EV Charging:")
    print(gdf[["name", "candidate_source", "Suitability_Score",
               "dist_to_grid_m", "local_demand"]].head().to_string(index=False))

    gdf.to_file(F_SCORED, driver="GeoJSON")
    print(f"\n[done] Saved {len(gdf)} scored candidates -> {F_SCORED}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 19: normalize & score")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)