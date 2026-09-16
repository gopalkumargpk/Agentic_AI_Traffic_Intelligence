"""
tests/test_api.py
Tests for FastAPI endpoints (without running full simulation).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

# Import app after path setup
from backend.main import app, APP_STATE


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_app_state():
    """Reset global state before each test."""
    APP_STATE.reset()
    APP_STATE.simulation_running = False
    yield
    APP_STATE.reset()


class TestHealthAndStatus:
    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "sumo" in data

    def test_status_endpoint(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert "simulation_running" in data
        assert "controller_mode" in data
        assert "sumo_available" in data

    def test_status_idle_by_default(self, client):
        r = client.get("/api/status")
        assert r.json()["simulation_running"] == False


class TestTrafficAndSignals:
    def test_traffic_returns_none_when_no_sim(self, client):
        r = client.get("/api/traffic")
        assert r.status_code == 200

    def test_signals_endpoint(self, client):
        r = client.get("/api/signals")
        assert r.status_code == 200
        data = r.json()
        assert "phase" in data
        assert "phase_name" in data


class TestAgentEndpoints:
    def test_agent_state_no_sim(self, client):
        r = client.get("/api/agent/state")
        assert r.status_code == 200

    def test_agent_decision_no_sim(self, client):
        r = client.get("/api/agent/decision")
        assert r.status_code == 200


class TestSimulationControl:
    def test_stop_when_not_running(self, client):
        r = client.post("/api/simulation/stop")
        assert r.status_code == 200

    def test_reset_endpoint(self, client):
        r = client.post("/api/simulation/reset")
        assert r.status_code == 200

    def test_set_controller_mode_valid(self, client):
        r = client.post("/api/controller/mode", json={"mode": "fixed"})
        assert r.status_code == 200
        assert r.json()["mode"] == "fixed"

    def test_set_controller_mode_invalid(self, client):
        r = client.post("/api/controller/mode", json={"mode": "invalid"})
        assert r.status_code == 400

    def test_history_endpoint(self, client):
        r = client.get("/api/history")
        assert r.status_code == 200
        data = r.json()
        assert "history" in data

    def test_comparison_endpoint(self, client):
        r = client.get("/api/comparison")
        assert r.status_code == 200
        data = r.json()
        assert "rows" in data
        assert "summary" in data

    def test_runs_endpoint(self, client):
        r = client.get("/api/runs")
        assert r.status_code == 200


class TestSimulationStart:
    def test_start_simulation_valid(self, client):
        payload = {
            "controller": "agentic",
            "demand": "low",
            "duration": 60,
            "seed": 1,
            "decision_interval": 10,
            "ns_green": 30,
            "ew_green": 30,
            "use_gui": False,
        }
        r = client.post("/api/simulation/start", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "run_id" in data
        # Cleanup
        client.post("/api/simulation/stop")

    def test_start_twice_conflicts(self, client):
        payload = {"controller": "fixed", "demand": "low", "duration": 300,
                   "seed": 1, "decision_interval": 10, "ns_green": 30, "ew_green": 30, "use_gui": False}
        client.post("/api/simulation/start", json=payload)
        r = client.post("/api/simulation/start", json=payload)
        assert r.status_code == 409
        client.post("/api/simulation/stop")
