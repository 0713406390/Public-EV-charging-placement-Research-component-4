"""
config.py — Shared settings, file paths and small helpers for the whole pipeline.
Every step imports from here, so nothing is hard-coded twice.
"""

from pathlib import Path

import geopandas as gpd

# ------------------------------------------------------------------
# Folders
# ------------------------------------------------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ------------------------------------------------------------------
# Study area
# ------------------------------------------------------------------
PLACES = [
    "Colombo 03, Colombo, Sri Lanka",
    "Colombo 04, Colombo, Sri Lanka",
    "Colombo 11, Colombo, Sri Lanka",
    "Colombo 12, Colombo, Sri Lanka",
]

# ------------------------------------------------------------------
# CRS — UTM Zone 44N covers Sri Lanka (units = metres)
# ------------------------------------------------------------------
TARGET_CRS = "EPSG:32644"

# ------------------------------------------------------------------
# Network settings
# ------------------------------------------------------------------
NETWORK_TYPE = "drive"

# ------------------------------------------------------------------
# OSM tag filters
# ------------------------------------------------------------------
TAGS_POIS = {
    "amenity": ["fuel", "parking"],
    "parking": ["underground", "multi-storey"],  # prioritise structured parking
}

TAGS_WATER = {
    "natural": ["water", "wetland"],
    "waterway": ["river", "canal"],
}

# ------------------------------------------------------------------
# Analysis parameters
# ------------------------------------------------------------------
FLOOD_BUFFER_M = 50            # metres around water = flood-risk zone
CENTRALITY_PERCENTILE = 0.95   # keep nodes in the top 5% of betweenness

# ------------------------------------------------------------------
# File names (all inside ./data)
# ------------------------------------------------------------------
F_BOUNDARIES    = DATA_DIR / "study_area_boundaries.geojson"       # Step 1 out
F_STUDY_POLYGON = DATA_DIR / "study_area_boundary.geojson"         # Step 1 out
F_GRAPH         = DATA_DIR / "road_network_drive.graphml"          # Step 2 out
F_EDGES         = DATA_DIR / "road_edges.geojson"                  # Step 2 out
F_NODES         = DATA_DIR / "road_nodes.geojson"                  # Step 2 out
F_POIS          = DATA_DIR / "pois_fuel_parking.geojson"           # Step 3 out
F_WATER         = DATA_DIR / "water_bodies.geojson"                # Step 4 out
F_FLOOD         = DATA_DIR / "flood_risk_zone.geojson"             # Step 4 out
F_NODES_BC      = DATA_DIR / "road_nodes_centrality.geojson"       # Step 5 out
F_CANDIDATES    = DATA_DIR / "phase1_candidates_colombo.geojson"   # Step 6 out
F_MAP           = DATA_DIR / "Phase1_Candidate_Nodes_Map.png"      # Step 7 out


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def dissolve_geometry(geoms):
    """Union a GeoDataFrame/GeoSeries into one shape (version-safe)."""
    if hasattr(geoms, "geometry"):        # GeoDataFrame -> GeoSeries
        geoms = geoms.geometry
    try:
        return geoms.union_all()          # geopandas >= 1.0
    except AttributeError:
        return geoms.unary_union          # older geopandas


def load_study_polygon():
    """Read the dissolved study-area polygon saved by Step 1."""
    gdf = gpd.read_file(F_STUDY_POLYGON)
    return dissolve_geometry(gdf)

    # ==================================================================
# PHASE 2 settings
# ==================================================================
GRID_SIZE_M       = 100   # fishnet cell size (metres)
WNA_KERNEL_RADIUS = 1     # 1 -> 3x3 kernel (300m x 300m neighbourhood)
WNA_KAPPA         = 2.0   # distance-decay strength (Trinidad Eq. 4)

# Placeholder simulation — used ONLY if the real teammate files are absent
N_SIM_DEMAND_POINTS = 5000

# Risk severity -> feasibility multiplier (the hard constraint)
RISK_SEVERITY = {"Red": 0.0, "Orange": 0.0, "Amber": 0.5}

# ------------------------------------------------------------------
# DROP-IN FILES: if these exist, the pipeline uses them automatically
# instead of the simulations. No code changes needed.
# ------------------------------------------------------------------
F_DEMAND_REAL = DATA_DIR / "demand_points_real.geojson"    # needs 'ev_demand' column
F_RISK_REAL   = DATA_DIR / "grid_risk_zones_real.geojson"  # needs 'risk_zone' column (Red/Orange/Amber)

# Step outputs
F_GRID_CELLS  = DATA_DIR / "phase2_grid_cells.geojson"           # Step 8 out
F_DEMAND_PTS  = DATA_DIR / "phase2_demand_points.geojson"        # Step 9 out
F_GRID_RAW    = DATA_DIR / "phase2_grid_raw_demand.geojson"      # Step 10 out
F_GRID_SMOOTH = DATA_DIR / "phase2_grid_smoothed_demand.geojson" # Step 11 out
F_RISK_ZONES  = DATA_DIR / "phase2_grid_risk_zones.geojson"      # Step 12 out
F_GRID_FINAL  = DATA_DIR / "phase2_integrated_grid.geojson"      # Step 13 out
F_MAP_P2      = DATA_DIR / "Phase2_Spatial_Integration_Map.png"  # Step 14 out

# ==================================================================
# PHASE 2.5 — LANDSLIDE HAZARD (multi-hazard extension)
# ==================================================================
# Same veto mechanism as grid risk: worst case wins
LANDSLIDE_FEASIBILITY = {"High": 0.0, "Moderate": 0.5, "Low": 1.0}

# Drop-in files (checked in priority order by Step 12b)
F_LANDSLIDE_REAL      = DATA_DIR / "landslide_hazard_zones_real.geojson"  # polygons + 'susceptibility'
F_LANDSLIDE_INVENTORY = DATA_DIR / "landslide_inventory_real.csv"         # points w/ lon/lat (NASA GLC, DesInventar)

# Historic-event buffer -> suspect zone radius
LANDSLIDE_BUFFER_M = 200

# DEM slope-proxy classification (degrees; only used if no drop-in file exists)
SLOPE_HIGH_DEG     = 15.0
SLOPE_MODERATE_DEG = 8.0

# Step 12b outputs
F_LANDSLIDE_ZONES = DATA_DIR / "landslide_hazard_zones.geojson"
F_SLOPE_RASTER    = DATA_DIR / "landslide_slope_degrees.tif"   # appendix figure material


# ==================================================================
# PHASE 3 settings
# ==================================================================
TAGS_POWER = {"power": "line"}   # OSM power distribution lines

# Grid-proximity scoring (JRC guidance: <=50 m ideal, >=200 m worthless)
GRID_PROX_FULL_M = 50
GRID_PROX_ZERO_M = 200

# Multi-criteria weights (weighted-sum model — keep the sum = 1.0)
W_DEMAND    = 0.50
W_TRAFFIC   = 0.30
W_GRID_PROX = 0.20


def sanitize_for_geojson(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """GeoJSON cannot store list/dict values -> stringify such columns."""
    gdf = gdf.copy()
    for col in gdf.columns:
        if col != "geometry" and gdf[col].map(
            lambda v: isinstance(v, (list, tuple, dict))
        ).any():
            gdf[col] = gdf[col].astype(str)
    return gdf


# ------------------------------------------------------------------
# File names (all inside ./data)
# ------------------------------------------------------------------
F_POWER       = DATA_DIR / "phase3_power_lines.geojson"              # Step 15 out
F_SURVIVORS   = DATA_DIR / "phase3_surviving_candidates.geojson"     # Step 16 out
F_POWER_DIST  = DATA_DIR / "phase3_candidates_power_dist.geojson"    # Step 17 out
F_WITH_DEMAND = DATA_DIR / "phase3_candidates_with_demand.geojson"   # Step 18 out
F_SCORED      = DATA_DIR / "phase3_scored_candidates.geojson"        # Step 19 out
F_MAP_P3      = DATA_DIR / "Phase3_Suitability_Scoring_Map.png"      # Step 20 out

# ==================================================================
# PHASE 4 settings (STATEFUL phased greedy set-cover optimization)
# ==================================================================
DT_M = 1000.0                 # service threshold (m): beyond this, satisfaction = 0
THETA = 0.003                 # distance decay: satisfaction = exp(-theta * d)
MIN_STATION_SPACING_M = 500   # hard minimum distance between ANY two stations
                              # (enforced against ALL phases — strict stateful rule)

# Deployment schedule: K = number of NEW stations, demand_mult = demand growth
PHASES = {
    "Phase_1_2027": {"K": 5,  "demand_mult": 1.0},   # early adoption
    "Phase_2_2030": {"K": 10, "demand_mult": 2.2},   # growth spike
    "Phase_3_2035": {"K": 15, "demand_mult": 4.5},   # maturity
}

# Charger capacity per phase (Component 2 logic)
CAPACITY_MAP = {
    "Phase_1_2027": "22kW AC / 50kW DC",
    "Phase_2_2030": "150kW DC Fast",
    "Phase_3_2035": "150kW+ DC Ultra-Fast",
}

# Map styling per phase (colour / marker / size grow with the phase)
PHASE_STYLES = {
    "Phase_1_2027": {"color": "#2ca02c", "marker": "o", "size": 200},  # circles
    "Phase_2_2030": {"color": "#ff7f0e", "marker": "s", "size": 250},  # squares
    "Phase_3_2035": {"color": "#d62728", "marker": "^", "size": 300},  # triangles
}

# ------------------------------------------------------------------
# File names (all inside ./data)
# ------------------------------------------------------------------
F_DIST_MATRIX = DATA_DIR / "phase4_distance_matrix.npz"            # Step 21 out
F_SELECTION   = DATA_DIR / "phase4_station_selection.csv"          # Step 22 out
F_METRICS     = DATA_DIR / "phase4_deployment_metrics.csv"         # Step 22 out
F_FINAL_PLAN  = DATA_DIR / "FINAL_Phased_EV_Plan_Colombo.geojson"  # Step 23 out
F_MAP_P4      = DATA_DIR / "FINAL_Thesis_Evolution_Map.png"        # Step 24 out