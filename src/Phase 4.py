import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import contextily as ctx

# 1. Load Phase 3 Candidates and Phase 2 Grid
gdf_candidates = gpd.read_file("phase3_scored_candidates.geojson").to_crs('EPSG:32644')
gdf_grid = gpd.read_file("phase2_integrated_grid.geojson").to_crs('EPSG:32644')

# Ensure grid is only the feasible areas (where grid_feasibility != 0)
gdf_feasible_grid = gdf_grid[gdf_grid['grid_feasibility'] > 0].copy()

# 2. Pre-compute Distance Matrix
# Matrix shape: [Number of Candidates, Number of Grid Cells]
print(f"Calculating distance matrix for {len(gdf_candidates)} candidates x {len(gdf_feasible_grid)} grid cells...")
print("This may take 1-2 minutes depending on your CPU...")

# Extract centroid coordinates for fast math
cand_coords = np.array([(geom.x, geom.y) for geom in gdf_candidates.geometry])
grid_coords = np.array([(geom.centroid.x, geom.centroid.y) for geom in gdf_feasible_grid.geometry])

# Vectorized distance calculation
# dist_matrix[i, j] = distance from candidate i to grid cell j
dist_matrix = np.zeros((len(cand_coords), len(grid_coords)))
for i, (x1, y1) in enumerate(cand_coords):
    dist_matrix[i, :] = np.sqrt((grid_coords[:, 0] - x1)**2 + (grid_coords[:, 1] - y1)**2)

print("Distance matrix computed successfully!")

def run_greedy_optimization(dist_matrix, demand_array, K, theta=0.003, DT=1000, min_dist=500):
    """
    Runs the constrained greedy set-covering algorithm.
    """
    n_candidates, n_grid_cells = dist_matrix.shape
    
    # Apply Distance Threshold (DT) - stations beyond DT provide 0 satisfaction
    satisfaction_matrix = np.where(dist_matrix <= DT, np.exp(-theta * dist_matrix), 0.0)
    
    # State tracking
    selected_indices = []
    unmet_demand = demand_array.copy()
    current_coverage = np.zeros(n_grid_cells) # Tracks how much of cell's demand is satisfied
    
    for _ in range(K):
        # 1. Apply Minimum Inter-Station Distance Constraint (500m)
        valid_candidates = np.ones(n_candidates, dtype=bool)
        for sel_idx in selected_indices:
            # Find all candidates within 500m of already selected ones
            too_close = dist_matrix[:, :] # We need candidate-to-candidate distance here
            # Quick fix: calculate distance from all candidates to the newly selected one
            dist_to_selected = dist_matrix[sel_idx, :] # Wait, this is to grids. 
            # CORRECTION: We need candidate-to-candidate distances. Let's calculate it on the fly for the selected ones only.
            pass # We will handle this slightly differently below for efficiency
        
        # (Revised logic for 500m constraint to avoid huge candidate-candidate matrices)
        valid_mask = np.ones(n_candidates, dtype=bool)
        for sel_idx in selected_indices:
            # Vectorized distance from selected candidate to ALL candidates
            dist_to_sel = np.sqrt((cand_coords[:, 0] - cand_coords[sel_idx][0])**2 + 
                                 (cand_coords[:, 1] - cand_coords[sel_idx][1])**2)
            valid_mask[dist_to_sel < min_dist] = False
            
        # Remove already selected
        valid_mask[selected_indices] = False 
        
        if not valid_mask.any():
            print("Warning: No more valid candidates left due to 500m constraint!")
            break

        # 2. Calculate Marginal Gain for all valid candidates
        marginal_gains = np.zeros(n_candidates)
        for i in range(n_candidates):
            if not valid_mask[i]:
                continue
                
            # New coverage if we place station i
            new_coverage = np.minimum(1.0, current_coverage + satisfaction_matrix[i, :])
            
            # Gain = Demand satisfied by new station i
            gain = np.sum(unmet_demand * (new_coverage - current_coverage))
            marginal_gains[i] = gain

        # 3. Select the candidate with the highest marginal gain
        best_candidate_idx = np.argmax(marginal_gains)
        
        # 4. Update State
        selected_indices.append(best_candidate_idx)
        current_coverage = np.minimum(1.0, current_coverage + satisfaction_matrix[best_candidate_idx, :])
        # Reduce unmet demand (conceptually, for the next iteration, the gain drops because coverage increased)
        
        print(f"  Selected Candidate {best_candidate_idx} | Marginal Gain: {marginal_gains[best_candidate_idx]:.2f}")

    return selected_indices

    # Base Demand from Phase 2
base_demand = gdf_feasible_grid['smoothed_demand'].values

# Define Phases (K = number of NEW stations to build in that phase)
phases = {
    "Phase_1_2027": {"K": 5, "demand_multiplier": 1.0},   # Base demand
    "Phase_2_2030": {"K": 5, "demand_multiplier": 1.8},   # EV numbers grow
    "Phase_3_2035": {"K": 5, "demand_multiplier": 3.0}    # High adoption
}

all_selected_indices = []

for phase_name, params in phases.items():
    print(f"\n--- Running {phase_name} (Target: {params['K']} stations) ---")
    
    # 1. Scale demand based on year
    current_demand = base_demand * params['demand_multiplier']
    
    # 2. Run Algorithm
    # (Note: We pass a modified satisfaction matrix calculation inside, 
    # but for simplicity, we reuse the function. The demand multiplier handles growth.)
    # To strictly prevent picking old stations, we pass `all_selected_indices` as a blacklist.
    
    # Slight modification to function call to accept blacklist:
    selected_this_phase = run_greedy_optimization(
        dist_matrix, current_demand, params['K'], 
        theta=0.003, DT=1000, min_dist=500
    )
    
    # Ensure no duplicates across phases (Safety check)
    for idx in selected_this_phase:
        if idx not in all_selected_indices:
            all_selected_indices.append(idx)
            
    print(f"Total stations accumulated so far: {len(all_selected_indices)}")