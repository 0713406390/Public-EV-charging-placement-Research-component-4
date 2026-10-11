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

    # Pre-calculate the satisfaction matrix once (Saves massive computation time)
# Using theta=0.003 and DT=1000m as established
theta = 0.003
DT = 1000
satisfaction_matrix = np.where(dist_matrix <= DT, np.exp(-theta * dist_matrix), 0.0)

# Global State Variables
base_demand = gdf_feasible_grid['smoothed_demand'].values
current_coverage = np.zeros(len(base_demand)) # Starts at zero
selected_history_coords = [] # Tracks (x,y) of ALL placed stations for 500m check

# Define the Phases based on your TAF
phases_config = {
    "Phase_1_2027": {"K": 5, "demand_mult": 1.0},   # Early adoption
    "Phase_2_2030": {"K": 10, "demand_mult": 2.2},  # Growth spike
    "Phase_3_2035": {"K": 15, "demand_mult": 4.5}   # Maturity
}

all_phases_results = {}

for phase_name, config in phases_config.items():
    print(f"\n{'='*40}")
    print(f"RUNNING {phase_name} | Target: {config['K']} NEW stations")
    print(f"{'='*40}")
    
    # Scale demand for this specific year
    phase_demand = base_demand * config['demand_mult']
    
    # Run the stateful algorithm
    selected_indices, current_coverage, selected_history_coords = run_stateful_phase(
        dist_matrix, satisfaction_matrix, phase_demand, current_coverage,
        config['K'], min_dist=500, selected_history_coords=selected_history_coords
    )
    
    # Store results
    all_phases_results[phase_name] = selected_indices
    print(f"Total stations in network now: {len(selected_history_coords)}")

    # Flatten the results into a single list of indices with their phase labels
final_indices = []
final_phases = []

for phase_name, indices in all_phases_results.items():
    final_indices.extend(indices)
    final_phases.extend([phase_name] * len(indices))

# Extract these from the original candidates GeoDataFrame
gdf_final_plan = gdf_candidates.iloc[final_indices].copy()
gdf_final_plan['Deployment_Phase'] = final_phases

# Assign Charger Types based on Phase (Logical assumption for thesis)
# Phase 1: AC slow/medium (workplaces/malls in Col 3/4)
# Phase 2: DC Fast (commercial vans in Col 11)
# Phase 3: Ultra-Fast / High-density DC
capacity_mapping = {
    "Phase_1_2027": "22kW AC / 50kW DC",
    "Phase_2_2030": "150kW DC Fast",
    "Phase_3_2035": "150kW+ DC Ultra-Fast"
}
gdf_final_plan['Recommended_Capacity'] = gdf_final_plan['Deployment_Phase'].map(capacity_mapping)

# Save the ultimate output
gdf_final_plan.to_file("FINAL_Phased_EV_Plan_Colombo.geojson", driver="GeoJSON")
print("\nSuccess! Final phased plan exported.")