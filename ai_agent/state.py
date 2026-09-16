"""
state.py
========
Defines the TrafficState dataclass — the canonical representation
of observed traffic conditions used by the AI agent.

All fields come from TraCI (or MockSumoRunner) measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict


@dataclass
class DirectionState:
    """Per-approach traffic measurements."""
    direction: str                  # N / S / E / W
    queue_length: float = 0.0      # number of halted vehicles
    waiting_time: float = 0.0      # cumulative waiting time (s)
    vehicle_count: int = 0         # total vehicles on approach
    stopped: int = 0               # vehicles at standstill

    @property
    def pressure(self) -> float:
        """Pressure = queue × waiting (proxy for urgency)."""
        return self.queue_length * max(self.waiting_time, 1.0)


@dataclass
class TrafficState:
    """
    Complete snapshot of the intersection at one decision point.

    This is the OBSERVATION that the agent receives from the environment.
    """
    sim_time: float = 0.0

    # Aggregate metrics
    total_vehicles: int = 0
    total_waiting_time: float = 0.0
    average_waiting_time: float = 0.0
    total_stopped: int = 0
    average_speed: float = 0.0
    density: float = 0.0
    throughput_departed: int = 0
    throughput_arrived: int = 0

    # Traffic light
    phase: int = 0
    phase_name: str = "NS_GREEN"
    phase_duration: float = 30.0
    next_switch_in: float = 30.0

    # Per-direction breakdown
    directions: Dict[str, DirectionState] = field(default_factory=dict)

    # Derived fields
    ns_queue: float = 0.0   # N + S combined queue
    ew_queue: float = 0.0   # E + W combined queue
    ns_wait: float = 0.0    # N + S combined waiting time
    ew_wait: float = 0.0    # E + W combined waiting time
    queue_imbalance: float = 0.0  # |ns_queue - ew_queue| / max(ns_queue + ew_queue, 1)
    congestion_level: str = "LOW"  # LOW / MEDIUM / HIGH / CRITICAL

    @classmethod
    def from_runner_dict(cls, d: dict) -> "TrafficState":
        """Build a TrafficState from the dict returned by SumoRunner.get_state()."""
        directions = {}
        dir_stats = d.get("direction_stats", {})
        for dir_name, stats in dir_stats.items():
            directions[dir_name] = DirectionState(
                direction=dir_name,
                queue_length=stats.get("queue_length", 0),
                waiting_time=stats.get("waiting_time", 0.0),
                vehicle_count=stats.get("vehicle_count", 0),
                stopped=stats.get("stopped", 0),
            )

        ns_q = (
            (directions["N"].queue_length if "N" in directions else 0) +
            (directions["S"].queue_length if "S" in directions else 0)
        )
        ew_q = (
            (directions["E"].queue_length if "E" in directions else 0) +
            (directions["W"].queue_length if "W" in directions else 0)
        )
        ns_w = (
            (directions["N"].waiting_time if "N" in directions else 0) +
            (directions["S"].waiting_time if "S" in directions else 0)
        )
        ew_w = (
            (directions["E"].waiting_time if "E" in directions else 0) +
            (directions["W"].waiting_time if "W" in directions else 0)
        )
        total_q = ns_q + ew_q
        imbalance = abs(ns_q - ew_q) / max(total_q, 1)

        avg_wait = d.get("average_waiting_time", 0.0)
        if avg_wait < 15:
            congestion = "LOW"
        elif avg_wait < 35:
            congestion = "MEDIUM"
        elif avg_wait < 60:
            congestion = "HIGH"
        else:
            congestion = "CRITICAL"

        return cls(
            sim_time=d.get("sim_time", 0.0),
            total_vehicles=d.get("total_vehicles", 0),
            total_waiting_time=d.get("total_waiting_time", 0.0),
            average_waiting_time=avg_wait,
            total_stopped=d.get("total_stopped", 0),
            average_speed=d.get("average_speed", 0.0),
            density=d.get("density", 0.0),
            throughput_departed=d.get("throughput_departed", 0),
            throughput_arrived=d.get("throughput_arrived", 0),
            phase=d.get("phase", 0),
            phase_name=d.get("phase_name", "NS_GREEN"),
            phase_duration=d.get("phase_duration", 30),
            next_switch_in=d.get("next_switch_in", 30),
            directions=directions,
            ns_queue=ns_q,
            ew_queue=ew_q,
            ns_wait=ns_w,
            ew_wait=ew_w,
            queue_imbalance=round(imbalance, 3),
            congestion_level=congestion,
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        # directions: convert DirectionState objects
        d["directions"] = {
            k: {
                "direction": v["direction"],
                "queue_length": v["queue_length"],
                "waiting_time": v["waiting_time"],
                "vehicle_count": v["vehicle_count"],
                "stopped": v["stopped"],
            }
            for k, v in d["directions"].items()
        }
        return d

    def feature_vector(self) -> list:
        """
        Compact numeric feature vector for RL state representation.
        Order: [ns_queue, ew_queue, ns_wait, ew_wait, avg_wait, avg_speed,
                density, queue_imbalance, phase, next_switch_in]
        """
        return [
            min(self.ns_queue / 20.0, 1.0),
            min(self.ew_queue / 20.0, 1.0),
            min(self.ns_wait / 300.0, 1.0),
            min(self.ew_wait / 300.0, 1.0),
            min(self.average_waiting_time / 120.0, 1.0),
            min(self.average_speed / 14.0, 1.0),
            min(self.density / 10.0, 1.0),
            self.queue_imbalance,
            self.phase / 5.0,
            min(self.next_switch_in / 60.0, 1.0),
        ]

    def discretize(self) -> tuple:
        """
        Discretise state for tabular Q-learning lookup.
        Returns a tuple of bin indices.
        """
        def _bin(val, max_val, n_bins=5):
            return min(int(val / max_val * n_bins), n_bins - 1)

        return (
            _bin(self.ns_queue, 20),
            _bin(self.ew_queue, 20),
            _bin(self.average_waiting_time, 90),
            _bin(self.queue_imbalance, 1.0),
            self.phase % 6,
        )
