"""
run_all.py — Orchestrate the full Phase 1 pipeline in the right order.

First run  -> downloads everything, step by step
Later runs -> skips any step whose output already exists
--force    -> re-downloads / recomputes everything

Run:  python run_all.py [--force]
"""

import argparse

import step1_boundaries
import step2_road_network
import step3_pois
import step4_water_flood
import step5_centrality
import step6_candidates
import step7_visualize

PIPELINE = [
    ("Step 1 — boundaries",     step1_boundaries),
    ("Step 2 — road network",   step2_road_network),
    ("Step 3 — POIs",           step3_pois),
    ("Step 4 — water & flood",  step4_water_flood),
    ("Step 5 — centrality",     step5_centrality),
    ("Step 6 — merge & filter", step6_candidates),
    ("Step 7 — map",            step7_visualize),
]


def main(force: bool = False) -> None:
    for label, module in PIPELINE:
        print("\n" + "=" * 60)
        print(f">>> {label}")
        print("=" * 60)
        module.main(force=force)
    print("\nAll steps finished. Outputs are in ./data")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the whole Phase 1 pipeline")
    parser.add_argument("--force", action="store_true", help="re-download/recompute everything")
    main(parser.parse_args().force)