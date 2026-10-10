"""
run_phase2.py — Orchestrate the full Phase 2 pipeline in the right order.

First run  -> builds everything, step by step
Later runs -> skips any step whose output already exists
--force    -> recomputes everything

Run:  python run_phase2.py [--force]
"""

import argparse

import step8_fishnet_grid
import step9_demand_points
import step10_demand_to_grid
import step11_wna_smoothing
import step12_grid_risk_zones
import step13_grid_constraints
import step14_visualize_phase2

PIPELINE = [
    ("Step 8  — fishnet grid",     step8_fishnet_grid),
    ("Step 9  — demand points",    step9_demand_points),
    ("Step 10 — demand -> grid",   step10_demand_to_grid),
    ("Step 11 — WNA smoothing",    step11_wna_smoothing),
    ("Step 12 — grid risk zones",  step12_grid_risk_zones),
    ("Step 13 — constraints/veto", step13_grid_constraints),
    ("Step 14 — Phase 2 map",      step14_visualize_phase2),
]


def main(force: bool = False) -> None:
    for label, module in PIPELINE:
        print("\n" + "=" * 60)
        print(f">>> {label}")
        print("=" * 60)
        module.main(force=force)
    print("\nPhase 2 finished. Outputs are in ./data")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the whole Phase 2 pipeline")
    parser.add_argument("--force", action="store_true", help="recompute everything")
    main(parser.parse_args().force)