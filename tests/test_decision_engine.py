"""
tests/test_decision_engine.py
Tests for the decision engine and signal safety constraints.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from ai_agent.state import TrafficState
from ai_agent.goal_manager import GoalManager, Goal
from ai_agent.planner import Planner, CandidateAction
from ai_agent.decision_engine import DecisionEngine, SAFE_TRANSITIONS
from ai_agent.learning import QLearner


def _make_state(**kwargs) -> TrafficState:
    defaults = dict(
        sim_time=300, total_vehicles=10, total_waiting_time=100,
        average_waiting_time=15.0, total_stopped=4, average_speed=6.0,
        density=3.0, throughput_departed=30, throughput_arrived=28,
        phase=0, phase_name="NS_GREEN", phase_duration=30,
        next_switch_in=20, directions={},
        ns_queue=4.0, ew_queue=3.0, ns_wait=80.0, ew_wait=60.0,
        queue_imbalance=0.15, congestion_level="LOW",
    )
    defaults.update(kwargs)
    return TrafficState(**defaults)


class TestSafeTransitions:
    def test_safe_transitions_complete(self):
        """Verify the safe transitions table covers all 6 phases."""
        assert set(SAFE_TRANSITIONS.keys()) == {0, 1, 2, 3, 4, 5}

    def test_cannot_go_from_green_to_green(self):
        """NS_GREEN → EW_GREEN is not a safe transition (must go through yellow)."""
        assert 3 not in SAFE_TRANSITIONS[0]

    def test_yellow_leads_to_all_red(self):
        assert 2 in SAFE_TRANSITIONS[1]   # NS_YELLOW → ALL_RED

    def test_all_red_leads_to_next_green(self):
        assert 3 in SAFE_TRANSITIONS[2]   # ALL_RED → EW_GREEN


class TestPlanner:
    def test_generates_candidates_in_green_phase(self):
        state = _make_state(phase=0, next_switch_in=25)
        planner = Planner()
        candidates = planner.generate_candidates(state, Goal.MAINTAIN_FLOW)
        assert len(candidates) > 0

    def test_generates_wait_transition_in_yellow(self):
        state = _make_state(phase=1, next_switch_in=3)
        planner = Planner()
        candidates = planner.generate_candidates(state, Goal.MAINTAIN_FLOW)
        assert any(c.action_id == "WAIT_TRANSITION" for c in candidates)

    def test_candidates_sorted_by_estimated_value(self):
        state = _make_state(phase=0, next_switch_in=25)
        planner = Planner()
        candidates = planner.generate_candidates(state, Goal.REDUCE_NS_CONGESTION)
        values = [c.estimated_value for c in candidates]
        assert values == sorted(values, reverse=True)

    def test_extend_action_has_valid_duration(self):
        state = _make_state(phase=0, next_switch_in=20)
        planner = Planner()
        candidates = planner.generate_candidates(state, Goal.MAINTAIN_FLOW)
        extend = next((c for c in candidates if c.action_id == "EXTEND_GREEN_10"), None)
        if extend:
            assert extend.duration >= 10  # MIN_GREEN
            assert extend.duration <= 60  # MAX_GREEN


class TestDecisionEngine:
    def test_returns_decision_result(self):
        engine = DecisionEngine()
        state = _make_state(phase=0, next_switch_in=25)
        planner = Planner()
        candidates = planner.generate_candidates(state, Goal.MAINTAIN_FLOW)
        result = engine.decide(state, candidates)
        assert result is not None
        assert result.chosen_action is not None

    def test_raises_on_empty_candidates(self):
        engine = DecisionEngine()
        state = _make_state(phase=0)
        with pytest.raises(ValueError):
            engine.decide(state, [])

    def test_selected_action_is_safe(self):
        """The selected action's target_phase must be a valid transition."""
        engine = DecisionEngine()
        state = _make_state(phase=0, next_switch_in=25)
        planner = Planner()
        candidates = planner.generate_candidates(state, Goal.REDUCE_NS_CONGESTION)
        result = engine.decide(state, candidates)
        allowed = SAFE_TRANSITIONS.get(state.phase, [])
        assert result.chosen_action.target_phase in allowed

    def test_decision_count_increments(self):
        engine = DecisionEngine()
        state = _make_state(phase=0, next_switch_in=25)
        planner = Planner()
        candidates = planner.generate_candidates(state, Goal.MAINTAIN_FLOW)
        engine.decide(state, candidates)
        engine.decide(state, candidates)
        assert engine.decision_count == 2


class TestGoalManager:
    def test_returns_goal_assessment(self):
        gm = GoalManager()
        state = _make_state()
        assessment = gm.evaluate(state)
        assert assessment is not None
        assert assessment.goal in Goal.__members__.values()

    def test_high_ns_queue_triggers_ns_goal(self):
        gm = GoalManager()
        state = _make_state(ns_queue=20.0, ew_queue=2.0)
        assessment = gm.evaluate(state)
        assert assessment.goal == Goal.REDUCE_NS_CONGESTION

    def test_high_ew_queue_triggers_ew_goal(self):
        gm = GoalManager()
        state = _make_state(ns_queue=2.0, ew_queue=20.0)
        assessment = gm.evaluate(state)
        assert assessment.goal == Goal.REDUCE_EW_CONGESTION

    def test_goal_priority_within_bounds(self):
        gm = GoalManager()
        state = _make_state(average_waiting_time=80.0)
        assessment = gm.evaluate(state)
        assert 0.0 <= assessment.priority <= 1.0


class TestQLearner:
    def test_initial_q_value_zero(self):
        learner = QLearner()
        learner.reset()
        q = learner.get_q_value((0, 0, 0, 0, 0), "HOLD_CURRENT")
        assert q == 0.0

    def test_update_changes_q_value(self):
        learner = QLearner()
        learner.reset()
        state = (1, 1, 2, 0, 0)
        learner.update(state, "EXTEND_GREEN_10", reward=0.5, next_state=(1, 0, 2, 0, 0))
        q = learner.get_q_value(state, "EXTEND_GREEN_10")
        assert q > 0.0

    def test_positive_reward_increases_q(self):
        learner = QLearner()
        learner.reset()
        state = (2, 3, 1, 0, 3)
        before = learner.get_q_value(state, "HOLD_CURRENT")
        learner.update(state, "HOLD_CURRENT", reward=1.0, next_state=state)
        after = learner.get_q_value(state, "HOLD_CURRENT")
        assert after > before

    def test_negative_reward_decreases_q(self):
        learner = QLearner()
        learner.reset()
        state = (2, 3, 1, 0, 3)
        learner.update(state, "HOLD_CURRENT", reward=0.5, next_state=state)
        before = learner.get_q_value(state, "HOLD_CURRENT")
        learner.update(state, "HOLD_CURRENT", reward=-1.0, next_state=state)
        after = learner.get_q_value(state, "HOLD_CURRENT")
        assert after < before
