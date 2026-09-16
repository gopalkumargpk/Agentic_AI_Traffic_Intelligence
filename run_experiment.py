"""
run_experiment.py
=================
Command-line experiment runner for reproducible Fixed vs Agentic AI comparison.

Usage:
    python run_experiment.py --controller fixed  --demand medium --duration 1800 --seed 42
    python run_experiment.py --controller agentic --demand medium --duration 1800 --seed 42

Results are written to:
    data/results/<timestamp>_<controller>_<demand>.csv
    data/results/comparison_<timestamp>.json   (when both runs complete)
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from simulation.sumo_runner import get_runner, is_sumo_available
from traffic_controller.fixed_controller import FixedController
from traffic_controller.adaptive_controller import AdaptiveController
from ai_agent.state import TrafficState
from backend.database import (
    init_db, create_run, update_run_status,
    record_traffic_state, record_agent_decision, record_performance,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

RESULTS_DIR = ROOT / "data" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def run_fixed(args, run_id: int) -> dict:
    """Run the fixed-time controller experiment."""
    logger.info(f"=== FIXED CONTROLLER | demand={args.demand} | duration={args.duration}s ===")

    runner = get_runner(seed=args.seed, demand=args.demand)
    controller = FixedController(runner=runner, ns_green=args.ns_green, ew_green=args.ew_green)
    controller.start()

    csv_path = RESULTS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_fixed_{args.demand}.csv"
    rows = []

    step_size = 5
    elapsed = 0

    while elapsed < args.duration:
        state = controller.step(step_size)
        elapsed += step_size

        row = {
            "sim_time": state.sim_time,
            "avg_waiting_time": state.average_waiting_time,
            "total_waiting_time": state.total_waiting_time,
            "ns_queue": state.ns_queue,
            "ew_queue": state.ew_queue,
            "throughput": state.throughput_arrived,
            "avg_speed": state.average_speed,
            "phase": state.phase,
            "congestion": state.congestion_level,
        }
        rows.append(row)

        if elapsed % 60 < step_size:
            logger.info(
                f"  t={state.sim_time:.0f}s | wait={state.average_waiting_time:.1f}s | "
                f"ns_q={state.ns_queue:.0f} ew_q={state.ew_queue:.0f} | "
                f"tp={state.throughput_arrived}"
            )

        try:
            record_traffic_state(run_id, state.to_dict())
        except Exception:
            pass

    controller.stop()
    summary = controller.metrics.summary()

    # Save CSV
    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"CSV saved: {csv_path}")

    record_performance(run_id, summary)
    update_run_status(run_id, "completed")

    _print_summary("FIXED", summary)
    return summary


def run_agentic(args, run_id: int) -> dict:
    """Run the agentic AI controller experiment."""
    logger.info(f"=== AGENTIC AI CONTROLLER | demand={args.demand} | duration={args.duration}s ===")

    runner = get_runner(seed=args.seed, demand=args.demand)
    controller = AdaptiveController(runner=runner, decision_interval=args.decision_interval)
    controller.start()

    csv_path = RESULTS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_agentic_{args.demand}.csv"
    rows = []

    step_size = 5
    elapsed = 0

    while elapsed < args.duration:
        state, cycle_log = controller.step(step_size)
        elapsed += step_size

        row = {
            "sim_time": state.sim_time,
            "avg_waiting_time": state.average_waiting_time,
            "total_waiting_time": state.total_waiting_time,
            "ns_queue": state.ns_queue,
            "ew_queue": state.ew_queue,
            "throughput": state.throughput_arrived,
            "avg_speed": state.average_speed,
            "phase": state.phase,
            "congestion": state.congestion_level,
            "reward": cycle_log.reward if cycle_log else 0,
            "goal": cycle_log.goal if cycle_log else "",
            "action": cycle_log.selected_action if cycle_log else "",
        }
        rows.append(row)

        if cycle_log:
            logger.info(
                f"  [AI Cycle {cycle_log.cycle_id}] t={state.sim_time:.0f}s | "
                f"goal={cycle_log.goal} | action={cycle_log.selected_action} | "
                f"reward={cycle_log.reward:+.3f} | "
                f"wait={state.average_waiting_time:.1f}s"
            )
            try:
                record_agent_decision(run_id, cycle_log.to_dict())
            except Exception:
                pass

        try:
            record_traffic_state(run_id, state.to_dict())
        except Exception:
            pass

    controller.stop()
    summary = controller.metrics.summary()

    # Save CSV
    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        logger.info(f"CSV saved: {csv_path}")

    record_performance(run_id, summary)
    update_run_status(run_id, "completed")

    _print_summary("AGENTIC AI", summary)
    return summary


def _print_summary(label: str, summary: dict) -> None:
    print(f"\n{'='*55}")
    print(f"  {label} RESULTS")
    print(f"{'='*55}")
    print(f"  Avg Waiting Time:  {summary.get('average_waiting_time_s', '?'):.2f} s")
    print(f"  Total Wait Time:   {summary.get('total_waiting_time_s', '?'):.0f} s")
    print(f"  Max NS Queue:      {summary.get('max_ns_queue', '?'):.1f} veh")
    print(f"  Max EW Queue:      {summary.get('max_ew_queue', '?'):.1f} veh")
    print(f"  Throughput:        {summary.get('throughput_vehicles', '?')} veh")
    print(f"  Avg Speed:         {summary.get('average_speed_ms', '?'):.2f} m/s")
    if "average_reward" in summary and summary["average_reward"] is not None:
        print(f"  Avg Reward:        {summary['average_reward']:+.4f}")
        print(f"  AI Decisions:      {summary.get('num_decisions', '?')}")
    print(f"{'='*55}\n")


def compare_and_save(fixed_summary: dict, agentic_summary: dict, args) -> None:
    """Generate comparison JSON and print table."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    comp_path = RESULTS_DIR / f"comparison_{ts}.json"

    metrics_to_compare = [
        ("average_waiting_time_s", "Average Waiting Time (s)", False),
        ("total_waiting_time_s",   "Total Waiting Time (s)",   False),
        ("max_ns_queue",           "Max NS Queue (veh)",        False),
        ("max_ew_queue",           "Max EW Queue (veh)",        False),
        ("throughput_vehicles",    "Throughput (veh)",          True),
        ("average_speed_ms",       "Avg Speed (m/s)",           True),
    ]

    comparison = {
        "metadata": {
            "demand": args.demand,
            "duration": args.duration,
            "seed": args.seed,
            "timestamp": ts,
        },
        "rows": [],
    }

    print(f"\n{'='*70}")
    print(f"  COMPARISON: Fixed-Time vs Agentic AI  (demand={args.demand})")
    print(f"{'='*70}")
    print(f"  {'Metric':<30} {'Fixed':>10} {'AI':>10} {'Change':>10}")
    print(f"  {'-'*60}")

    for key, label, higher_is_better in metrics_to_compare:
        f_val = fixed_summary.get(key)
        a_val = agentic_summary.get(key)

        if f_val is not None and a_val is not None and f_val != 0:
            delta_pct = (a_val - f_val) / abs(f_val) * 100
            if higher_is_better:
                improvement = f"{'UP' if delta_pct > 0 else 'DN'} {abs(delta_pct):.1f}%"
            else:
                improvement = f"{'DN' if delta_pct < 0 else 'UP'} {abs(delta_pct):.1f}%"
        else:
            delta_pct = None
            improvement = "--"

        fv_str = str(round(f_val, 2)) if f_val is not None else '--'
        av_str = str(round(a_val, 2)) if a_val is not None else '--'
        print(f"  {label:<30} {fv_str:>10} {av_str:>10} {improvement:>10}")

        comparison["rows"].append({
            "key": key,
            "label": label,
            "fixed": f_val,
            "agentic": a_val,
            "delta_pct": delta_pct,
            "higher_is_better": higher_is_better,
        })

    print(f"{'='*70}\n")

    with open(comp_path, "w", encoding="utf-8") as f:
        json.dump({"fixed": fixed_summary, "agentic": agentic_summary, "comparison": comparison}, f, indent=2, default=str)
    logger.info(f"Comparison saved: {comp_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Run Fixed or Agentic traffic controller experiment."
    )
    parser.add_argument("--controller", default="agentic", choices=["fixed", "agentic", "both"],
                        help="Which controller to run. 'both' runs fixed then agentic.")
    parser.add_argument("--demand", default="medium", help="Traffic demand level")
    parser.add_argument("--duration", type=int, default=1800, help="Simulation duration (s)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--decision-interval", type=int, default=10, dest="decision_interval",
                        help="AI decision interval (agentic only)")
    parser.add_argument("--ns-green", type=int, default=30, dest="ns_green",
                        help="NS green time (fixed only)")
    parser.add_argument("--ew-green", type=int, default=30, dest="ew_green",
                        help="EW green time (fixed only)")
    args = parser.parse_args()

    # Init database
    init_db()

    print(f"\n[**] Agentic AI Traffic Intelligence -- Experiment Runner")
    print(f"   SUMO: {'AVAILABLE' if is_sumo_available() else 'NOT INSTALLED (using mock simulation)'}")
    print(f"   Controller: {args.controller} | Demand: {args.demand} | Duration: {args.duration}s | Seed: {args.seed}\n")

    fixed_summary = None
    agentic_summary = None

    if args.controller in ("fixed", "both"):
        run_id = create_run(
            run_name=f"fixed_{args.demand}_{args.seed}",
            controller="fixed",
            demand=args.demand,
            seed=args.seed,
            duration=args.duration,
        )
        fixed_summary = run_fixed(args, run_id)

    if args.controller in ("agentic", "both"):
        run_id = create_run(
            run_name=f"agentic_{args.demand}_{args.seed}",
            controller="agentic",
            demand=args.demand,
            seed=args.seed,
            duration=args.duration,
        )
        agentic_summary = run_agentic(args, run_id)

    if fixed_summary and agentic_summary:
        compare_and_save(fixed_summary, agentic_summary, args)


if __name__ == "__main__":
    main()
