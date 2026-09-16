"""
goal_manager.py
===============
Dynamically selects and prioritises the agent's current optimisation goal
based on the observed traffic state.

Goals are not static — the agent switches goals as conditions change.
This demonstrates goal-oriented autonomous behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from ai_agent.state import TrafficState


class Goal(str, Enum):
    REDUCE_WAITING_TIME   = "REDUCE_WAITING_TIME"
    REDUCE_NS_CONGESTION  = "REDUCE_NS_CONGESTION"
    REDUCE_EW_CONGESTION  = "REDUCE_EW_CONGESTION"
    INCREASE_THROUGHPUT   = "INCREASE_THROUGHPUT"
    BALANCE_DIRECTIONS    = "BALANCE_DIRECTIONS"
    MAINTAIN_FLOW         = "MAINTAIN_FLOW"  # default low-demand goal


@dataclass
class GoalAssessment:
    goal: Goal
    priority: float           # 0..1, higher = more urgent
    reason: str
    recommended_actions: List[str]

    def to_dict(self) -> dict:
        return {
            "goal": self.goal.value,
            "priority": round(self.priority, 3),
            "reason": self.reason,
            "recommended_actions": self.recommended_actions,
        }


class GoalManager:
    """
    Analyses the current traffic state and returns a ranked list of goals.

    The highest-priority goal is passed to the Planner and Decision Engine.
    """

    # Thresholds for goal triggering
    HIGH_QUEUE_THRESHOLD     = 8    # vehicles
    CRITICAL_QUEUE_THRESHOLD = 15
    HIGH_WAIT_THRESHOLD      = 40   # seconds
    CRITICAL_WAIT_THRESHOLD  = 90
    IMBALANCE_THRESHOLD      = 0.40
    HIGH_DENSITY_THRESHOLD   = 6.0  # vehicles/approach

    def __init__(self):
        self._history: List[Goal] = []

    def evaluate(self, state: TrafficState) -> GoalAssessment:
        """
        Evaluate all possible goals against the current state.
        Return the highest-priority goal with reasoning.
        """
        assessments = self._score_all_goals(state)
        assessments.sort(key=lambda a: a.priority, reverse=True)
        best = assessments[0]
        self._history.append(best.goal)
        if len(self._history) > 20:
            self._history.pop(0)
        return best

    def _score_all_goals(self, state: TrafficState) -> List[GoalAssessment]:
        assessments = []

        # ------------------------------------------------------------------
        # 1. REDUCE_NS_CONGESTION
        # ------------------------------------------------------------------
        ns_score = 0.0
        ns_reason = ""
        ns_actions = []
        if state.ns_queue > self.HIGH_QUEUE_THRESHOLD:
            ns_score += 0.5
            ns_reason = f"N-S queue={state.ns_queue:.0f} exceeds threshold={self.HIGH_QUEUE_THRESHOLD}"
            ns_actions.append("Extend NS green phase")
        if state.ns_queue > self.CRITICAL_QUEUE_THRESHOLD:
            ns_score += 0.4
            ns_reason += " (CRITICAL)"
            ns_actions.append("Switch to NS green immediately")
        if state.ns_wait > self.HIGH_WAIT_THRESHOLD:
            ns_score += 0.3
            ns_reason += f"; NS waiting={state.ns_wait:.0f}s"
        assessments.append(GoalAssessment(
            goal=Goal.REDUCE_NS_CONGESTION,
            priority=min(ns_score, 1.0),
            reason=ns_reason or "N-S demand within normal range",
            recommended_actions=ns_actions or ["Maintain current NS timing"],
        ))

        # ------------------------------------------------------------------
        # 2. REDUCE_EW_CONGESTION
        # ------------------------------------------------------------------
        ew_score = 0.0
        ew_reason = ""
        ew_actions = []
        if state.ew_queue > self.HIGH_QUEUE_THRESHOLD:
            ew_score += 0.5
            ew_reason = f"E-W queue={state.ew_queue:.0f} exceeds threshold={self.HIGH_QUEUE_THRESHOLD}"
            ew_actions.append("Extend EW green phase")
        if state.ew_queue > self.CRITICAL_QUEUE_THRESHOLD:
            ew_score += 0.4
            ew_reason += " (CRITICAL)"
            ew_actions.append("Switch to EW green immediately")
        if state.ew_wait > self.HIGH_WAIT_THRESHOLD:
            ew_score += 0.3
            ew_reason += f"; EW waiting={state.ew_wait:.0f}s"
        assessments.append(GoalAssessment(
            goal=Goal.REDUCE_EW_CONGESTION,
            priority=min(ew_score, 1.0),
            reason=ew_reason or "E-W demand within normal range",
            recommended_actions=ew_actions or ["Maintain current EW timing"],
        ))

        # ------------------------------------------------------------------
        # 3. REDUCE_WAITING_TIME (overall)
        # ------------------------------------------------------------------
        wait_score = min(state.average_waiting_time / self.CRITICAL_WAIT_THRESHOLD, 1.0)
        if state.congestion_level in ("HIGH", "CRITICAL"):
            wait_score = min(wait_score + 0.3, 1.0)
        assessments.append(GoalAssessment(
            goal=Goal.REDUCE_WAITING_TIME,
            priority=wait_score,
            reason=(
                f"Average waiting time={state.average_waiting_time:.1f}s "
                f"(congestion={state.congestion_level})"
            ),
            recommended_actions=["Optimise signal timing", "Shorten phase for low-demand direction"],
        ))

        # ------------------------------------------------------------------
        # 4. BALANCE_DIRECTIONS (fairness)
        # ------------------------------------------------------------------
        imbalance_score = state.queue_imbalance if state.queue_imbalance > self.IMBALANCE_THRESHOLD else 0.0
        assessments.append(GoalAssessment(
            goal=Goal.BALANCE_DIRECTIONS,
            priority=imbalance_score,
            reason=f"Queue imbalance={state.queue_imbalance:.2f} (NS={state.ns_queue:.0f}, EW={state.ew_queue:.0f})",
            recommended_actions=["Balance green time allocation between NS and EW"],
        ))

        # ------------------------------------------------------------------
        # 5. INCREASE_THROUGHPUT
        # ------------------------------------------------------------------
        tp_score = 0.2  # baseline always useful
        if state.total_vehicles > 20:
            tp_score += 0.2
        if state.average_speed < 2.0:
            tp_score += 0.3  # very slow → throughput urgency
        assessments.append(GoalAssessment(
            goal=Goal.INCREASE_THROUGHPUT,
            priority=min(tp_score, 1.0),
            reason=f"Vehicles in network={state.total_vehicles}, avg speed={state.average_speed:.1f} m/s",
            recommended_actions=["Optimise cycle to move more vehicles", "Reduce unnecessary red phases"],
        ))

        # ------------------------------------------------------------------
        # 6. MAINTAIN_FLOW (default, low demand)
        # ------------------------------------------------------------------
        maintain_score = 0.15
        if state.congestion_level == "LOW" and state.density < 3.0:
            maintain_score = 0.5
        assessments.append(GoalAssessment(
            goal=Goal.MAINTAIN_FLOW,
            priority=maintain_score,
            reason=f"Light traffic detected (density={state.density:.1f}, congestion={state.congestion_level})",
            recommended_actions=["Keep standard cycle timing", "Monitor for demand changes"],
        ))

        return assessments

    def get_recent_goals(self) -> List[str]:
        return [g.value for g in self._history[-5:]]
