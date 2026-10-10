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

print("Downloading power line infrastructure from OpenStreetMap...")
# Recreate boundary for OSMnx query
places = ["Colombo 03, Colombo, Sri Lanka", "Colombo 04, Colombo, Sri Lanka", 
          "Colombo 11, Colombo, Sri Lanka", "Colombo 12, Colombo, Sri Lanka"]
boundary = ox.geocode_to_gdf(places).unary_union

# Get power lines ('power' == 'line' represents medium/low voltage distribution)
gdf_power = ox.features_from_polygon(boundary, tags={'power': 'line'})
# Keep only linestrings, project to meters
gdf_power = gdf_power[gdf_power.geometry.type.isin(['LineString', 'MultiLineString'])]
gdf_power = gdf_power.to_crs('EPSG:32644')

# Unify all power lines into one giant geometry for fast distance calculation
power_lines_union = gdf_power.unary_union

# Calculate distance from every surviving candidate to the nearest power line
# .distance() in GeoPandas automatically calculates minimum distance to a complex geometry
gdf_survivors['dist_to_grid_m'] = gdf_survivors.geometry.apply(
    lambda x: x.distance(power_lines_union)
)

print(f"Power proximity calculated. Min dist: {gdf_survivors['dist_to_grid_m'].min():.1f}m | Max dist: {gdf_survivors['dist_to_grid_m'].max():.1f}m")

# Spatial Join: Points (candidates) inside Polygons (grid cells)
gdf_score_data = gpd.sjoin(gdf_survivors, gdf_grid[['grid_id', 'smoothed_demand', 'geometry']], 
                           how='left', predicate='intersects')

# Drop duplicate columns created by the join
gdf_score_data = gdf_score_data.drop(columns=['geometry_right'])
gdf_score_data = gdf_score_data.rename(columns={'smoothed_demand': 'local_demand'})

# Fill any NaNs (if a point somehow fell just outside a grid cell) with 0
gdf_score_data['local_demand'] = gdf_score_data['local_demand'].fillna(0)