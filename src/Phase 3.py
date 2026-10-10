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

def min_max_normalize(series):
    """Scales data strictly between 0 and 1"""
    min_val = series.min()
    max_val = series.max()
    return (series - min_val) / (max_val - min_val)

# 1. Normalize Demand (Higher is better -> 0 to 1)
gdf_score_data['norm_demand'] = min_max_normalize(gdf_score_data['local_demand'])

# 2. Normalize Traffic / Betweenness (Higher is better -> 0 to 1)
# Fill NaN betweenness (from POIs) with 0 before normalizing
gdf_score_data['betweenness'] = gdf_score_data['betweenness'].fillna(0)
gdf_score_data['norm_traffic'] = min_max_normalize(gdf_score_data['betweenness'])

# 3. Normalize Grid Proximity (Closer is better, but JRC says >50m is bad)
# We will invert this: Score = 1 if dist <= 50m. Score decays to 0 if dist > 200m.
def grid_proximity_score(distance):
    if distance <= 50:
        return 1.0
    elif distance >= 200:
        return 0.0
    else:
        # Linear decay between 50m and 200m
        return 1 - ((distance - 50) / 150)

gdf_score_data['norm_grid_prox'] = gdf_score_data['dist_to_grid_m'].apply(grid_proximity_score)

print("All criteria normalized to 0-1 scale.")

# Define Weights
W1_DEMAND = 0.50
W2_TRAFFIC = 0.30
W3_GRID_PROX = 0.20

# Apply the Weighted Sum Model (Map Algebra)
gdf_score_data['Suitability_Score'] = (
    (W1_DEMAND * gdf_score_data['norm_demand']) +
    (W2_TRAFFIC * gdf_score_data['norm_traffic']) +
    (W3_GRID_PROX * gdf_score_data['norm_grid_prox'])
)

# Sort to see the best locations
gdf_score_data = gdf_score_data.sort_values(by='Suitability_Score', ascending=False)

print("Top 5 Candidate Locations for EV Charging:")
print(gdf_score_data[['name', 'candidate_source', 'Suitability_Score', 'dist_to_grid_m', 'local_demand']].head())

fig, ax = plt.subplots(figsize=(14, 10))

# Plot the base grid to show context
gdf_grid.plot(ax=ax, facecolor='none', edgecolor='lightgray', linewidth=0.2, alpha=0.5)

# Plot Vetoed Grid Zones in the background for context
vetoed_cells.plot(ax=ax, facecolor='red', alpha=0.15, label='Vetoed Grid Zones (Phase 2)')

# Plot the OSM Power Lines
gdf_power.plot(ax=ax, color='brown', linewidth=1, alpha=0.6, label='Power Distribution Lines')

# Plot the final scored candidates
# Size based on demand, Color based on final score
scatter = gdf_score_data.plot(
    ax=ax,
    markersize=gdf_score_data['norm_demand'] * 100 + 20, # Scale marker size
    column='Suitability_Score',
    cmap='RdYlGn', # Red=Low score, Green=High score
    legend=True,
    legend_kwds={'label': 'Final Suitability Score ($S_i$)', 'shrink': 0.6},
    alpha=0.85,
    zorder=5
)

# Add basemap
ctx.add_basemap(ax, crs=gdf_score_data.crs.to_string(), source=ctx.providers.CartoDB.Positron, alpha=0.4)
ax.set_title("Phase 3: Multi-Criteria Suitability Scoring for EVCS Candidates\nColombo 3, 4, 11 & 12", fontsize=14)
ax.legend(fontsize=10, loc='lower left')
ax.axis('off')

plt.savefig("Phase3_Suitability_Scoring_Map.png", dpi=300, bbox_inches='tight')
plt.show()

# Save for Phase 4!
gdf_score_data.to_file("phase3_scored_candidates.geojson", driver="GeoJSON")