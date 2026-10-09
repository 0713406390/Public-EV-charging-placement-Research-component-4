"""
STEP 7 — Draw the Phase 1 map and export the PNG.
         (Only the basemap tiles need internet.)

Reads:   data/road_edges.geojson                (Step 2)
         data/flood_risk_zone.geojson           (Step 4)
         data/phase1_candidates_colombo.geojson (Step 6)
Saves:   data/Phase1_Candidate_Nodes_Map.png

Run:  python step7_visualize.py [--force]
"""

import argparse

import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx

from config import F_EDGES, F_FLOOD, F_CANDIDATES, F_MAP


def main(force: bool = False) -> None:
    if F_MAP.exists() and not force:
        print(f"[skip] Map already cached -> {F_MAP}")
        return

    for f in (F_EDGES, F_FLOOD, F_CANDIDATES):
        if not f.exists():
            raise FileNotFoundError(f"{f} is missing — run the earlier steps first.")

    gdf_edges = gpd.read_file(F_EDGES)
    gdf_flood = gpd.read_file(F_FLOOD)
    gdf_final = gpd.read_file(F_CANDIDATES)

    fig, ax = plt.subplots(figsize=(12, 12))

    # 1. Base road network
    gdf_edges.plot(ax=ax, linewidth=0.5, color="gray", alpha=0.5)

    # 2. Flood-risk zones (red, transparent)
    gdf_flood.plot(ax=ax, color="red", alpha=0.2,
                   label="High Flood Risk Zone (50m buffer)")

    # 3. Final safe candidates, coloured by source
    traffic_nodes = gdf_final[gdf_final["candidate_source"] == "Traffic_Centrality"]
    poi_nodes = gdf_final[gdf_final["candidate_source"] != "Traffic_Centrality"]

    if len(traffic_nodes):
        traffic_nodes.plot(ax=ax, color="blue", markersize=15,
                           label="High-Traffic Intersections (Novelty)", zorder=5)
    if len(poi_nodes):
        poi_nodes.plot(ax=ax, color="green", markersize=30, marker="s",
                       label="Existing Fuel/Parking", zorder=5)

    # 4. Basemap for context (requires internet)
    ctx.add_basemap(ax, crs=gdf_edges.crs.to_string(),
                    source=ctx.providers.CartoDB.Positron)

    ax.set_title("Phase 1: EV Charging Candidate Nodes\n"
                 "Colombo 3, 4, 11 & 12 (Flood Exclusion Applied)", fontsize=16)
    ax.legend(fontsize=12)
    ax.axis("off")

    plt.savefig(F_MAP, dpi=300, bbox_inches="tight")
    plt.show()
    print(f"[done] Map saved -> {F_MAP}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 7: plot map")
    parser.add_argument("--force", action="store_true", help="re-render even if cached")
    main(parser.parse_args().force)