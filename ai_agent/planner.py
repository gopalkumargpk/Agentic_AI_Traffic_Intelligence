"""
planner.py
==========
Generates candidate actions for the Decision Engine.

The planner takes the current TrafficState and Goal, then enumerates
a set of candidate signal-control actions with estimated payoffs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ai_agent.state import TrafficState
from ai_agent.goal_manager import Goal


# Phase constants
PHASE_NS_GREEN  = 0
PHASE_NS_YELLOW = 1
PHASE_ALL_RED_1 = 2
PHASE_EW_GREEN  = 3
PHASE_EW_YELLOW = 4
PHASE_ALL_RED_2 = 5

# Safety constraints
MIN_GREEN  = 10   # seconds
MAX_GREEN  = 60   # seconds
YELLOW_DUR = 4    # seconds
ALL_RED    = 2    # seconds


@dataclass
class CandidateAction:
    """A candidate signal-control action with estimated value."""
    action_id: str
    description: str
    target_phase: int
    duration: int                  # seconds for this phase
    estimated_value: float         # higher = more beneficial
    rationale: str
    is_safe: bool = True

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "target_phase": self.target_phase,
            "duration": self.duration,
            "estimated_value": round(self.estimated_value, 3),
            "rationale": self.rationale,
            "is_safe": self.is_safe,
        }


class Planner:
    """
    Generates a list of candidate actions given the state and active goal.

    Actions include:
    - Extend current green phase
    - Shorten current green phase
    - Switch phase (only via safe yellow transition)
    - Hold current plan
    """

    def generate_candidates(
        self,
        state: TrafficState,
        goal: Goal,
    ) -> List[CandidateAction]:
        candidates = []

        phase = state.phase
        in_green = phase in (PHASE_NS_GREEN, PHASE_EW_GREEN)
        in_yellow = phase in (PHASE_NS_YELLOW, PHASE_EW_YELLOW)
        in_red    = phase in (PHASE_ALL_RED_1, PHASE_ALL_RED_2)

        ns_pressure = state.ns_queue * max(state.ns_wait, 1)
        ew_pressure = state.ew_queue * max(state.ew_wait, 1)
        total_pressure = max(ns_pressure + ew_pressure, 1)

        if in_green:
            current_green = PHASE_NS_GREEN if phase == PHASE_NS_GREEN else PHASE_EW_GREEN
            other_green   = PHASE_EW_GREEN  if phase == PHASE_NS_GREEN else PHASE_NS_GREEN
            current_pressure = ns_pressure if phase == PHASE_NS_GREEN else ew_pressure
            other_pressure   = ew_pressure if phase == PHASE_NS_GREEN else ns_pressure

            # --- Action 1: Extend current green by 10 s ---
            ext_val = self._extend_value(current_pressure, other_pressure, total_pressure, goal, phase)
            candidates.append(CandidateAction(
                action_id="EXTEND_GREEN_10",
                description=f"Extend {'NS' if phase==0 else 'EW'} green by 10 seconds",
                target_phase=phase,
                duration=min(int(state.next_switch_in) + 10, MAX_GREEN),
                estimated_value=ext_val,
                rationale=(
                    f"Current direction pressure={current_pressure:.0f}, "
                    f"other pressure={other_pressure:.0f}. "
                    f"Extending benefits current demand."
                ),
            ))

            # --- Action 2: Shorten current green by 10 s (only if time > MIN_GREEN) ---
            if state.next_switch_in > MIN_GREEN + 10:
                short_val = self._shorten_value(current_pressure, other_pressure, goal)
                candidates.append(CandidateAction(
                    action_id="SHORTEN_GREEN_10",
                    description=f"Shorten {'NS' if phase==0 else 'EW'} green by 10 seconds",
                    target_phase=phase,
                    duration=max(int(state.next_switch_in) - 10, MIN_GREEN),
                    estimated_value=short_val,
                    rationale=(
                        f"Other direction pressure={other_pressure:.0f} is higher. "
                        f"Releasing green sooner benefits the waiting direction."
                    ),
                ))

            # --- Action 3: Hold current timing ---
            hold_val = 0.3 + 0.1 * (current_pressure / total_pressure)
            candidates.append(CandidateAction(
                action_id="HOLD_CURRENT",
                description="Hold current phase timing (no change)",
                target_phase=phase,
                duration=int(state.next_switch_in),
                estimated_value=hold_val,
                rationale="Demand is balanced; no immediate change required.",
            ))

        elif in_yellow or in_red:
            # During yellow/all-red, only option is to let it run out
            candidates.append(CandidateAction(
                action_id="WAIT_TRANSITION",
                description="Allow safety transition to complete",
                target_phase=phase,
                duration=int(state.next_switch_in),
                estimated_value=1.0,   # always execute safety transition
                rationale="Safety: yellow/all-red phase must complete before any change.",
            ))
        else:
            # Fallback
            candidates.append(CandidateAction(
                action_id="HOLD_CURRENT",
                description="Hold current phase",
                target_phase=phase,
                duration=30,
                estimated_value=0.5,
                rationale="Fallback: unknown phase state — maintain current.",
            ))

        # Sort by estimated_value descending
        candidates.sort(key=lambda c: c.estimated_value, reverse=True)
        return candidates

    # ------------------------------------------------------------------
    # Value estimation helpers
    # ------------------------------------------------------------------

    def _extend_value(
        self,
        current_pressure: float,
        other_pressure: float,
        total_pressure: float,
        goal: Goal,
        phase: int,
    ) -> float:
        base = current_pressure / max(total_pressure, 1)
        if goal == Goal.REDUCE_NS_CONGESTION and phase == PHASE_NS_GREEN:
            base += 0.25
        elif goal == Goal.REDUCE_EW_CONGESTION and phase == PHASE_EW_GREEN:
            base += 0.25
        elif goal == Goal.BALANCE_DIRECTIONS:
            # Extending benefits current direction only if it has more pressure
            if current_pressure > other_pressure:
                base += 0.1
            else:
                base -= 0.2
        elif goal == Goal.INCREASE_THROUGHPUT:
            base += 0.1  # more green always moves more cars
        return min(base, 1.0)

    def _shorten_value(
        self,
        current_pressure: float,
        other_pressure: float,
        goal: Goal,
    ) -> float:
        base = other_pressure / max(current_pressure + other_pressure, 1)
        if goal == Goal.BALANCE_DIRECTIONS:
            base += 0.2
        elif goal == Goal.REDUCE_NS_CONGESTION or goal == Goal.REDUCE_EW_CONGESTION:
            base += 0.15
        return min(base, 1.0)
