"""
fixed_controller.py
===================
Fixed-time traffic signal controller (baseline).

Implements a simple pre-timed signal plan:
    Phase 0 (NS Green):   configurable duration (default 30s)
    Phase 1 (NS Yellow):  4s
    Phase 2 (All Red):    2s
    Phase 3 (EW Green):   configurable duration (default 30s)
    Phase 4 (EW Yellow):  4s
    Phase 5 (All Red):    2s

This is the BASELINE against which the AI controller is compared.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

from simulation.sumo_runner import SumoRunner, MockSumoRunner
from ai_agent.state import TrafficState

logger = logging.getLogger(__name__)

PHASE_DURATIONS = {
    0: 30,  # NS green
    1: 4,   # NS yellow
    2: 2,   # All red
    3: 30,  # EW green
    4: 4,   # EW yellow
    5: 2,   # All red
}


@dataclass
class FixedControllerMetrics:
    """Accumulated performance metrics for the fixed controller."""
    total_steps: int = 0
    total_waiting_time: float = 0.0
    total_vehicles: int = 0
    total_stopped: int = 0
    total_throughput: int = 0
    max_ns_queue: float = 0.0
    max_ew_queue: float = 0.0
    sum_avg_wait: float = 0.0
    sum_avg_speed: float = 0.0

    def update(self, state: TrafficState) -> None:
        self.total_steps += 1
        self.total_waiting_time += state.total_waiting_time
        self.total_vehicles = max(self.total_vehicles, state.total_vehicles)
        self.total_stopped  += state.total_stopped
        self.total_throughput = state.throughput_arrived
        self.max_ns_queue = max(self.max_ns_queue, state.ns_queue)
        self.max_ew_queue = max(self.max_ew_queue, state.ew_queue)
        self.sum_avg_wait  += state.average_waiting_time
        self.sum_avg_speed += state.average_speed

    @property
    def average_waiting_time(self) -> float:
        return self.sum_avg_wait / max(self.total_steps, 1)

    @property
    def average_speed(self) -> float:
        return self.sum_avg_speed / max(self.total_steps, 1)

    @property
    def average_queue(self) -> float:
        return (self.max_ns_queue + self.max_ew_queue) / 2.0

    def summary(self) -> dict:
        return {
            "controller": "fixed",
            "total_steps": self.total_steps,
            "average_waiting_time_s": round(self.average_waiting_time, 2),
            "total_waiting_time_s": round(self.total_waiting_time, 2),
            "max_ns_queue": round(self.max_ns_queue, 1),
            "max_ew_queue": round(self.max_ew_queue, 1),
            "average_queue": round(self.average_queue, 1),
            "throughput_vehicles": self.total_throughput,
            "average_speed_ms": round(self.average_speed, 2),
        }


class FixedController:
    """
    Fixed-time signal controller.

    Runs the simulation with a pre-configured phase cycle.
    Does NOT adapt to traffic conditions.
    """

    def __init__(
        self,
        runner,
        ns_green: int = 30,
        ew_green: int = 30,
        on_state: Optional[Callable[[TrafficState], None]] = None,
    ):
        self.runner = runner
        self.ns_green = ns_green
        self.ew_green = ew_green
        self.on_state = on_state  # callback for live updates

        self._phase_schedule = [
            (0, ns_green),
            (1, 4),
            (2, 2),
            (3, ew_green),
            (4, 4),
            (5, 2),
        ]
        self._schedule_idx = 0
        self._phase_remaining = self._phase_schedule[0][1]
        self.metrics = FixedControllerMetrics()
        self._running = False

    def start(self) -> None:
        self.runner.start()
        self._running = True
        # Apply initial phase
        phase, dur = self._phase_schedule[0]
        self.runner.set_phase(phase, dur)
        logger.info(
            f"FixedController started: NS={self.ns_green}s, EW={self.ew_green}s"
        )

    def step(self, sim_steps: int = 1) -> TrafficState:
        """Advance simulation and enforce the fixed timing plan."""
        for _ in range(sim_steps):
            self.runner.step(1)
            self._phase_remaining -= 1

            if self._phase_remaining <= 0:
                self._schedule_idx = (self._schedule_idx + 1) % len(self._phase_schedule)
                phase, dur = self._phase_schedule[self._schedule_idx]
                self._phase_remaining = dur
                self.runner.set_phase(phase, dur)

        raw = self.runner.get_state()
        state = TrafficState.from_runner_dict(raw)
        self.metrics.update(state)

        if self.on_state:
            try:
                self.on_state(state)
            except Exception as e:
                logger.warning(f"on_state callback error: {e}")

        return state

    def stop(self) -> None:
        self._running = False
        self.runner.stop()
        logger.info("FixedController stopped.")
        logger.info(f"Summary: {self.metrics.summary()}")

    def is_running(self) -> bool:
        return self._running

    def get_current_state_dict(self) -> dict:
        try:
            raw = self.runner.get_state()
            return TrafficState.from_runner_dict(raw).to_dict()
        except Exception:
            return {}
