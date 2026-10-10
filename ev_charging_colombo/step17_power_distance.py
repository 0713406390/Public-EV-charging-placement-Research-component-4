"""
STEP 17 — Distance from every surviving candidate to the nearest power line.

Reads:  data/phase3_surviving_candidates.geojson (Step 16)
        data/phase3_power_lines.geojson          (Step 15)
Saves:  data/phase3_candidates_power_dist.geojson (adds 'dist_to_grid_m')

Run:  python step17_power_distance.py [--force]
"""

import argparse

import geopandas as gpd

from config import F_SURVIVORS, F_POWER, F_POWER_DIST, dissolve_geometry


def main(force: bool = False) -> None:
    if F_POWER_DIST.exists() and not force:
        print(f"[skip] Power-distance data already cached -> {F_POWER_DIST}")
        return

    gdf = gpd.read_file(F_SURVIVORS)
    gdf_power = gpd.read_file(F_POWER)

    # Unify all lines into ONE geometry -> one distance op per candidate
    power_union = dissolve_geometry(gdf_power)

    # Vectorised (much faster than .apply with shapely 2)
    gdf["dist_to_grid_m"] = gdf.geometry.distance(power_union)

    gdf.to_file(F_POWER_DIST, driver="GeoJSON")
    print(f"[done] Power proximity calculated. "
          f"Min: {gdf['dist_to_grid_m'].min():.1f} m | "
          f"Max: {gdf['dist_to_grid_m'].max():.1f} m")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 17: distance to power lines")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)