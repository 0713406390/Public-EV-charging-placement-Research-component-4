"""
STEP 24 — Final thesis map: temporal evolution of the charging network.
          (Only the basemap tiles need internet.)

Reads:  data/FINAL_Phased_EV_Plan_Colombo.geojson (Step 23)
        data/phase2_integrated_grid.geojson       (Phase 2, Step 13)
Saves:  data/FINAL_Thesis_Evolution_Map.png

Run:  python step24_visualize_phase4.py [--force]
"""

import argparse

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import contextily as ctx

from config import (MIN_STATION_SPACING_M, PHASE_STYLES,
                    F_FINAL_PLAN, F_GRID_FINAL, F_MAP_P4)

LEGEND_LABELS = {
    "Phase_1_2027": "Phase 1 (2027) - Early Adopters",
    "Phase_2_2030": "Phase 2 (2030) - Commercial Expansion",
    "Phase_3_2035": "Phase 3 (2035) - Network Maturity",
}


def main(force: bool = False) -> None:
    if F_MAP_P4.exists() and not force:
        print(f"[skip] Phase 4 map already cached -> {F_MAP_P4}")
        return

    gdf_plan = gpd.read_file(F_FINAL_PLAN).to_crs("EPSG:32644")
    gdf_grid = gpd.read_file(F_GRID_FINAL).to_crs("EPSG:32644")
    vetoed_cells = gdf_grid[gdf_grid["grid_feasibility"] == 0]

    fig, ax = plt.subplots(figsize=(15, 12))

    # 1. Background demand heatmap (Blues)
    gdf_grid.plot(ax=ax, column="smoothed_demand", cmap="Blues",
                  alpha=0.4, legend=False)

    # 2. Vetoed zones for context
    if len(vetoed_cells):
        vetoed_cells.plot(ax=ax, facecolor="red", alpha=0.1)

    # 3. Stations per phase: marker shape, size and colour grow with each phase
    for phase, style in PHASE_STYLES.items():
        subset = gdf_plan[gdf_plan["Deployment_Phase"] == phase]
        if not len(subset):
            continue  # phase may be empty if constraints stopped early
        ax.scatter(
            subset.geometry.x, subset.geometry.y,
            c=style["color"], s=style["size"], marker=style["marker"],
            edgecolor="black", linewidth=1.5, zorder=5,
        )
        # Labels like "2027-1" (year from the phase name + build sequence)
        year = phase.split("_")[2]
        for x, y, seq in zip(subset.geometry.x, subset.geometry.y,
                             subset["seq_in_phase"]):
            ax.text(x, y + 90, f"{year}-{seq}", fontsize=7, ha="center",
                    fontweight="bold", color=style["color"])

    # 4. Custom legend
    legend_elements = [
        Line2D([0], [0], marker=st["marker"], color="w",
               label=LEGEND_LABELS[phase], markerfacecolor=st["color"],
               markersize=12)
        for phase, st in PHASE_STYLES.items()
    ]
    legend_elements.append(
        Line2D([0], [0], linestyle="--", color="green", alpha=0.5,
               label=f"{MIN_STATION_SPACING_M:.0f}m Exclusion Zone (Phase 1 Example)")
    )

    # 5. Dashed 500 m circles around JUST Phase 1 (proves the constraint visually)
    phase1 = gdf_plan[gdf_plan["Deployment_Phase"] == "Phase_1_2027"]
    for geom in phase1.geometry:
        circle = plt.Circle((geom.x, geom.y), MIN_STATION_SPACING_M,
                            color="green", fill=False, linestyle="--", alpha=0.5)
        ax.add_patch(circle)

    # 6. Final touches
    ctx.add_basemap(ax, crs=gdf_plan.crs.to_string(),
                    source=ctx.providers.CartoDB.Positron, alpha=0.5)
    ax.set_aspect("equal")  # UTM metres -> circles stay circular
    ax.legend(handles=legend_elements, loc="lower left", fontsize=10,
              title="Deployment Strategy")
    ax.set_title("Temporal Evolution of EV Charging Infrastructure\n"
                 "Colombo 3, 4, 11 & 12 (2027-2035)",
                 fontsize=16, fontweight="bold")
    ax.axis("off")

    plt.savefig(F_MAP_P4, dpi=300, bbox_inches="tight")
    plt.show()
    print(f"[done] Map saved -> {F_MAP_P4}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 24: final evolution map")
    parser.add_argument("--force", action="store_true", help="re-render even if cached")
    main(parser.parse_args().force)