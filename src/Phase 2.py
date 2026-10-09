import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
import contextily as ctx

# Load the study area boundary you saved from Phase 1
# (If you didn't save it, re-run the boundary code from Phase 1 Step 1)
gdf_boundaries = gpd.read_file("phase1_candidates_colombo.geojson") # Temporary workaround, see note below
# NOTE: It is better to save your boundary as a separate file in Phase 1. 
# For now, we will recreate the boundary quickly:
places = ["Colombo 03, Colombo, Sri Lanka", "Colombo 04, Colombo, Sri Lanka", 
          "Colombo 11, Colombo, Sri Lanka", "Colombo 12, Colombo, Sri Lanka"]
gdf_boundary = ox.geocode_to_gdf(places).unary_union
gdf_boundary = gpd.GeoDataFrame(geometry=[gdf_boundary], crs='EPSG:4326')
gdf_boundary = gdf_boundary.to_crs('EPSG:32644') # Project to UTM (meters)

def create_fishnet(gdf_boundary, grid_size_meters=100):
    """Creates a fishnet grid over a boundary."""
    minx, miny, maxx, maxy = gdf_boundary.total_bounds
    
    # Generate grid coordinates
    x_coords = np.arange(minx, maxx, grid_size_meters)
    y_coords = np.arange(miny, maxy, grid_size_meters)
    
    polygons = []
    for x in x_coords:
        for y in y_coords:
            poly = Polygon([(x, y), (x + grid_size_meters, y), 
                            (x + grid_size_meters, y + grid_size_meters), (x, y + grid_size_meters)])
            polygons.append(poly)
            
    grid = gpd.GeoDataFrame(geometry=polygons, crs=gdf_boundary.crs)
    
    # Clip the grid to the actual study area boundary (removes ocean/outer areas)
    grid_clipped = gpd.clip(grid, gdf_boundary)
    grid_clipped['grid_id'] = range(len(grid_clipped))
    
    return grid_clipped

gdf_grid = create_fishnet(gdf_boundary, 100)
print(f"Created {len(gdf_grid)} grid cells (100x100m) over the study area.")

from shapely.geometry import Point

# === REPLACE THIS BLOCK WITH YOUR TEAMMATE'S DATA ===
# Simulating dasymetric demand points (e.g., 5000 EVs distributed across the area)
np.random.seed(42)
minx, miny, maxx, maxy = gdf_boundary.total_bounds
random_x = np.random.uniform(minx, maxx, 5000)
random_y = np.random.uniform(miny, maxy, 5000)
gdf_demand_points = gpd.GeoDataFrame(
    geometry=[Point(x, y) for x, y in zip(random_x, random_y)],
    crs='EPSG:32644'
)
# Add a fake demand weight (e.g., some cars charge more than others based on Component 2)
gdf_demand_points['ev_demand'] = np.random.randint(1, 5, len(gdf_demand_points))
# === END REPLACE BLOCK ===

# Spatial Join: Assign demand points to the 100x100m grid cells
gdf_grid_demand = gpd.sjoin(gdf_grid, gdf_demand_points, how='left', predicate='contains')

# Aggregate to get total raw demand per grid cell
gdf_grid_demand = gdf_grid_demand.groupby('grid_id').agg({
    'geometry': 'first',
    'ev_demand': 'sum'
}).reset_index()

# Fill NaNs (cells with zero demand) with 0
gdf_grid_demand['raw_demand'] = gdf_grid_demand['ev_demand'].fillna(0)

print("Raw demand mapped to grid cells.")