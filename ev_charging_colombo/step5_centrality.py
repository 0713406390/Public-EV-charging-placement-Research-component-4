"""
STEP 5 — Compute betweenness centrality on the cached road graph.
         (No downloading — reuses the graph saved by Step 2.)

Reads:   data/road_network_drive.graphml (Step 2)
Saves:   data/road_nodes_centrality.geojson (every node + raw betweenness score)

Note: the top-5% cut is applied in Step 6, so you can change
      CENTRALITY_PERCENTILE in config.py WITHOUT recomputing centrality.

Run:  python step5_centrality.py [--force]
"""

import argparse

import networkx as nx
import osmnx as ox

from config import F_GRAPH, F_NODES_BC, CENTRALITY_PERCENTILE


def main(force: bool = False) -> None:
    if F_NODES_BC.exists() and not force:
        print(f"[skip] Centrality already cached -> {F_NODES_BC}")
        return

    if not F_GRAPH.exists():
        raise FileNotFoundError(f"{F_GRAPH} not found — run step2_road_network.py first.")

    print("Loading cached road graph...")
    G = ox.load_graphml(F_GRAPH)

    print("Calculating Betweenness Centrality... (this may take 1-2 minutes)")
    bc = nx.betweenness_centrality(G, normalized=True, weight="length")

    gdf_nodes, _ = ox.graph_to_gdfs(G)
    gdf_nodes["betweenness"] = gdf_nodes.index.map(bc)
    gdf_nodes = gdf_nodes.reset_index()

    threshold = gdf_nodes["betweenness"].quantile(CENTRALITY_PERCENTILE)
    n_top = int((gdf_nodes["betweenness"] >= threshold).sum())
    print(f"Top-{int((1 - CENTRALITY_PERCENTILE) * 100)}% threshold = {threshold:.5f} "
          f"-> {n_top} high-traffic intersections.")

    gdf_nodes.to_file(F_NODES_BC, driver="GeoJSON")
    print(f"[done] Saved node scores to {F_NODES_BC}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 5: betweenness centrality")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)