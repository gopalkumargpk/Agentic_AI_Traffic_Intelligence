"""
tests/test_reward.py
Tests for the reward function.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from ai_agent.state import TrafficState
from ai_agent.reward import calculate_reward, RewardResult, ALPHA, BETA, GAMMA


def _make_state(**kwargs) -> TrafficState:
    """Helper to create a TrafficState with given field overrides."""
    defaults = dict(
        sim_time=100,
        total_vehicles=20,
        total_waiting_time=400,
        average_waiting_time=20.0,
        total_stopped=8,
        average_speed=5.0,
        density=4.0,
        throughput_departed=50,
        throughput_arrived=45,
        phase=0,
        phase_name="NS_GREEN",
        phase_duration=30,
        next_switch_in=15,
        directions={},
        ns_queue=5.0,
        ew_queue=5.0,
        ns_wait=100.0,
        ew_wait=100.0,
        queue_imbalance=0.0,
        congestion_level="MEDIUM",
    )
    defaults.update(kwargs)
    return TrafficState(**defaults)


class TestRewardFirstStep:
    def test_reward_zero_on_first_step(self):
        """With no previous state, reward must be 0.0."""
        state = _make_state()
        result = calculate_reward(None, state)
        assert result.total_reward == 0.0

    def test_all_components_zero_on_first_step(self):
        state = _make_state()
        result = calculate_reward(None, state)
        assert result.waiting_time_component == 0.0
        assert result.ns_queue_component == 0.0
        assert result.ew_queue_component == 0.0


class TestRewardImprovement:
    def test_positive_reward_when_wait_decreases(self):
        prev = _make_state(average_waiting_time=50.0)
        curr = _make_state(average_waiting_time=30.0)
        result = calculate_reward(prev, curr)
        assert result.total_reward > 0
        assert result.waiting_time_component > 0

    def test_negative_reward_when_wait_increases(self):
        prev = _make_state(average_waiting_time=20.0)
        curr = _make_state(average_waiting_time=60.0)
        result = calculate_reward(prev, curr)
        assert result.waiting_time_component < 0

    def test_positive_reward_when_ns_queue_decreases(self):
        prev = _make_state(ns_queue=15.0, ew_queue=5.0)
        curr = _make_state(ns_queue=5.0,  ew_queue=5.0)
        result = calculate_reward(prev, curr)
        assert result.ns_queue_component > 0

    def test_positive_reward_when_throughput_increases(self):
        prev = _make_state(throughput_arrived=100)
        curr = _make_state(throughput_arrived=115)
        result = calculate_reward(prev, curr)
        assert result.throughput_component > 0


class TestRewardBounds:
    def test_reward_within_minus1_plus1(self):
        prev = _make_state(average_waiting_time=0.0, ns_queue=0.0, ew_queue=0.0)
        curr = _make_state(average_waiting_time=120.0, ns_queue=20.0, ew_queue=20.0)
        result = calculate_reward(prev, curr)
        assert -1.0 <= result.total_reward <= 1.0

    def test_reward_structure(self):
        prev = _make_state()
        curr = _make_state(average_waiting_time=10.0)
        result = calculate_reward(prev, curr)
        assert isinstance(result, RewardResult)
        assert hasattr(result, 'total_reward')
        assert hasattr(result, 'waiting_time_component')
        assert hasattr(result, 'ns_queue_component')

    def test_to_dict_keys(self):
        result = calculate_reward(None, _make_state())
        d = result.to_dict()
        required = {'total_reward', 'waiting_time_component', 'throughput_component', 'delta_avg_wait'}
        assert required.issubset(d.keys())


class TestRewardImbalancePenalty:
    def test_high_imbalance_reduces_reward(self):
        s_balanced   = _make_state(queue_imbalance=0.0)
        s_imbalanced = _make_state(queue_imbalance=0.8)
        prev = _make_state()
        r1 = calculate_reward(prev, s_balanced)
        r2 = calculate_reward(prev, s_imbalanced)
        assert r1.imbalance_component > r2.imbalance_component
