"""
STEP 12 — Dynamic area electricity & grid risk zones.

Supports optional dynamic area columns in data/grid_risk_zones_real.geojson:
  - 'risk_zone' (required if real file exists): Red / Orange / Amber / Green
  - 'dynamic_load_factor' (optional float, e.g. 0.2..1.5): area electricity stress/demand multiplier
  - 'headroom_factor' (optional float in [0, 1]): available grid capacity factor
"""

import argparse
import numpy as np
import geopandas as gpd
from shapely.geometry import box

from config import TARGET_CRS, F_RISK_REAL, F_RISK_ZONES, load_study_polygon

DEFAULT_ZONE_STRESS = {"Red": 1.35, "Orange": 1.15, "Amber": 1.00, "Green": 0.85}
DEFAULT_HEADROOM = {"Red": 0.15, "Orange": 0.40, "Amber": 0.70, "Green": 0.95}


def simulate_placeholder(boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print("[warn] No real grid-risk data found — SIMULATING placeholder area electricity zones.")
    minx, miny, maxx, maxy = boundary.total_bounds
    w, h = maxx - minx, maxy - miny

    zones = ["Red", "Orange", "Amber"]
    return gpd.GeoDataFrame(
        {
            "area_id": ["AREA_CORE_HIGH_LOAD", "AREA_NW_MED_LOAD", "AREA_SE_MODERATE"],
            "risk_zone": zones,
            "dynamic_load_factor": [DEFAULT_ZONE_STRESS[z] for z in zones],
            "headroom_factor": [DEFAULT_HEADROOM[z] for z in zones],
            "geometry": [
                box(minx + 0.45 * w, miny + 0.45 * h, minx + 0.55 * w, miny + 0.55 * h),
                box(minx + 0.15 * w, miny + 0.60 * h, minx + 0.25 * w, miny + 0.70 * h),
                box(minx + 0.65 * w, miny + 0.15 * h, minx + 0.78 * w, miny + 0.28 * h),
            ],
        },
        crs=TARGET_CRS,
    )


def main(force: bool = False) -> None:
    if F_RISK_ZONES.exists() and not force:
        print(f"[skip] Risk zones already cached -> {F_RISK_ZONES}")
        return

    if F_RISK_REAL.exists():
        print(f"[info] Real grid-risk data found -> {F_RISK_REAL}")
        gdf_risk = gpd.read_file(F_RISK_REAL).to_crs(TARGET_CRS)
        if "risk_zone" not in gdf_risk.columns:
            raise ValueError("Real risk file must contain a 'risk_zone' column.")
        gdf_risk["risk_zone"] = gdf_risk["risk_zone"].astype(str).str.strip().str.capitalize()

        if "dynamic_load_factor" not in gdf_risk.columns:
            gdf_risk["dynamic_load_factor"] = gdf_risk["risk_zone"].map(DEFAULT_ZONE_STRESS).fillna(1.0)
        else:
            gdf_risk["dynamic_load_factor"] = pd.to_numeric(
                gdf_risk["dynamic_load_factor"], errors="coerce"
            ).fillna(1.0)

        if "headroom_factor" not in gdf_risk.columns:
            gdf_risk["headroom_factor"] = gdf_risk["risk_zone"].map(DEFAULT_HEADROOM).fillna(0.75)
        else:
            gdf_risk["headroom_factor"] = np.clip(
                pd.to_numeric(gdf_risk["headroom_factor"], errors="coerce").fillna(0.75), 0.0, 1.0
            )
    else:
        boundary = gpd.GeoDataFrame(geometry=[load_study_polygon()], crs=TARGET_CRS)
        gdf_risk = simulate_placeholder(boundary)

    gdf_risk.to_file(F_RISK_ZONES, driver="GeoJSON")
    print(f"[done] Saved {len(gdf_risk)} dynamic area electricity zones -> {F_RISK_ZONES}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 12: dynamic area electricity & grid risk")
    parser.add_argument("--force", action="store_true", help="re-extract even if cached")
    main(parser.parse_args().force)