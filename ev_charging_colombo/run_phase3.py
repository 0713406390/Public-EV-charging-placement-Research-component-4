"""
run_phase3.py — Orchestrate the full Phase 3 pipeline in the right order.

First run  -> computes everything, step by step (only Step 15 downloads)
Later runs -> skips any step whose output already exists
--force    -> recomputes everything

Run:  python run_phase3.py [--force]
"""

import argparse

import step15_power_lines
import step16_apply_grid_veto
import step17_power_distance
import step18_assign_local_demand
import step19_normalize_score
import step20_visualize_phase3

PIPELINE = [
    ("Step 15 — power lines",      step15_power_lines),
    ("Step 16 — grid veto",        step16_apply_grid_veto),
    ("Step 17 — power distance",   step17_power_distance),
    ("Step 18 — local demand",     step18_assign_local_demand),
    ("Step 19 — normalize & score", step19_normalize_score),
    ("Step 20 — Phase 3 map",      step20_visualize_phase3),
]


def main(force: bool = False) -> None:
    for label, module in PIPELINE:
        print("\n" + "=" * 60)
        print(f">>> {label}")
        print("=" * 60)
        module.main(force=force)
    print("\nPhase 3 finished. Outputs are in ./data")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the whole Phase 3 pipeline")
    parser.add_argument("--force", action="store_true", help="recompute everything")
    main(parser.parse_args().force)