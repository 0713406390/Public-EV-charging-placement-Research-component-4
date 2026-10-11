"""
run_phase4.py — Orchestrate the full Phase 4 pipeline in the right order.

Requires the Phase 1-3 outputs in ./data (steps 1-20).
Only heavy download-free compute here; the matrix (step 21) is cached.

Run:  python run_phase4.py [--force]
"""

import argparse

import step21_distance_matrix
import step22_greedy_optimizer
import step23_phased_plan
import step24_visualize_phase4

PIPELINE = [
    ("Step 21 — distance matrix",  step21_distance_matrix),
    ("Step 22 — greedy optimizer", step22_greedy_optimizer),
    ("Step 23 — phased plan",      step23_phased_plan),
    ("Step 24 — final map",        step24_visualize_phase4),
]


def main(force: bool = False) -> None:
    for label, module in PIPELINE:
        print("\n" + "=" * 60)
        print(f">>> {label}")
        print("=" * 60)
        module.main(force=force)
    print("\nPhase 4 finished. Outputs are in ./data")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the whole Phase 4 pipeline")
    parser.add_argument("--force", action="store_true", help="recompute everything")
    main(parser.parse_args().force)