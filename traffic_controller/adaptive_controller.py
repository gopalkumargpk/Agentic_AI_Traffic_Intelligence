"""
adaptive_controller.py
======================
Adaptive AI controller — wraps the AgentController and provides
the same interface as FixedController for fair comparison.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Callable

from ai_agent.agent import AgentController, AgentCycleLog
from ai_agent.state import TrafficState

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveControllerMetrics:
    """Accumulated metrics for the adaptive controller (mirrors FixedControllerMetrics)."""
    total_steps: int = 0
    total_waiting_time: float = 0.0
    total_stopped: int = 0
    max_ns_queue: float = 0.0
    max_ew_queue: float = 0.0
    sum_avg_wait: float = 0.0
    sum_avg_speed: float = 0.0
    total_throughput: int = 0
    total_reward: float = 0.0
    num_decisions: int = 0

    def update(self, state: TrafficState, reward: float = 0.0) -> None:
        self.total_steps += 1
        self.total_waiting_time += state.total_waiting_time
        self.total_stopped += state.total_stopped
        self.max_ns_queue = max(self.max_ns_queue, state.ns_queue)
        self.max_ew_queue = max(self.max_ew_queue, state.ew_queue)
        self.sum_avg_wait += state.average_waiting_time
        self.sum_avg_speed += state.average_speed
        self.total_throughput = state.throughput_arrived
        if reward != 0.0:
            self.total_reward += reward
            self.num_decisions += 1

    @property
    def average_waiting_time(self) -> float:
        return self.sum_avg_wait / max(self.total_steps, 1)

    @property
    def average_speed(self) -> float:
        return self.sum_avg_speed / max(self.total_steps, 1)

    @property
    def average_queue(self) -> float:
        return (self.max_ns_queue + self.max_ew_queue) / 2.0

    @property
    def average_reward(self) -> float:
        return self.total_reward / max(self.num_decisions, 1)

    def summary(self) -> dict:
        return {
            "controller": "agentic",
            "total_steps": self.total_steps,
            "average_waiting_time_s": round(self.average_waiting_time, 2),
            "total_waiting_time_s": round(self.total_waiting_time, 2),
            "max_ns_queue": round(self.max_ns_queue, 1),
            "max_ew_queue": round(self.max_ew_queue, 1),
            "average_queue": round(self.average_queue, 1),
            "throughput_vehicles": self.total_throughput,
            "average_speed_ms": round(self.average_speed, 2),
            "average_reward": round(self.average_reward, 4),
            "num_decisions": self.num_decisions,
        }


class AdaptiveController:
    """
    AI-based adaptive traffic controller.

    Wraps the AgentController (which contains the full agent cycle)
    and exposes the same interface as FixedController.
    """

    def __init__(
        self,
        runner,
        decision_interval: int = 10,
        on_state: Optional[Callable[[TrafficState, Optional[AgentCycleLog]], None]] = None,
        on_cycle: Optional[Callable[[AgentCycleLog], None]] = None,
    ):
        self.runner = runner
        self.on_state = on_state
        self.metrics = AdaptiveControllerMetrics()
        self._agent = AgentController(
            runner=runner,
            decision_interval=decision_interval,
            on_cycle_complete=on_cycle,
        )
        self._running = False

    def start(self) -> None:
        self._agent.start()
        self._running = True
        logger.info("AdaptiveController started.")

    def step(self, sim_steps: int = 1):
        """Advance simulation and run agent cycle if decision interval reached."""
        cycle_log = self._agent.step(sim_steps)

        # Collect state
        raw = self.runner.get_state()
        state = TrafficState.from_runner_dict(raw)

        reward = 0.0
        if cycle_log:
            reward = cycle_log.reward

        self.metrics.update(state, reward)

        if self.on_state:
            try:
                self.on_state(state, cycle_log)
            except Exception as e:
                logger.warning(f"on_state callback error: {e}")

        return state, cycle_log

    def stop(self) -> None:
        self._agent.stop()
        self._running = False
        logger.info("AdaptiveController stopped.")
        logger.info(f"Summary: {self.metrics.summary()}")

    def is_running(self) -> bool:
        return self._running

    @property
    def latest_cycle(self) -> Optional[AgentCycleLog]:
        return self._agent.latest_cycle

    @property
    def agent(self) -> AgentController:
        return self._agent

    def get_current_state_dict(self) -> dict:
        return self._agent.get_current_state_dict()
