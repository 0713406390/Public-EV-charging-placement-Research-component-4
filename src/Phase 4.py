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