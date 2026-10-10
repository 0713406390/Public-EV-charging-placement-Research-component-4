"""
STEP 11 — Weighted Neighborhood Average (WNA) smoothing of grid demand.

Reads:  data/phase2_grid_raw_demand.geojson (Step 10)
Saves:  data/phase2_grid_smoothed_demand.geojson (adds 'smoothed_demand')

Tip: to experiment with the kernel, just change WNA_KERNEL_RADIUS / WNA_KAPPA
in config.py and re-run THIS step only (Step 10's output is reused).

Run:  python step11_wna_smoothing.py [--force]
"""

import argparse

import numpy as np
import geopandas as gpd
from scipy.ndimage import convolve

from config import WNA_KERNEL_RADIUS, WNA_KAPPA, F_GRID_RAW, F_GRID_SMOOTH


def build_decay_kernel(radius: int, kappa: float) -> np.ndarray:
    """Distance-decay kernel (Trinidad Eq. 4 concept): w = 1/(1+d)^kappa.
    d = distance in cells (0 centre, 1 adjacent, ~1.41 diagonal)."""
    size = 2 * radius + 1
    kernel = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            d = np.hypot(i - radius, j - radius)
            kernel[i, j] = 1.0 if d == 0 else 1.0 / (1.0 + d) ** kappa
    return kernel / kernel.sum()  # normalise


def main(force: bool = False) -> None:
    if F_GRID_SMOOTH.exists() and not force:
        print(f"[skip] Smoothed demand already cached -> {F_GRID_SMOOTH}")
        return

    gdf = gpd.read_file(F_GRID_RAW)

    # --- Rasterise using the indices baked in by Step 8 -------------------
    n_rows = int(gdf["row_idx"].max()) + 1
    n_cols = int(gdf["col_idx"].max()) + 1
    demand_array = np.zeros((n_rows, n_cols))
    demand_array[gdf["row_idx"].to_numpy(), gdf["col_idx"].to_numpy()] = \
        gdf["raw_demand"].to_numpy()

    # --- Apply convolution (smooth) ---------------------------------------
    kernel = build_decay_kernel(WNA_KERNEL_RADIUS, WNA_KAPPA)
    smoothed_array = convolve(demand_array, kernel, mode="constant", cval=0.0)

    # --- Map the smoothed values back to the vector grid -------------------
    gdf["smoothed_demand"] = \
        smoothed_array[gdf["row_idx"].to_numpy(), gdf["col_idx"].to_numpy()]

    gdf.to_file(F_GRID_SMOOTH, driver="GeoJSON")
    k = 2 * WNA_KERNEL_RADIUS + 1
    print(f"[done] WNA applied ({k}x{k} kernel, kappa={WNA_KAPPA}). "
          "Demand is now spatially continuous.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 11: WNA smoothing")
    parser.add_argument("--force", action="store_true", help="recompute even if cached")
    main(parser.parse_args().force)