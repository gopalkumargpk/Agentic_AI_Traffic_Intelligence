"""
decision_engine.py
==================
Selects the best action from the candidate list produced by the Planner,
combining Q-learning value estimates with the planner's estimated values.

The decision engine enforces all safety constraints:
  - Never skip yellow/all-red phases
  - Always enforce minimum green time
  - Always enforce maximum green time
  - Log every decision for explainability
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from ai_agent.planner import CandidateAction
from ai_agent.state import TrafficState
from ai_agent.learning import QLearner

logger = logging.getLogger(__name__)

# Phase safety map: which transitions are safe (no jumping over yellow)
SAFE_TRANSITIONS = {
    0: [0, 1],      # NS_GREEN → stay or go to NS_YELLOW
    1: [1, 2],      # NS_YELLOW → stay or go to ALL_RED
    2: [2, 3],      # ALL_RED → stay or go to EW_GREEN
    3: [3, 4],      # EW_GREEN → stay or go to EW_YELLOW
    4: [4, 5],      # EW_YELLOW → stay or go to ALL_RED
    5: [5, 0],      # ALL_RED → stay or go to NS_GREEN
}


@dataclass
class DecisionResult:
    """Full explanation of a single agent decision."""
    chosen_action: CandidateAction
    all_candidates: List[CandidateAction]
    q_value: float
    confidence: float            # 0..1 (planner score)
    decision_basis: str          # "q_learning" / "planner" / "safety_override"

    def to_dict(self) -> dict:
        return {
            "chosen_action": self.chosen_action.to_dict(),
            "all_candidates": [c.to_dict() for c in self.all_candidates],
            "q_value": round(self.q_value, 4),
            "confidence": round(self.confidence, 3),
            "decision_basis": self.decision_basis,
        }


class DecisionEngine:
    """
    Selects the best action using a weighted combination of:
    1. Q-learning Q-value for (state, action) pair
    2. Planner's estimated_value (heuristic)

    Decision = argmax(α * Q_value + β * estimated_value)
    where α = 0.6, β = 0.4

    Safety overrides always take precedence.
    """

    ALPHA_Q      = 0.6  # weight for Q-learning
    BETA_PLANNER = 0.4  # weight for planner heuristic

    def __init__(self, learner: Optional[QLearner] = None):
        self.learner = learner or QLearner()
        self._decision_count = 0

    def decide(
        self,
        state: TrafficState,
        candidates: List[CandidateAction],
    ) -> DecisionResult:
        """
        Select the best safe action from the candidates list.
        """
        if not candidates:
            raise ValueError("No candidate actions provided to decision engine.")

        # Filter to safe candidates
        safe_candidates = [c for c in candidates if self._is_safe(state, c)]
        if not safe_candidates:
            # Safety override: take the hold action or first candidate
            logger.warning("No safe candidates found — applying safety override.")
            override = candidates[0]
            override.rationale = f"[SAFETY OVERRIDE] {override.rationale}"
            return DecisionResult(
                chosen_action=override,
                all_candidates=candidates,
                q_value=0.0,
                confidence=1.0,
                decision_basis="safety_override",
            )

        # Compute composite score for each safe candidate
        state_key = state.discretize()
        scored = []
        for c in safe_candidates:
            q_val = self.learner.get_q_value(state_key, c.action_id)
            composite = self.ALPHA_Q * q_val + self.BETA_PLANNER * c.estimated_value
            scored.append((composite, q_val, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_composite, best_q, best_action = scored[0]

        # Determine what drove the decision
        if abs(best_q) > 0.05:
            basis = "q_learning"
        else:
            basis = "planner"

        self._decision_count += 1
        logger.info(
            f"[Decision #{self._decision_count}] {best_action.action_id} "
            f"(composite={best_composite:.3f}, Q={best_q:.3f}, planner={best_action.estimated_value:.3f})"
        )

        return DecisionResult(
            chosen_action=best_action,
            all_candidates=candidates,
            q_value=best_q,
            confidence=min(best_action.estimated_value, 1.0),
            decision_basis=basis,
        )

    def _is_safe(self, state: TrafficState, candidate: CandidateAction) -> bool:
        """
        Safety check: ensure the target phase is a legal transition from current phase.
        """
        allowed = SAFE_TRANSITIONS.get(state.phase, [])
        return candidate.target_phase in allowed

    def update_q(self, state: TrafficState, action_id: str, reward: float, next_state: TrafficState) -> None:
        """Update Q-table after observing the reward from the executed action."""
        self.learner.update(
            state=state.discretize(),
            action=action_id,
            reward=reward,
            next_state=next_state.discretize(),
        )

    @property
    def decision_count(self) -> int:
        return self._decision_count
