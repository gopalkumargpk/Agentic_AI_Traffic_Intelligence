"""
reward.py
=========
Reward function for the Agentic AI traffic controller.

Reward is calculated after each decision step and fed back into the
learning algorithm. This is the core closed-loop feedback signal.

Reward Formula
--------------
    reward = (
        - α * Δavg_wait           (waiting time improvement)
        - β * Δns_queue            (queue reduction NS)
        - γ * Δew_queue            (queue reduction EW)
        + δ * Δthroughput          (throughput increase)
        + ε * avg_speed_bonus      (speed improvement)
        - ζ * imbalance_penalty    (fairness between directions)
    )

All deltas are normalised to [-1, +1] range.
Positive reward = improvement. Negative reward = degradation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai_agent.state import TrafficState


# Reward weights (tunable)
ALPHA = 0.40   # waiting time weight
BETA  = 0.20   # NS queue weight
GAMMA = 0.20   # EW queue weight
DELTA = 0.10   # throughput weight
EPS   = 0.05   # speed weight
ZETA  = 0.05   # imbalance penalty weight

# Normalization constants
MAX_WAIT_DELTA = 60.0       # seconds
MAX_QUEUE_DELTA = 15.0      # vehicles
MAX_THROUGHPUT_DELTA = 20.0 # vehicles/step
MAX_SPEED = 14.0            # m/s


@dataclass
class RewardResult:
    """Detailed reward breakdown for explainability."""
    total_reward: float
    waiting_time_component: float
    ns_queue_component: float
    ew_queue_component: float
    throughput_component: float
    speed_component: float
    imbalance_component: float

    # Raw deltas
    delta_avg_wait: float
    delta_ns_queue: float
    delta_ew_queue: float
    delta_throughput: int
    current_avg_wait: float
    current_ns_queue: float
    current_ew_queue: float

    def to_dict(self) -> dict:
        return {
            "total_reward": round(self.total_reward, 4),
            "waiting_time_component": round(self.waiting_time_component, 4),
            "ns_queue_component": round(self.ns_queue_component, 4),
            "ew_queue_component": round(self.ew_queue_component, 4),
            "throughput_component": round(self.throughput_component, 4),
            "speed_component": round(self.speed_component, 4),
            "imbalance_component": round(self.imbalance_component, 4),
            "delta_avg_wait": round(self.delta_avg_wait, 3),
            "delta_ns_queue": round(self.delta_ns_queue, 3),
            "delta_ew_queue": round(self.delta_ew_queue, 3),
            "delta_throughput": self.delta_throughput,
            "current_avg_wait": round(self.current_avg_wait, 2),
            "current_ns_queue": round(self.current_ns_queue, 2),
            "current_ew_queue": round(self.current_ew_queue, 2),
        }


def calculate_reward(
    prev_state: Optional[TrafficState],
    curr_state: TrafficState,
) -> RewardResult:
    """
    Calculate the reward signal by comparing the current state to the
    previous state measured BEFORE the last AI action was executed.

    If prev_state is None (first step), reward is 0.
    """
    if prev_state is None:
        return RewardResult(
            total_reward=0.0,
            waiting_time_component=0.0,
            ns_queue_component=0.0,
            ew_queue_component=0.0,
            throughput_component=0.0,
            speed_component=0.0,
            imbalance_component=0.0,
            delta_avg_wait=0.0,
            delta_ns_queue=0.0,
            delta_ew_queue=0.0,
            delta_throughput=0,
            current_avg_wait=curr_state.average_waiting_time,
            current_ns_queue=curr_state.ns_queue,
            current_ew_queue=curr_state.ew_queue,
        )

    # ---- Compute deltas (positive = improvement) ----

    # Waiting time: decrease is good
    delta_wait = prev_state.average_waiting_time - curr_state.average_waiting_time
    wait_component = ALPHA * _clip(delta_wait / MAX_WAIT_DELTA)

    # NS queue: decrease is good
    delta_ns = prev_state.ns_queue - curr_state.ns_queue
    ns_component = BETA * _clip(delta_ns / MAX_QUEUE_DELTA)

    # EW queue: decrease is good
    delta_ew = prev_state.ew_queue - curr_state.ew_queue
    ew_component = GAMMA * _clip(delta_ew / MAX_QUEUE_DELTA)

    # Throughput: increase is good
    delta_tp = (
        (curr_state.throughput_arrived - prev_state.throughput_arrived)
    )
    tp_component = DELTA * _clip(delta_tp / MAX_THROUGHPUT_DELTA)

    # Speed: increase is good
    speed_ratio = curr_state.average_speed / MAX_SPEED
    speed_component = EPS * (speed_ratio * 2 - 1)  # maps [0,1] → [-1,+1]

    # Imbalance: lower is better (fairness)
    imbalance_penalty = -ZETA * curr_state.queue_imbalance

    total = (
        wait_component
        + ns_component
        + ew_component
        + tp_component
        + speed_component
        + imbalance_penalty
    )
    total = round(_clip(total, lo=-1.0, hi=1.0), 4)

    return RewardResult(
        total_reward=total,
        waiting_time_component=round(wait_component, 4),
        ns_queue_component=round(ns_component, 4),
        ew_queue_component=round(ew_component, 4),
        throughput_component=round(tp_component, 4),
        speed_component=round(speed_component, 4),
        imbalance_component=round(imbalance_penalty, 4),
        delta_avg_wait=round(delta_wait, 3),
        delta_ns_queue=round(delta_ns, 3),
        delta_ew_queue=round(delta_ew, 3),
        delta_throughput=delta_tp,
        current_avg_wait=curr_state.average_waiting_time,
        current_ns_queue=curr_state.ns_queue,
        current_ew_queue=curr_state.ew_queue,
    )


def _clip(val: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))
