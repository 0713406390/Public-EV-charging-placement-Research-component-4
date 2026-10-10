import geopandas as gpd
import pandas as pd
import numpy as np
import osmnx as ox
import matplotlib.pyplot as plt
import contextily as ctx
from shapely.geometry import Point

# 1. Load outputs from Phase 1 and Phase 2
gdf_candidates = gpd.read_file("phase1_candidates_colombo.geojson")
gdf_grid = gpd.read_file("phase2_integrated_grid.geojson")

# Ensure both are in the same CRS (UTM Zone 44N for Sri Lanka)
gdf_candidates = gdf_candidates.to_crs('EPSG:32644')
gdf_grid = gpd_grid.to_crs('EPSG:32644')

# 2. APPLY THE GRID VETO (Novelty #1 Enforcement)
# Identify which grid cells were vetoed (feasibility == 0)
vetoed_cells = gdf_grid[gdf_grid['grid_feasibility'] == 0]

# Check if any candidates fall inside these vetoed grid cells
candidates_in_veto_zone = gpd.sjoin(gdf_candidates, vetoed_cells, how='inner', predicate='intersects')
vetoed_candidate_ids = candidates_in_veto_zone.index.unique()

# Remove them from the candidate list
gdf_survivors = gdf_candidates[~gdf_candidates.index.isin(vetoed_candidate_ids)].copy()

print(f"Started with {len(gdf_candidates)} candidates.")
print(f"Vetoed {len(vetoed_candidate_ids)} candidates due to Red/Orange Grid Risk.")
print(f"Proceeding to score {len(gdf_survivors)} surviving candidates.")