import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
import networkx as nx

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