"""
STEP 24 — Final thesis map: phased network over the demand heatmap.
          (Only the basemap tiles need internet.)

Reads:  data/component4_final_phased_plan.geojson (Step 23)
        data/phase2_integrated_grid.geojson       (Phase 2, Step 13)
Saves:  data/Component4_Final_Thesis_Map.png

Run:  python step24_visualize_phase4.py [--force]
"""

import argparse

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import contextily as ctx

from config import (CAPACITY_MAP, PHASES, MIN_STATION_SPACING_M,
                    F_FINAL_PLAN, F_GRID_FINAL, F_MAP_P4)

PHASE_COLORS = {
    "Phase_1_2027": "#2ca02c",   # green
    "Phase_2_2030": "#ff7f0e",   # orange
    "Phase_3_2035": "#d62728",   # red
}


def main(force: bool = False) -> None:
    if F_MAP_P4.exists() and not force:
        print(f"[skip] Phase 4 map already cached -> {F_MAP_P4}")
        return

    gdf_plan = gpd.read_file(F_FINAL_PLAN).to_crs("EPSG:32644")
    gdf_grid = gpd.read_file(F_GRID_FINAL).to_crs("EPSG:32644")

    fig, ax = plt.subplots(figsize=(14, 11))

    # 1. Background demand heatmap
    gdf_grid.plot(ax=ax, column="smoothed_demand", cmap="YlOrRd",
                  alpha=0.4, legend=False)

    # 2. Stations per phase, size growing with each phase to show build-out
    for phase, color in PHASE_COLORS.items():
        subset = gdf_plan[gdf_plan["Phase"] == phase]
        if not len(subset):
            continue  # guard: phase may be empty if constraints stopped early
        capacity = CAPACITY_MAP.get(phase, "")
        ax.scatter(
            subset.geometry.x, subset.geometry.y,
            c=color, s=200,
            label=f"{phase} ({capacity})",
            edgecolor="black", linewidth=1.5, zorder=5,
        )
        for x, y, sid in zip(subset.geometry.x, subset.geometry.y, subset["station_id"]):
            ax.text(x, y + 80, sid, fontsize=8, ha="center",
                    fontweight="bold", color=color)

    # 3. Spacing exclusion circles for Phase 1 (proves the constraint works)
    phase1 = gdf_plan[gdf_plan["Phase"] == "Phase_1_2027"]
    for geom in phase1.geometry:
        ax.add_patch(plt.Circle((geom.x, geom.y), MIN_STATION_SPACING_M,
                                color="green", alpha=0.08,
                                linestyle="--", linewidth=1, zorder=3))

    # 4. Basemap + formatting
    ctx.add_basemap(ax, crs=gdf_plan.crs.to_string(),
                    source=ctx.providers.CartoDB.Positron, alpha=0.5)
    ax.set_aspect("equal")  # UTM metres -> circles stay circular

    handles, labels = ax.get_legend_handles_labels()
    if len(phase1):
        handles.append(Patch(facecolor="green", alpha=0.1, edgecolor="green",
                             linestyle="--",
                             label=f"{MIN_STATION_SPACING_M:.0f} m spacing zone (Phase 1)"))
    ax.legend(handles=handles, fontsize=11, loc="lower left",
              title="Deployment Strategy")

    ax.set_title("Component 4 Output: Prioritized, Phased EV Charging Network\n"
                 "Colombo 3, 4, 11 & 12", fontsize=16, fontweight="bold")
    ax.axis("off")

    plt.savefig(F_MAP_P4, dpi=300, bbox_inches="tight")
    plt.show()
    print(f"[done] Map saved -> {F_MAP_P4}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 24: final thesis map")
    parser.add_argument("--force", action="store_true", help="re-render even if cached")
    main(parser.parse_args().force)