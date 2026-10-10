"""
STEP 20 — Phase 3 map: suitability scores over grid + power lines context.
          (Only the basemap tiles need internet.)

Reads:  data/phase3_scored_candidates.geojson (Step 19)
        data/phase2_integrated_grid.geojson   (Phase 2, Step 13)
        data/phase3_power_lines.geojson       (Step 15)
Saves:  data/Phase3_Suitability_Scoring_Map.png

Run:  python step20_visualize_phase3.py [--force]
"""

import argparse

import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx

from config import F_SCORED, F_GRID_FINAL, F_POWER, F_MAP_P3


def main(force: bool = False) -> None:
    if F_MAP_P3.exists() and not force:
        print(f"[skip] Phase 3 map already cached -> {F_MAP_P3}")
        return

    gdf_scored = gpd.read_file(F_SCORED)
    gdf_grid = gpd.read_file(F_GRID_FINAL)
    gdf_power = gpd.read_file(F_POWER)
    vetoed_cells = gdf_grid[gdf_grid["grid_feasibility"] == 0.0]

    fig, ax = plt.subplots(figsize=(14, 10))

    # 1. Base grid for context
    gdf_grid.plot(ax=ax, facecolor="none", edgecolor="lightgray",
                  linewidth=0.2, alpha=0.5)

    # 2. Vetoed grid zones in the background
    if len(vetoed_cells):
        vetoed_cells.plot(ax=ax, facecolor="red", alpha=0.15,
                          label="Vetoed Grid Zones (Phase 2)")

    # 3. OSM power lines
    gdf_power.plot(ax=ax, color="brown", linewidth=1, alpha=0.6,
                   label="Power Distribution Lines")

    # 4. Final scored candidates: size = demand, colour = final score
    gdf_scored.plot(
        ax=ax,
        markersize=gdf_scored["norm_demand"] * 100 + 20,
        column="Suitability_Score",
        cmap="RdYlGn",
        legend=True,
        legend_kwds={"label": "Final Suitability Score", "shrink": 0.6},
        alpha=0.85,
        zorder=5,
    )

    # 5. Basemap
    ctx.add_basemap(ax, crs=gdf_scored.crs.to_string(),
                    source=ctx.providers.CartoDB.Positron, alpha=0.4)

    ax.set_title("Phase 3: Multi-Criteria Suitability Scoring for EVCS Candidates\n"
                 "Colombo 3, 4, 11 & 12", fontsize=14)
    ax.legend(fontsize=10, loc="lower left")
    ax.axis("off")

    plt.savefig(F_MAP_P3, dpi=300, bbox_inches="tight")
    plt.show()
    print(f"[done] Map saved -> {F_MAP_P3}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 20: Phase 3 map")
    parser.add_argument("--force", action="store_true", help="re-render even if cached")
    main(parser.parse_args().force)