"""
STEP 6 — Merge the two candidate sources and apply the flood exclusion.
         (Pure file-based geoprocessing — nothing is downloaded.)

Reads:   data/road_nodes_centrality.geojson     (Step 5)
         data/pois_fuel_parking.geojson         (Step 3)
         data/flood_risk_zone.geojson           (Step 4)
Saves:   data/phase1_candidates_colombo.geojson (final safe candidates)

Run:  python step6_candidates.py [--force]
"""

import pandas as pd
import geopandas as gpd

from config import F_NODES_BC, F_POIS, F_FLOOD, F_CANDIDATES, CENTRALITY_PERCENTILE


def main(force: bool = False) -> None:
    if F_CANDIDATES.exists() and not force:
        print(f"[skip] Final candidates already cached -> {F_CANDIDATES}")
        return

    # --- 0. Make sure inputs exist --------------------------------------
    for f in (F_NODES_BC, F_POIS, F_FLOOD):
        if not f.exists():
            raise FileNotFoundError(f"{f} is missing — run the earlier steps first.")

    # --- 1. Traffic candidates (top 5% betweenness) ----------------------
    gdf_traffic = gpd.read_file(F_NODES_BC)
    threshold = gdf_traffic["betweenness"].quantile(CENTRALITY_PERCENTILE)
    gdf_traffic = gdf_traffic[gdf_traffic["betweenness"] >= threshold].copy()
    gdf_traffic["candidate_source"] = "Traffic_Centrality"

    # --- 2. POI candidates ------------------------------------------------
    gdf_pois = gpd.read_file(F_POIS)
    gdf_pois["candidate_source"] = gdf_pois["poi_type"]
    gdf_pois["betweenness"] = float("nan")

    # osmid as string in BOTH frames (avoids mixed-type GeoJSON errors)
    gdf_traffic["osmid"] = gdf_traffic["osmid"].astype(str)
    gdf_pois["osmid"] = gdf_pois["osmid"].astype(str)
    gdf_traffic["name"] = None

    cols = ["osmid", "name", "betweenness", "candidate_source", "geometry"]
    gdf_traffic = gdf_traffic[cols]
    gdf_pois = gdf_pois[cols]

    # --- 3. Merge ----------------------------------------------------------
    gdf_all_candidates = gpd.GeoDataFrame(
        pd.concat([gdf_traffic, gdf_pois], ignore_index=True),
        crs=gdf_traffic.crs,
    )
    print(f"Total combined candidates before filtering: {len(gdf_all_candidates)}")

    # --- 4. Apply flood exclusion (the hard constraint) ---------------------
    gdf_flood = gpd.read_file(F_FLOOD)
    candidates_in_flood = gpd.sjoin(
        gdf_all_candidates, gdf_flood[["geometry"]],
        how="inner", predicate="intersects",
    )
    flood_victim_ids = candidates_in_flood.index.unique()

    gdf_final = gdf_all_candidates[~gdf_all_candidates.index.isin(flood_victim_ids)].copy()
    gdf_final = gdf_final.reset_index(drop=True)

    print(f"Removed {len(flood_victim_ids)} candidates due to high flood risk.")
    print(f"Total SAFE candidates after flood exclusion: {len(gdf_final)}")

    # --- 5. Export for Phase 2 ----------------------------------------------
    gdf_final.to_file(F_CANDIDATES, driver="GeoJSON")
    print(f"[done] Saved {F_CANDIDATES}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Step 6: merge & filter candidates")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)