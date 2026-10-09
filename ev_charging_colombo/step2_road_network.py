"""
STEP 2 — Download the drivable road network inside the study area.

Reads:    data/study_area_boundary.geojson (Step 1)
Saves:    data/road_network_drive.graphml  (full projected graph — reloaded in Step 5)
          data/road_edges.geojson          (edge lines — used for plotting)
          data/road_nodes.geojson          (intersection points)

Run:  python step2_road_network.py [--force]
"""

import argparse

import geopandas as gpd
import osmnx as ox

from config import NETWORK_TYPE, TARGET_CRS, F_GRAPH, F_EDGES, F_NODES, load_study_polygon


def main(force: bool = False) -> None:
    if F_GRAPH.exists() and F_EDGES.exists() and not force:
        print(f"[skip] Road network already cached -> {F_GRAPH}")
        return

    study_area = load_study_polygon()

    print("Downloading drivable street network...")
    G = ox.graph_from_polygon(study_area, network_type=NETWORK_TYPE)

    print(f"Projecting graph to {TARGET_CRS} (metres)...")
    G_proj = ox.project_graph(G, to_crs=TARGET_CRS)

    # 1. Save the full graph so Step 5 can reload it without re-downloading
    ox.save_graphml(G_proj, filepath=F_GRAPH)

    # 2. Save nodes / edges as GeoDataFrames for mapping & inspection
    gdf_nodes, gdf_edges = ox.graph_to_gdfs(G_proj)

    # GeoJSON cannot store list/dict values -> flatten any such columns
    gdf_edges = gdf_edges.reset_index()
    for col in gdf_edges.columns:
        if col != "geometry" and gdf_edges[col].map(lambda v: isinstance(v, (list, tuple, dict))).any():
            gdf_edges[col] = gdf_edges[col].astype(str)
    gdf_edges.to_file(F_EDGES, driver="GeoJSON")

    gdf_nodes = gdf_nodes.reset_index()
    gdf_nodes.to_file(F_NODES, driver="GeoJSON")

    print(f"[done] Extracted {len(gdf_nodes)} intersections and {len(gdf_edges)} road segments.")
    print(f"       Graph cached at {F_GRAPH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 2: download road network")
    parser.add_argument("--force", action="store_true", help="re-download even if cached")
    main(parser.parse_args().force)