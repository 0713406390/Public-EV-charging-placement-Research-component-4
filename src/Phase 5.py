import numpy as np
import geopandas as gpd
import pandas as pd

def run_stateful_phase(dist_matrix, satisfaction_matrix, current_demand, 
                       current_coverage, K, min_dist, selected_history_coords):
    """
    Runs one phase of the greedy algorithm while respecting previous phases.
    """
    n_candidates = dist_matrix.shape[0]
    selected_this_phase = []
    
    for _ in range(K):
        # 1. STRICT 500m EXCLUSION CONSTRAINT (Against ALL previous stations)
        valid_mask = np.ones(n_candidates, dtype=bool)
        for (hx, hy) in selected_history_coords:
            dist_to_hist = np.sqrt((cand_coords[:, 0] - hx)**2 + (cand_coords[:, 1] - hy)**2)
            valid_mask[dist_to_hist < min_dist] = False
            
        # If no valid spots left, break
        if not valid_mask.any():
            print("  -> No valid locations left respecting 500m constraint!")
            break

        # 2. VECTORIZED MARGINAL GAIN CALCULATION
        # Calculate potential new coverage for ALL valid candidates at once
        # Shape manipulation for vectorized math: (valid_count, 1) + (1, grid_cells)
        valid_indices = np.where(valid_mask)[0]
        valid_satisfaction = satisfaction_matrix[valid_indices, :]
        
        # New coverage if we place these stations
        new_coverage = np.minimum(1.0, current_coverage + valid_satisfaction)
        
        # The actual marginal gain (what's actually newly satisfied)
        marginal_coverage = new_coverage - current_coverage
        
        # Weight by demand
        marginal_gains = np.sum(current_demand * marginal_coverage, axis=1)
        
        # 3. SELECT BEST CANDIDATE
        best_local_idx = np.argmax(marginal_gains)
        best_global_idx = valid_indices[best_local_idx]
        
        # 4. UPDATE STATE
        selected_this_phase.append(best_global_idx)
        selected_history_coords.append((cand_coords[best_global_idx][0], cand_coords[best_global_idx][1]))
        
        # Update the global coverage array (this carries over to the next phase!)
        current_coverage = np.minimum(1.0, current_coverage + satisfaction_matrix[best_global_idx, :])
        
        print(f"  -> Selected Node {best_global_idx} | Marginal Gain: {marginal_gains[best_local_idx]:.2f}")
        
    return selected_this_phase, current_coverage, selected_history_coords