"""
STEP 22 — Phased greedy set-cover optimization (the Component 4 core).

Reads:  data/phase4_distance_matrix.npz    (Step 21)
        data/phase2_integrated_grid.geojson (for base demand, aligned via grid_id)
Saves:  data/phase4_station_selection.csv
        One row per station: station_id, phase, seq_in_phase, cand_row,
        cand_osmid, gain.

Algorithm per phase:
    1. Scale base demand by the phase's demand_multiplier
    2. Greedy max-coverage: pick the candidate whose distance-decayed
       satisfaction satisfies the most UNMET demand
    3. Hard constraints: 500 m inter-station spacing + never re-pick a
       station already built in an earlier phase (blacklist)

Run:  python step22_greedy_optimizer.py [--force]
"""

import argparse

import numpy as np
import pandas as pd
import geopandas as gpd

from config import (DT_M, THETA, MIN_STATION_SPACING_M, SPACING_ACROSS_PHASES,
                    PHASES, F_SCORED, F_GRID_FINAL, F_DIST_MATRIX, F_SELECTION)


def greedy_set_cover(satisfaction, demand, cand_xy, k, min_dist,
                     blocked=(), spacing_against=()):
    """
    Greedy maximum-coverage with distance decay.

    satisfaction   : (n_candidates, n_cells) precomputed exp(-theta*d), 0 beyond DT
    demand         : (n_cells,) demand weight per cell
    blocked        : indices that can NEVER be selected (earlier phases)
    spacing_against: indices the min-distance rule is checked against
                     (earlier phases too, if SPACING_ACROSS_PHASES)

    Returns (newly_selected_indices, their_gains).
    """
    n_candidates, n_cells = satisfaction.shape
    demand = np.asarray(demand, dtype=float)

    spacing_pts = list(spacing_against)
    new_idx, new_gains = [], []
    current_cov = np.zeros(n_cells)

    for _ in range(k):
        # --- Hard constraint 1: minimum inter-station spacing --------------
        valid = np.ones(n_candidates, dtype=bool)
        for j in spacing_pts:
            d = np.hypot(cand_xy[:, 0] - cand_xy[j, 0],
                         cand_xy[:, 1] - cand_xy[j, 1])
            valid[d < min_dist] = False

        # --- Hard constraint 2: never re-pick earlier-phase stations -------
        valid[list(blocked)] = False

        if not valid.any():
            print("  [warn] No valid candidates left (spacing constraint). Stopping early.")
            break

        # --- Vectorised marginal gain --------------------------------------
        # gain_i = sum_j demand_j * (min(1, cov_j + s_ij) - cov_j)
        #        = sum_j demand_j * min(s_ij, 1 - cov_j)
        room = np.clip(1.0 - current_cov, 0.0, 1.0)        # unmet coverage fraction
        gains = np.minimum(satisfaction, room) @ demand    # (n_candidates,)
        gains[~valid] = -1.0

        best = int(np.argmax(gains))
        if gains[best] <= 1e-9:
            print("  [warn] No remaining candidate satisfies any unmet demand. Stopping early.")
            break

        new_idx.append(best)
        new_gains.append(float(gains[best]))
        spacing_pts.append(best)
        current_cov = np.minimum(1.0, current_cov + satisfaction[best])

        print(f"    Selected candidate row {best:>4} | marginal gain: {gains[best]:.2f}")

    return new_idx, new_gains


def main(force: bool = False) -> None:
    if F_SELECTION.exists() and not force:
        print(f"[skip] Station selection already cached -> {F_SELECTION}")
        return

    if not F_DIST_MATRIX.exists():
        raise FileNotFoundError(f"{F_DIST_MATRIX} not found — run step21_distance_matrix.py first.")

    data = np.load(F_DIST_MATRIX, allow_pickle=False)
    dist_matrix = data["dist"]
    cand_xy = data["cand_xy"]
    cand_osmid_saved = data["cand_osmid"]
    grid_id_saved = data["grid_id"]

    # --- Alignment checks against the cached source files ------------------
    gdf_candidates = gpd.read_file(F_SCORED).to_crs("EPSG:32644")
    cand_osmid_file = gdf_candidates["osmid"].astype(str).to_numpy()
    if len(cand_osmid_file) != len(cand_osmid_saved) or \
            not np.array_equal(cand_osmid_file, cand_osmid_saved):
        raise RuntimeError("Distance matrix out of sync with the candidates file. "
                           "Re-run: python step21_distance_matrix.py --force")

    gdf_grid = gpd.read_file(F_GRID_FINAL).to_crs("EPSG:32644")
    gdf_feasible = gdf_grid[gdf_grid["grid_feasibility"] > 0]
    demand_lookup = gdf_feasible.set_index("grid_id")["smoothed_demand"]
    base_demand = demand_lookup.reindex(grid_id_saved).to_numpy()
    if np.isnan(base_demand).any():
        raise RuntimeError("Grid file out of sync with the distance matrix. "
                           "Re-run: python step21_distance_matrix.py --force")

    # --- Precompute the satisfaction matrix (decay + hard DT cutoff) -------
    satisfaction = np.where(dist_matrix <= DT_M, np.exp(-THETA * dist_matrix), 0.0)
    print(f"Satisfaction matrix ready (DT={DT_M:.0f} m, theta={THETA}).")

    # --- Run the phased deployment ------------------------------------------
    all_selected = []
    rows = []
    station_counter = 0

    for phase_name, params in PHASES.items():
        k = params["K"]
        mult = params["demand_multiplier"]
        print(f"\n--- Running {phase_name} (target: {k} stations, demand x{mult}) ---")

        demand = base_demand * mult
        spacing_against = all_selected if SPACING_ACROSS_PHASES else []

        new_idx, new_gains = greedy_set_cover(
            satisfaction, demand, cand_xy, k, MIN_STATION_SPACING_M,
            blocked=tuple(all_selected),
            spacing_against=tuple(spacing_against),
        )

        for seq, (idx, gain) in enumerate(zip(new_idx, new_gains), start=1):
            station_counter += 1
            rows.append({
                "station_id": f"S{station_counter:02d}",
                "phase": phase_name,
                "seq_in_phase": seq,
                "cand_row": idx,
                "cand_osmid": str(cand_osmid_saved[idx]),
                "gain": round(gain, 4),
            })

        all_selected.extend(new_idx)
        print(f"  -> {len(new_idx)} new stations | total so far: {len(all_selected)}")

    # --- Network performance report (base demand) ----------------------------
    if all_selected:
        total_cov = np.minimum(1.0, satisfaction[all_selected].sum(axis=0))
        satisfied = float((total_cov * base_demand).sum())
        total = float(base_demand.sum())
        print(f"\nNetwork coverage of base demand: "
              f"{satisfied:.1f} / {total:.1f} ({100 * satisfied / max(total, 1e-9):.1f}%)")

    pd.DataFrame(rows).to_csv(F_SELECTION, index=False)
    print(f"[done] Saved {len(rows)} station selections -> {F_SELECTION}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 22: phased greedy optimization")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)