"""
STEP 8 — Create the fishnet grid (100 m x 100 m) over the study area.

Reads:  data/study_area_boundary.geojson  (Phase 1, Step 1 — no re-download!)
Saves:  data/phase2_grid_cells.geojson
        Each cell carries grid_id, row_idx, col_idx — the raster indices are
        baked in HERE so the WNA step never needs fragile centroid math.

Run:  python step8_fishnet_grid.py [--force]
"""

import argparse

import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon

from config import GRID_SIZE_M, TARGET_CRS, F_GRID_CELLS, load_study_polygon


def create_fishnet(gdf_boundary: gpd.GeoDataFrame, grid_size_m: int) -> gpd.GeoDataFrame:
    """Fishnet grid over the boundary, clipped to it, with raster indices."""
    minx, miny, maxx, maxy = gdf_boundary.total_bounds

    x_coords = np.arange(minx, maxx, grid_size_m)
    y_coords = np.arange(miny, maxy, grid_size_m)

    polygons, row_idx, col_idx = [], [], []
    for j, y in enumerate(y_coords):        # j = row index (from bottom)
        for i, x in enumerate(x_coords):    # i = column index (from left)
            polygons.append(Polygon([
                (x, y), (x + grid_size_m, y),
                (x + grid_size_m, y + grid_size_m), (x, y + grid_size_m),
            ]))
            row_idx.append(j)
            col_idx.append(i)

    grid = gpd.GeoDataFrame(
        {"row_idx": row_idx, "col_idx": col_idx},
        geometry=polygons,
        crs=gdf_boundary.crs,
    )

    # Clip to the actual study area (removes ocean / outer areas)
    grid = gpd.clip(grid, gdf_boundary).reset_index(drop=True)
    grid["grid_id"] = range(len(grid))
    return grid


def main(force: bool = False) -> None:
    if F_GRID_CELLS.exists() and not force:
        print(f"[skip] Grid already cached -> {F_GRID_CELLS}")
        return

    print("Building the fishnet grid...")
    gdf_boundary = gpd.GeoDataFrame(geometry=[load_study_polygon()], crs=TARGET_CRS)
    gdf_grid = create_fishnet(gdf_boundary, GRID_SIZE_M)

    gdf_grid.to_file(F_GRID_CELLS, driver="GeoJSON")
    print(f"[done] Created {len(gdf_grid)} grid cells ({GRID_SIZE_M}x{GRID_SIZE_M} m).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 8: fishnet grid")
    parser.add_argument("--force", action="store_true", help="rebuild even if cached")
    main(parser.parse_args().force)