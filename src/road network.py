import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

# Define the specific areas for your study
# OSMnx uses these names to fetch boundaries
places = [
    "Colombo 03, Colombo, Sri Lanka",
    "Colombo 04, Colombo, Sri Lanka",
    "Colombo 11, Colombo, Sri Lanka",
    "Colombo 12, Colombo, Sri Lanka"
]

print("Fetching administrative boundaries...")
# Get the boundary polygons
gdf_boundaries = ox.geocode_to_gdf(places)
# Combine them into one single boundary polygon for the whole study area
study_area_boundary = gdf_boundaries.unary_union

print("Downloading drivable street network...")
# Download the road network within this boundary
# 'drive' gets only roads meant for cars
G = ox.graph_from_polygon(study_area_boundary, network_type='drive')

# Project the graph to a local CRS (meters) for accurate distance calculations later
# This projects to UTM zone 44N, which covers Sri Lanka
G_proj = ox.project_graph(G, to_crs='EPSG:32644')

# Convert graph nodes and edges to GeoDataFrames for easy mapping
gdf_nodes, gdf_edges = ox.graph_to_gdfs(G_proj)

print(f"Success! Extracted {len(gdf_nodes)} intersections and {len(gdf_edges)} road segments.")

# Tags for what we want to extract from OSM
tags_pois = {
    'amenity': ['fuel', 'parking'],
    'parking': ['underground', 'multi-storey'] # Prioritize structured parking
}

print("Extracting Fuel Stations and Parking lots...")
# This fetches POIs within our study area boundary
gdf_pois = ox.features_from_polygon(study_area_boundary, tags=tags_pois)

# Clean the POI data (keep only points, drop relation polygons for simplicity)
gdf_pois = gdf_pois[gdf_pois.geometry.type == 'Point']

# Project POIs to the same CRS as the road network
gdf_pois = gdf_pois.to_crs('EPSG:32644')

# Extract names if available
gdf_pois['name'] = gdf_pois['name'].fillna('Unknown POI')
gdf_pois['poi_type'] = gdf_pois['amenity']

print(f"Found {len(gdf_pois)} potential POI candidates (Fuel/Parking).")

from shapely.geometry import Point
import numpy as np


print("Extracting water bodies (rivers, canals) for flood risk proxy...")
tags_water = {'natural': ['water', 'wetland'], 'waterway': ['river', 'canal']}
gdf_water = ox.features_from_polygon(study_area_boundary, tags=tags_water)

# Keep only polygons and linestrings
gdf_water = gdf_water[gdf_water.geometry.type.isin(['Polygon', 'MultiPolygon', 'LineString'])]
gdf_water = gdf_water.to_crs('EPSG:32644')

# Create a buffer of 50 meters around water bodies to represent "High Flood Risk Zones"
# (In Colombo, canals like St. Sebastian Canal flood heavily into adjacent streets)
flood_buffer_distance = 50 
gdf_flood_risk = gdf_water.buffer(flood_buffer_distance).unary_union
gdf_flood_risk = gpd.GeoDataFrame(geometry=[gdf_flood_risk], crs='EPSG:32644', columns=['flood_zone'])

print("Flood risk exclusion zone created (50m buffer from water bodies).")

print("Calculating Betweenness Centrality... (This may take 1-2 minutes)")

# Calculate betweenness centrality on the projected graph
# We normalize by edge count to make scores comparable
bc = nx.betweenness_centrality(G_proj, normalized=True, weight='length')

# Add these scores back to our nodes GeoDataFrame
gdf_nodes['betweenness'] = gdf_nodes.index.map(bc)

# Identify the top 5% of nodes by traffic importance
top_5_percent_threshold = gdf_nodes['betweenness'].quantile(0.95)

# Create a new GeoDataFrame for these high-traffic candidate nodes
gdf_traffic_candidates = gdf_nodes[gdf_nodes['betweenness'] >= top_5_percent_threshold].copy()
gdf_traffic_candidates['candidate_source'] = 'Traffic_Centrality'

print(f"Identified {len(gdf_traffic_candidates)} high-traffic intersection candidates.")


# 1. Merge the two candidate sources
# We convert POIs to the same column structure for merging
gdf_pois_candidates = gdf_pois[['geometry', 'name', 'poi_type']].copy()
gdf_pois_candidates = gdf_pois_candidates.rename(columns={'poi_type': 'candidate_source'})
gdf_pois_candidates['betweenness'] = np.nan # POIs don't have a centrality score yet

# Combine both GeoDataFrames
gdf_all_candidates = gpd.GeoDataFrame(
    pd.concat([gdf_traffic_candidates, gdf_pois_candidates], ignore_index=True),
    crs='EPSG:32644'
)

print(f"Total combined candidates before filtering: {len(gdf_all_candidates)}")

# 2. Apply Flood Exclusion (The Hard Constraint)
# We use a spatial join to see which candidates fall INSIDE the flood risk polygon
candidates_in_flood = gpd.sjoin(gdf_all_candidates, gdf_flood_risk, how='inner', predicate='intersects')

# Get the IDs of candidates that are in the flood zone
flood_victim_ids = candidates_in_flood.index.unique()

# Filter them OUT
gdf_final_phase1_candidates = gdf_all_candidates[~gdf_all_candidates.index.isin(flood_victim_ids)]

print(f"Total SAFE candidates after flood exclusion: {len(gdf_final_phase1_candidates)}")
print(f"Removed {len(flood_victim_ids)} candidates due to high flood risk.")

import contextily as ctx

fig, ax = plt.subplots(figsize=(12, 12))

# 1. Plot the base road network
gdf_edges.plot(ax=ax, linewidth=0.5, color='gray', alpha=0.5)

# 2. Plot the Flood Risk Zones (In Red/Transparent)
gdf_flood_risk.plot(ax=ax, color='red', alpha=0.2, label='High Flood Risk Zone (50m buffer)')

# 3. Plot the FINAL SAFE Candidates
# Color them by source type
traffic_nodes = gdf_final_phase1_candidates[gdf_final_phase1_candidates['candidate_source'] == 'Traffic_Centrality']
poi_nodes = gdf_final_phase1_candidates[gdf_final_phase1_candidates['candidate_source'] != 'Traffic_Centrality']

traffic_nodes.plot(ax=ax, color='blue', markersize=15, label='High-Traffic Intersections (Novelty)', zorder=5)
poi_nodes.plot(ax=ax, color='green', markersize=30, marker='s', label='Existing Fuel/Parking', zorder=5)

# 4. Add basemap for context (requires internet)
ctx.add_basemap(ax, crs=gdf_edges.crs.to_string(), source=ctx.providers.CartoDB.Positron)

# Formatting
ax.set_title("Phase 1: EV Charging Candidate Nodes\nColombo 3, 4, 11 & 12 (Flood Exclusion Applied)", fontsize=16)
ax.legend(fontsize=12)
ax.axis('off')

plt.savefig("Phase1_Candidate_Nodes_Map.png", dpi=300, bbox_inches='tight')
plt.show()

# Export to GeoJSON for Phase 2!
gdf_final_phase1_candidates.to_file("phase1_candidates_colombo.geojson", driver="GeoJSON")
print("Saved map and GeoJSON successfully!")