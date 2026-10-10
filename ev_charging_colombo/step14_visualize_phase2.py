"""
STEP 14 — Phase 2 map: demand heatmap + vetoed cells + Phase 1 candidates.
          (Only the basemap tiles need internet.)

Reads:  data/phase2_integrated_grid.geojson    (Step 13)
        data/phase1_candidates_colombo.geojson (Phase 1, Step 6)
Saves:  data/Phase2_Spatial_Integration_Map.png

Run:  python step14_visualize_phase2.py [--force]
"""

import argparse

import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx

from config import F_GRID_FINAL, F_CANDIDATES, F_MAP_P2


def main(force: bool = False) -> None:
    if F_MAP_P2.exists() and not force:
        print(f"[skip] Phase 2 map already cached -> {F_MAP_P2}")
        return

    gdf_grid = gpd.read_file(F_GRID_FINAL)
    gdf_candidates = gpd.read_file(F_CANDIDATES)

    fig, ax = plt.subplots(figsize=(14, 10))

    # 1. Smoothed demand heatmap
    gdf_grid.plot(
        ax=ax, column="smoothed_demand", cmap="YlOrRd", legend=True,
        legend_kwds={"label": "Smoothed EV Charging Demand (WNA)", "shrink": 0.6},
        alpha=0.8,
    )

    # 2. Vetoed cells (hard black outline)
    vetoed = gdf_grid[gdf_grid["grid_feasibility"] == 0.0]
    if len(vetoed):
        vetoed.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=2,
                    label="Grid Veto Zone (Red/Orange)")

    # 2b. Amber cells (soft penalty — dashed outline)
    amber = gdf_grid[gdf_grid["grid_feasibility"] == 0.5]
    if len(amber):
        amber.plot(ax=ax, facecolor="none", edgecolor="orange", linewidth=1.5,
                   linestyle="--", label="Amber Zone (penalised, not vetoed)")

    # 3. Phase 1 candidate nodes waiting in the wings
    gdf_candidates.plot(ax=ax, color="cyan", markersize=10,
                        label="Phase 1 Candidates", zorder=5)

    # 4. Basemap for context
    ctx.add_basemap(ax, crs=gdf_grid.crs.to_string(),
                    source=ctx.providers.CartoDB.Positron, alpha=0.5)

    ax.set_title("Phase 2 Output: Spatial Integration of Demand, "
                 "Grid Constraints, & Candidates", fontsize=14)
    ax.legend(fontsize=11)
    ax.axis("off")

    plt.savefig(F_MAP_P2, dpi=300, bbox_inches="tight")
    plt.show()
    print(f"[done] Map saved -> {F_MAP_P2}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 14: Phase 2 map")
    parser.add_argument("--force", action="store_true", help="re-render even if cached")
    main(parser.parse_args().force)