"""
STEP 22 — STATEFUL phased greedy set-cover optimization (Component 4 core).

Reads:  data/phase4_distance_matrix.npz    (Step 21)
        data/phase2_integrated_grid.geojson (for base demand, aligned via grid_id)
Saves:  data/phase4_station_selection.csv      (one row per station, in build order)
        data/phase4_deployment_metrics.csv     (coverage KPI per phase — thesis table)

The STATEFUL novelty (kept exactly as designed):
    - current_coverage carries over BETWEEN phases, so Phase 2/3 stations are
      chosen to complement — not duplicate — the existing network
    - the 500 m spacing rule is enforced against ALL stations ever built,
      not just the ones from the current phase

Run:  python step22_stateful_optimizer.py [--force]
"""

import argparse

import numpy as np
import pandas as pd
import geopandas as gpd

from config import (DT_M, THETA, MIN_STATION_SPACING_M, PHASES,
                    F_SCORED, F_GRID_FINAL, F_DIST_MATRIX, F_SELECTION, F_METRICS)


def run_stateful_phase(satisfaction, demand, cand_xy, k, min_dist,
                       history_idx, current_cov):
    """
    Runs ONE phase of the greedy algorithm while respecting the whole network.

    satisfaction : (n_cand, n_cells) precomputed exp(-theta*d), 0 beyond DT
    demand       : (n_cells,) demand weights for THIS phase (already scaled)
    history_idx  : global indices of ALL stations built so far (all phases)
    current_cov  : (n_cells,) coverage fractions carried over from prior phases

    Returns (new_indices, gains, updated_coverage, updated_history).
    """
    n_candidates = satisfaction.shape[0]
    new_idx, new_gains = [], []

    for _ in range(k):
        # --- 1. STRICT 500 m exclusion against ALL previous stations --------
        valid = np.ones(n_candidates, dtype=bool)
        for j in history_idx:
            d = np.hypot(cand_xy[:, 0] - cand_xy[j, 0],
                         cand_xy[:, 1] - cand_xy[j, 1])
            valid[d < min_dist] = False
        valid[list(history_idx)] = False   # never rebuild an existing station

        if not valid.any():
            print("  -> No valid locations left respecting 500m constraint!")
            break

        # --- 2. VECTORIZED marginal gain for ALL valid candidates -----------
        valid_idx = np.where(valid)[0]
        new_coverage = np.minimum(1.0,
                                  current_cov[None, :] + satisfaction[valid_idx, :])
        marginal_coverage = new_coverage - current_cov[None, :]
        gains = np.sum(demand * marginal_coverage, axis=1)

        # --- 3. Select the best candidate ------------------------------------
        best_local = int(np.argmax(gains))
        if gains[best_local] <= 1e-9:
            print("  -> No remaining candidate satisfies any unmet demand. Stopping early.")
            break
        best_global = int(valid_idx[best_local])

        # --- 4. Update state (coverage carries to the NEXT phase) ------------
        new_idx.append(best_global)
        new_gains.append(float(gains[best_local]))
        history_idx.append(best_global)
        current_cov = np.minimum(1.0, current_cov + satisfaction[best_global])

        print(f"  -> Selected Node {best_global} | Marginal Gain: {gains[best_local]:.2f}")

    return new_idx, new_gains, current_cov, history_idx


def main(force: bool = False) -> None:
    if F_SELECTION.exists() and F_METRICS.exists() and not force:
        print(f"[skip] Optimization already cached -> {F_SELECTION}")
        return

    if not F_DIST_MATRIX.exists():
        raise FileNotFoundError(f"{F_DIST_MATRIX} not found — run step21_distance_matrix.py first.")

    # allow_pickle=True is needed for old cached .npz files where cand_osmid was
    # saved as a Python-string object array.  Re-running step21 --force will
    # produce a fixed-width unicode array that no longer needs pickle.
    data = np.load(F_DIST_MATRIX, allow_pickle=True)
    dist_matrix = data["dist"]
    cand_xy = data["cand_xy"]
    # Normalise to plain numpy str_ array regardless of how it was saved
    cand_osmid_saved = np.array(data["cand_osmid"], dtype=np.str_)
    grid_id_saved = data["grid_id"]

    # --- Alignment checks (fail loudly if the matrix is stale) --------------
    gdf_candidates = gpd.read_file(F_SCORED).to_crs("EPSG:32644")
    cand_osmid_file = gdf_candidates["osmid"].astype(str).to_numpy()
    if len(cand_osmid_file) != len(cand_osmid_saved) or \
            not np.array_equal(cand_osmid_file, cand_osmid_saved):
        raise RuntimeError("Distance matrix out of sync with candidates. "
                           "Re-run: python step21_distance_matrix.py --force")

    gdf_grid = gpd.read_file(F_GRID_FINAL).to_crs("EPSG:32644")
    gdf_feasible = gdf_grid[gdf_grid["grid_feasibility"] > 0]
    demand_lookup = gdf_feasible.set_index("grid_id")["smoothed_demand"]
    base_demand = demand_lookup.reindex(grid_id_saved).to_numpy()
    if np.isnan(base_demand).any():
        raise RuntimeError("Grid file out of sync with distance matrix. "
                           "Re-run: python step21_distance_matrix.py --force")

    # --- Pre-compute satisfaction ONCE (saves massive computation time) -----
    satisfaction_matrix = np.where(dist_matrix <= DT_M,
                                   np.exp(-THETA * dist_matrix), 0.0)
    print(f"Satisfaction matrix ready (DT={DT_M:.0f} m, theta={THETA}).")

    # --- Global state --------------------------------------------------------
    current_coverage = np.zeros(len(base_demand))   # starts at zero
    selected_history = []                            # indices of ALL stations

    selection_rows, metric_rows = [], []
    station_counter = 0

    for phase_name, cfg in PHASES.items():
        print(f"\n{'=' * 40}")
        print(f"RUNNING {phase_name} | Target: {cfg['K']} NEW stations")
        print(f"{'=' * 40}")

        phase_demand = base_demand * cfg["demand_mult"]

        new_idx, new_gains, current_coverage, selected_history = run_stateful_phase(
            satisfaction_matrix, phase_demand, cand_xy,
            cfg["K"], MIN_STATION_SPACING_M, selected_history, current_coverage,
        )

        for seq, (idx, gain) in enumerate(zip(new_idx, new_gains), start=1):
            station_counter += 1
            selection_rows.append({
                "station_id": f"S{station_counter:02d}",
                "phase": phase_name,
                "seq_in_phase": seq,
                "cand_row": idx,
                "cand_osmid": str(cand_osmid_saved[idx]),
                "gain": round(gain, 4),
            })

        # --- Phase KPI: cumulative network coverage against THIS phase demand
        covered_demand = float((current_coverage * phase_demand).sum())
        total_demand = float(phase_demand.sum())
        metric_rows.append({
            "phase": phase_name,
            "k_target": cfg["K"],
            "k_built": len(new_idx),
            "demand_multiplier": cfg["demand_mult"],
            "stations_in_network": len(selected_history),
            "coverage_pct": round(100 * covered_demand / max(total_demand, 1e-9), 2),
        })
        print(f"Total stations in network now: {len(selected_history)}")

    pd.DataFrame(selection_rows).to_csv(F_SELECTION, index=False)
    pd.DataFrame(metric_rows).to_csv(F_METRICS, index=False)

    print("\nDeployment metrics per phase:")
    print(pd.DataFrame(metric_rows).to_string(index=False))
    print(f"\n[done] Saved {len(selection_rows)} selections -> {F_SELECTION}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 22: stateful phased optimizer")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)