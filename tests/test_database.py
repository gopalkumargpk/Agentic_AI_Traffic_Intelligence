"""
tests/test_database.py
Tests for SQLite database operations.
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile

# Override DB path for tests
os.environ.setdefault("TEST_MODE", "1")

from backend.database import (
    init_db, create_run, update_run_status, record_traffic_state,
    record_agent_decision, record_performance,
    get_recent_traffic_states, get_recent_decisions, get_all_runs, get_run
)


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    import backend.database as db_module
    test_db = tmp_path / "test.db"
    engine = __import__("sqlalchemy").create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr(db_module, "ENGINE", engine)
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    db_module.metadata.create_all(engine)
    yield


def _sample_state():
    return {
        "sim_time": 100.0, "total_vehicles": 15, "average_waiting_time": 20.0,
        "total_waiting_time": 300.0, "total_stopped": 5, "average_speed": 6.0,
        "density": 3.5, "throughput_arrived": 30, "phase": 0, "phase_name": "NS_GREEN",
        "ns_queue": 4.0, "ew_queue": 3.0, "ns_wait": 80.0, "ew_wait": 60.0,
        "queue_imbalance": 0.15, "congestion_level": "LOW",
    }


class TestRunCRUD:
    def test_create_run_returns_id(self):
        rid = create_run("test", "fixed", "medium", 42, 1800)
        assert isinstance(rid, int)
        assert rid > 0

    def test_get_run_by_id(self):
        rid = create_run("my_run", "agentic", "high", 99, 3600)
        run = get_run(rid)
        assert run is not None
        assert run["run_name"] == "my_run"
        assert run["controller"] == "agentic"

    def test_update_run_status(self):
        rid = create_run("run2", "fixed", "low", 1, 600)
        update_run_status(rid, "completed")
        run = get_run(rid)
        assert run["status"] == "completed"

    def test_get_all_runs_returns_list(self):
        create_run("r1", "fixed")
        create_run("r2", "agentic")
        runs = get_all_runs()
        assert len(runs) >= 2


class TestTrafficStateRecording:
    def test_record_and_retrieve_traffic_state(self):
        rid = create_run("ts_test", "fixed")
        record_traffic_state(rid, _sample_state())
        states = get_recent_traffic_states(rid, limit=10)
        assert len(states) == 1
        assert states[0]["sim_time"] == 100.0

    def test_multiple_states_ordered_by_sim_time(self):
        rid = create_run("ts_order", "fixed")
        for t in [100, 200, 300]:
            s = _sample_state()
            s["sim_time"] = t
            record_traffic_state(rid, s)
        states = get_recent_traffic_states(rid, limit=10)
        assert len(states) == 3
        times = [s["sim_time"] for s in states]
        assert times == sorted(times)


class TestAgentDecisionRecording:
    def test_record_and_retrieve_decision(self):
        rid = create_run("dec_test", "agentic")
        cycle = {
            "cycle_id": 1, "sim_time": 100.0, "goal": "REDUCE_WAITING_TIME",
            "goal_priority": 0.7, "goal_reason": "High wait", "selected_action": "EXTEND_GREEN_10",
            "action_description": "Extend NS green by 10s", "action_duration": 30,
            "decision_basis": "planner", "confidence": 0.8, "q_value": 0.1,
            "reward": 0.05, "reward_detail": {}, "reasoning_summary": "Test reasoning",
        }
        record_agent_decision(rid, cycle)
        decisions = get_recent_decisions(rid, limit=5)
        assert len(decisions) == 1
        assert decisions[0]["goal"] == "REDUCE_WAITING_TIME"


class TestPerformanceRecording:
    def test_record_performance(self):
        rid = create_run("perf_test", "fixed")
        metrics = {
            "controller": "fixed", "average_waiting_time_s": 25.5,
            "total_waiting_time_s": 12000, "max_ns_queue": 10.0,
            "max_ew_queue": 8.0, "average_queue": 9.0,
            "throughput_vehicles": 450, "average_speed_ms": 5.5,
        }
        record_performance(rid, metrics)
        # No exception = success
