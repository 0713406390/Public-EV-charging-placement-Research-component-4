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

from scipy.ndimage import convolve

def apply_wna_smoothing(gdf_grid, demand_column, grid_size=100, kernel_radius_cells=1):
    """
    Applies a distance-weighted neighborhood average to grid demand.
    kernel_radius_cells=1 means a 3x3 grid (300m x 300m area).
    """
    # 1. Convert GeoDataFrame to a 2D Numpy Array (Rasterize)
    minx, miny, maxx, maxy = gdf_grid.total_bounds
    cols = int((maxx - minx) / grid_size) + 1
    rows = int((maxy - miny) / grid_size) + 1
    
    demand_array = np.zeros((rows, cols))
    
    for idx, row in gdf_grid.iterrows():
        # Calculate array index for the grid cell
        col_idx = int((row.geometry.centroid.x - minx) / grid_size)
        row_idx = int((maxy - row.geometry.centroid.y) / grid_size) # Y is inverted in arrays
        if 0 <= row_idx < rows and 0 <= col_idx < cols:
            demand_array[row_idx, col_idx] = row[demand_column]
            
    # 2. Create the Distance-Weighted Kernel (Trinidad Equation 4 concept)
    # Center cell has distance 0, adjacent has distance 1 (representing 100m), diagonal ~1.4
    size = 2 * kernel_radius_cells + 1
    kernel = np.zeros((size, size))
    center = kernel_radius_cells
    
    for i in range(size):
        for j in range(size):
            distance_cells = np.sqrt((i - center)**2 + (j - center)**2)
            # d_jk in the formula. Using kappa=2 for distance decay
            if distance_cells == 0:
                kernel[i, j] = 1.0 
            else:
                kernel[i, j] = 1.0 / (1 + distance_cells)**2 
                
    kernel = kernel / kernel.sum() # Normalize

    # 3. Apply Convolution (Smooth the array)
    smoothed_array = convolve(demand_array, kernel, mode='constant', cval=0.0)
    
    # 4. Map the smoothed array back to the GeoDataFrame
    smoothed_demand = []
    for idx, row in gdf_grid.iterrows():
        col_idx = int((row.geometry.centroid.x - minx) / grid_size)
        row_idx = int((maxy - row.geometry.centroid.y) / grid_size)
        smoothed_demand.append(smoothed_array[row_idx, col_idx])
        
    gdf_grid['smoothed_demand'] = smoothed_demand
    return gdf_grid

gdf_grid = apply_wna_smoothing(gdf_grid_demand, 'raw_demand')
print("Applied Weighted Neighborhood Average. Demand is now spatially continuous.")

# === REPLACE THIS BLOCK WITH YOUR TEAMMATE'S DATA ===
# Simulating Component 3 Grid Risk Polygons (Substation boundaries)
# Let's create a fake "Red Zone" polygon in the middle of Pettah (Col 11)
from shapely.geometry import box
fake_red_zone = box(375000, 344500, 376000, 345000) # Random coords in Col 11 area
gdf_grid_risk = gpd.GeoDataFrame({
    'risk_zone': ['Red'],
    'geometry': [fake_red_zone]
}, crs='EPSG:32644')
# === END REPLACE BLOCK ===

# 1. Spatial Join: Which grid cells fall inside a risk zone?
gdf_final_grid = gpd.sjoin(gdf_grid, gdf_grid_risk, how='left', predicate='intersects')

# 2. Initialize Grid Feasibility to 1 (Feasible)
gdf_final_grid['grid_feasibility'] = 1

# 3. Apply the Hard Constraint (TAF Novelty #1)
# If the cell intersects an Orange or Red zone, feasibility becomes 0 (Vetoed)
mask_veto = gdf_final_grid['risk_zone'].isin(['Orange', 'Red'])
gdf_final_grid.loc[mask_veto, 'grid_feasibility'] = 0

# Optional but recommended: Also apply a small buffer penalty for 'Amber' zones 
# (Not a hard veto, but reduces the score. We will use this in Phase 3).
gdf_final_grid.loc[gdf_final_grid['risk_zone'] == 'Amber', 'grid_feasibility'] = 0.5 

print(f"Applied Grid Constraints. {len(gdf_final_grid[gdf_final_grid['grid_feasibility']==0])} cells vetoed.")

fig, ax = plt.subplots(figsize=(14, 10))

# 1. Plot the Smoothed Demand Heatmap
gdf_final_grid.plot(
    ax=ax, 
    column='smoothed_demand', 
    cmap='YlOrRd', 
    legend=True,
    legend_kwds={'label': 'Smoothed EV Charging Demand (WNA)', 'shrink': 0.6},
    alpha=0.8
)

# 2. Plot the Vetoed Grid Cells (Hard Black outlines to show constraints)
vetoed_cells = gdf_final_grid[gdf_final_grid['grid_feasibility'] == 0]
vetoed_cells.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=2, label='Grid Veto Zone (Red/Orange)')

# 3. Plot Phase 1 Candidate Nodes to show they are waiting in the wings
gdf_candidates = gpd.read_file("phase1_candidates_colombo.geojson")
gdf_candidates.plot(ax=ax, color='cyan', markersize=10, label='Phase 1 Candidates', zorder=5)

# Formatting
ctx.add_basemap(ax, crs=gdf_final_grid.crs.to_string(), source=ctx.providers.CartoDB.Positron, alpha=0.5)
ax.set_title("Phase 2 Output: Spatial Integration of Demand, Grid Constraints, & Candidates", fontsize=14)
ax.legend(fontsize=11)
ax.axis('off')

plt.savefig("Phase2_Spatial_Integration_Map.png", dpi=300, bbox_inches='tight')
plt.show()

# Save this masterpiece for Phase 3!
gdf_final_grid.to_file("phase2_integrated_grid.geojson", driver="GeoJSON")
print("Phase 2 Complete. Grid saved for Phase 3 Optimization.")