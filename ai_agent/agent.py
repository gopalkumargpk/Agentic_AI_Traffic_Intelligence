"""
agent.py
========
Main Agentic AI orchestrator.

Implements the complete closed-loop control cycle:

    OBSERVE → UNDERSTAND → GOAL → PLAN → DECIDE → EXECUTE → MEASURE → REWARD → LEARN → NEXT

This is the central research contribution:
an autonomous, goal-driven, learning traffic-control agent
that operates as an intelligence layer over the traffic simulator.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ai_agent.state import TrafficState
from ai_agent.goal_manager import GoalManager, GoalAssessment, Goal
from ai_agent.planner import Planner, CandidateAction
from ai_agent.decision_engine import DecisionEngine, DecisionResult
from ai_agent.reward import calculate_reward, RewardResult
from ai_agent.learning import QLearner

logger = logging.getLogger(__name__)


@dataclass
class AgentCycleLog:
    """
    Full record of one agent decision cycle — for explainability and database storage.
    """
    cycle_id: int
    timestamp: str
    sim_time: float

    # Observe
    observed_state: dict

    # Goal
    goal: str
    goal_priority: float
    goal_reason: str

    # Plan & Decide
    candidates: List[dict]
    selected_action: str
    action_description: str
    action_duration: int
    decision_basis: str
    confidence: float
    q_value: float

    # Reward & Learn
    reward: float
    reward_detail: dict
    q_update_applied: bool

    # Summary for display
    reasoning_summary: str

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "sim_time": self.sim_time,
            "goal": self.goal,
            "goal_priority": self.goal_priority,
            "goal_reason": self.goal_reason,
            "selected_action": self.selected_action,
            "action_description": self.action_description,
            "action_duration": self.action_duration,
            "decision_basis": self.decision_basis,
            "confidence": self.confidence,
            "q_value": self.q_value,
            "reward": self.reward,
            "reward_detail": self.reward_detail,
            "reasoning_summary": self.reasoning_summary,
            "observed_state": self.observed_state,
            "candidates": self.candidates,
        }


class AgentController:
    """
    Autonomous Agentic AI traffic controller.

    Usage:
        agent = AgentController(runner)
        agent.start()
        while simulation_running:
            agent.step()          # runs one agent cycle
        agent.stop()
    """

    DECISION_INTERVAL = 10   # seconds between agent decisions

    def __init__(
        self,
        runner,
        decision_interval: int = DECISION_INTERVAL,
        on_cycle_complete: Optional[Callable[[AgentCycleLog], None]] = None,
    ):
        self.runner = runner
        self.decision_interval = decision_interval
        self.on_cycle_complete = on_cycle_complete  # callback (e.g., save to DB)

        self._goal_manager   = GoalManager()
        self._planner        = Planner()
        self._learner        = QLearner()
        self._decision_engine = DecisionEngine(learner=self._learner)

        self._cycle_id        = 0
        self._prev_state: Optional[TrafficState] = None
        self._last_action_id: Optional[str] = None
        self._last_state_key: Optional[tuple] = None
        self._sim_step_counter = 0
        self._history: List[AgentCycleLog] = []
        self._latest_cycle: Optional[AgentCycleLog] = None
        self._running = False

        # Cumulative performance metrics
        self._total_reward = 0.0
        self._num_cycles   = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self.runner.start()
        self._running = True
        logger.info("AgentController started.")

    def stop(self) -> None:
        self._running = False
        self.runner.stop()
        self._learner.save()
        logger.info(f"AgentController stopped after {self._cycle_id} cycles.")

    # ------------------------------------------------------------------
    # Main step: advance sim + run agent cycle every DECISION_INTERVAL
    # ------------------------------------------------------------------

    def step(self, sim_steps: int = 1) -> Optional[AgentCycleLog]:
        """
        Advance the simulation by `sim_steps` seconds.
        Run an agent decision cycle every DECISION_INTERVAL steps.
        Returns AgentCycleLog if a decision was made, else None.
        """
        self.runner.step(sim_steps)
        self._sim_step_counter += sim_steps

        if self._sim_step_counter >= self.decision_interval:
            self._sim_step_counter = 0
            return self._run_cycle()
        return None

    # ------------------------------------------------------------------
    # Agent decision cycle (the core closed-loop)
    # ------------------------------------------------------------------

    def _run_cycle(self) -> AgentCycleLog:
        self._cycle_id += 1
        ts = datetime.utcnow().isoformat()

        # ---- STEP 1: OBSERVE ----
        raw_state = self.runner.get_state()
        state = TrafficState.from_runner_dict(raw_state)
        logger.debug(f"[Cycle {self._cycle_id}] Observed: t={state.sim_time}, "
                     f"ns_q={state.ns_queue}, ew_q={state.ew_queue}, "
                     f"avg_wait={state.average_waiting_time:.1f}s")

        # ---- STEP 2: CALCULATE REWARD (from previous action) ----
        reward_result: RewardResult = calculate_reward(self._prev_state, state)
        self._total_reward += reward_result.total_reward
        self._num_cycles += 1

        # ---- STEP 3: LEARN (Q-update for previous action) ----
        q_updated = False
        if (
            self._prev_state is not None
            and self._last_action_id is not None
            and self._last_state_key is not None
        ):
            self._decision_engine.update_q(
                self._prev_state,
                self._last_action_id,
                reward_result.total_reward,
                state,
            )
            q_updated = True

        # ---- STEP 4: GOAL SELECTION ----
        goal_assessment: GoalAssessment = self._goal_manager.evaluate(state)

        # ---- STEP 5: PLAN ----
        candidates: List[CandidateAction] = self._planner.generate_candidates(
            state, goal_assessment.goal
        )

        # ---- STEP 6: DECIDE ----
        decision: DecisionResult = self._decision_engine.decide(state, candidates)
        chosen = decision.chosen_action

        # ---- STEP 7: EXECUTE ----
        self.runner.set_phase(chosen.target_phase, chosen.duration)
        logger.info(
            f"[Cycle {self._cycle_id}] EXECUTE: {chosen.action_id} "
            f"(phase={chosen.target_phase}, dur={chosen.duration}s) | "
            f"reward={reward_result.total_reward:.3f}"
        )

        # ---- STEP 8: BUILD REASONING SUMMARY ----
        reasoning = self._build_reasoning(
            state, goal_assessment, candidates, decision, reward_result
        )

        # ---- STEP 9: LOG ----
        cycle_log = AgentCycleLog(
            cycle_id=self._cycle_id,
            timestamp=ts,
            sim_time=state.sim_time,
            observed_state=state.to_dict(),
            goal=goal_assessment.goal.value,
            goal_priority=goal_assessment.priority,
            goal_reason=goal_assessment.reason,
            candidates=[c.to_dict() for c in candidates],
            selected_action=chosen.action_id,
            action_description=chosen.description,
            action_duration=chosen.duration,
            decision_basis=decision.decision_basis,
            confidence=decision.confidence,
            q_value=decision.q_value,
            reward=reward_result.total_reward,
            reward_detail=reward_result.to_dict(),
            q_update_applied=q_updated,
            reasoning_summary=reasoning,
        )

        # ---- STEP 10: CALLBACK / DB SAVE ----
        if self.on_cycle_complete:
            try:
                self.on_cycle_complete(cycle_log)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        self._latest_cycle = cycle_log
        self._history.append(cycle_log)
        if len(self._history) > 500:
            self._history = self._history[-500:]

        # ---- STEP 11: UPDATE STATE FOR NEXT CYCLE ----
        self._prev_state    = state
        self._last_action_id = chosen.action_id
        self._last_state_key = state.discretize()

        return cycle_log

    # ------------------------------------------------------------------
    # Reasoning text (explainability)
    # ------------------------------------------------------------------

    def _build_reasoning(
        self,
        state: TrafficState,
        goal: GoalAssessment,
        candidates: List[CandidateAction],
        decision: DecisionResult,
        reward: RewardResult,
    ) -> str:
        lines = [
            f"Goal: {goal.goal.value} (priority={goal.priority:.2f})",
            f"Reason: {goal.reason}",
            f"",
            f"Traffic state: NS_queue={state.ns_queue:.0f}, EW_queue={state.ew_queue:.0f}, "
            f"avg_wait={state.average_waiting_time:.1f}s, speed={state.average_speed:.1f}m/s",
            f"Congestion level: {state.congestion_level}",
            f"",
            f"Candidates evaluated: {len(candidates)}",
            f"Selected: {decision.chosen_action.action_id} ({decision.decision_basis})",
            f"Rationale: {decision.chosen_action.rationale}",
            f"",
            f"Reward: {reward.total_reward:+.4f}",
            f"  ΔWait={reward.delta_avg_wait:+.2f}s, "
            f"  ΔNS_q={reward.delta_ns_queue:+.1f}, "
            f"  ΔEW_q={reward.delta_ew_queue:+.1f}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Status accessors
    # ------------------------------------------------------------------

    @property
    def latest_cycle(self) -> Optional[AgentCycleLog]:
        return self._latest_cycle

    @property
    def average_reward(self) -> float:
        return self._total_reward / max(self._num_cycles, 1)

    @property
    def learning_stats(self) -> dict:
        return self._learner.get_stats()

    def get_current_state_dict(self) -> dict:
        if self._prev_state:
            return self._prev_state.to_dict()
        return {}

    def is_running(self) -> bool:
        return self._running
