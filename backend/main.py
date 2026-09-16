"""
main.py
=======
FastAPI backend for Agentic AI Traffic Intelligence.

Endpoints:
    GET  /api/status
    GET  /api/traffic
    GET  /api/signals
    GET  /api/agent/state
    GET  /api/agent/decision
    GET  /api/metrics
    GET  /api/history
    GET  /api/runs
    GET  /api/comparison
    GET  /api/stream          (SSE live stream)
    POST /api/simulation/start
    POST /api/simulation/stop
    POST /api/simulation/reset
    POST /api/controller/mode

CORS enabled for React dev server (localhost:5173).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Adjust path so imports work regardless of cwd
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import (
    init_db, create_run, update_run_status, record_traffic_state,
    record_agent_decision, record_performance,
    get_recent_traffic_states, get_recent_decisions,
    get_all_runs, get_run, get_comparison_metrics,
)
from backend.models import (
    SystemStatus, TrafficStateModel, SignalStateModel,
    AgentStateModel, MetricsModel, ComparisonResult, ComparisonRow,
    HistoryPoint, SimulationRunModel, SimulationStartRequest,
    ControllerModeRequest,
)
from simulation.sumo_runner import get_runner, is_sumo_available, verify_sumo_runtime
from traffic_controller.fixed_controller import FixedController
from traffic_controller.adaptive_controller import AdaptiveController
from ai_agent.state import TrafficState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# Global application state
# ============================================================

class AppState:
    def __init__(self):
        self.simulation_running = False
        self.controller_mode = "agentic"    # "fixed" | "agentic"
        self.run_id: Optional[int] = None
        self.runner = None
        self.controller = None
        self.latest_state: Optional[dict] = None
        self.latest_agent_cycle: Optional[dict] = None
        self.metrics: Optional[dict] = None
        self.history: list = []             # ring buffer
        self.sim_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.using_mock = not is_sumo_available()
        self.error_message: str = ""

    def reset(self):
        self.simulation_running = False
        self.run_id = None
        self.runner = None
        self.controller = None
        self.latest_state = None
        self.latest_agent_cycle = None
        self.metrics = None
        self.history = []
        self.error_message = ""


APP_STATE = AppState()


# ============================================================
# Lifespan
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialised.")
    sumo_diag = verify_sumo_runtime(test_connection=True)
    logger.info("--- SUMO Environment Verification ---")
    logger.info(f"  Binary:     {sumo_diag.get('sumo_binary') or 'NOT FOUND'} (version: {sumo_diag.get('sumo_version')})")
    logger.info(f"  SUMO_HOME:  {sumo_diag.get('sumo_home') or 'NOT SET'}")
    logger.info(f"  TraCI:      {'Available' if sumo_diag.get('traci_available') else 'NOT AVAILABLE'} ({sumo_diag.get('traci_location')})")
    logger.info(f"  Connection: {sumo_diag.get('connection_test')}")
    logger.info(f"  Engine:     {'SUMO Simulation' if sumo_diag.get('ready') else 'Mock Simulation Fallback'}")
    APP_STATE.using_mock = not sumo_diag.get("ready", False)
    yield
    # Cleanup on shutdown
    if APP_STATE.simulation_running:
        APP_STATE.stop_event.set()
        if APP_STATE.sim_thread:
            APP_STATE.sim_thread.join(timeout=5)
    logger.info("Backend shutdown complete.")


app = FastAPI(
    title="Agentic AI Traffic Intelligence API",
    description="REST API for the autonomous traffic control prototype.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Simulation background thread
# ============================================================

def _run_simulation(
    request: SimulationStartRequest,
    run_id: int,
    stop_event: threading.Event,
):
    """Background thread that runs the simulation loop."""
    try:
        # Build runner
        runner = get_runner(
            gui=request.use_gui,
            seed=request.seed,
            demand=request.demand,
        )
        APP_STATE.runner = runner
        # Reflect actual runner type: only False if we got a real SumoRunner
        from simulation.sumo_runner import SumoRunner as _SumoRunner
        APP_STATE.using_mock = not isinstance(runner, _SumoRunner)

        if request.controller == "fixed":
            controller = FixedController(
                runner=runner,
                ns_green=request.ns_green,
                ew_green=request.ew_green,
                on_state=lambda s: _on_state(run_id, s),
            )
        else:
            controller = AdaptiveController(
                runner=runner,
                decision_interval=request.decision_interval,
                on_state=lambda s, c: _on_state_with_cycle(run_id, s, c),
                on_cycle=lambda c: _on_cycle(run_id, c),
            )

        APP_STATE.controller = controller
        controller.start()

        sim_end = request.duration
        step_size = 5  # steps per loop iteration (balance speed vs responsiveness)
        steps_done = 0

        while not stop_event.is_set():
            raw_state = runner.get_state()
            if raw_state.get("sim_time", 0) >= sim_end:
                break

            if request.controller == "fixed":
                state = controller.step(step_size)
            else:
                state, _ = controller.step(step_size)

            steps_done += step_size

            # Record every ~30 sim seconds
            if steps_done % 30 < step_size:
                try:
                    raw = runner.get_state()
                    ts = TrafficState.from_runner_dict(raw)
                    record_traffic_state(run_id, ts.to_dict())
                except Exception as e:
                    logger.debug(f"State record error: {e}")

            # Update metrics
            if request.controller == "fixed":
                APP_STATE.metrics = controller.metrics.summary()
            else:
                APP_STATE.metrics = controller.metrics.summary()

            time.sleep(0.02)  # throttle to not peg CPU

        # Final metrics
        if request.controller == "fixed":
            final_metrics = controller.metrics.summary()
        else:
            final_metrics = controller.metrics.summary()

        record_performance(run_id, final_metrics)
        update_run_status(run_id, "completed")
        logger.info(f"Simulation {run_id} completed. Metrics: {final_metrics}")

    except Exception as e:
        logger.exception(f"Simulation error: {e}")
        APP_STATE.error_message = str(e)
        try:
            update_run_status(run_id, "error")
        except Exception:
            pass
    finally:
        try:
            if APP_STATE.controller:
                APP_STATE.controller.stop()
        except Exception:
            pass
        APP_STATE.simulation_running = False


def _on_state(run_id: int, state: TrafficState):
    """Callback: update latest state (fixed controller)."""
    d = state.to_dict()
    with APP_STATE.lock:
        APP_STATE.latest_state = d
        APP_STATE.history.append({
            "sim_time": d["sim_time"],
            "avg_waiting_time": d["average_waiting_time"],
            "ns_queue": d["ns_queue"],
            "ew_queue": d["ew_queue"],
            "throughput": d["throughput_arrived"],
            "avg_speed": d["average_speed"],
            "phase": d["phase"],
            "congestion_level": d["congestion_level"],
        })
        if len(APP_STATE.history) > 500:
            APP_STATE.history = APP_STATE.history[-500:]


def _on_state_with_cycle(run_id: int, state: TrafficState, cycle=None):
    """Callback: update latest state (adaptive controller)."""
    _on_state(run_id, state)


def _on_cycle(run_id: int, cycle_log):
    """Callback: store agent decision cycle."""
    d = cycle_log.to_dict()
    with APP_STATE.lock:
        APP_STATE.latest_agent_cycle = d
    try:
        record_agent_decision(run_id, d)
    except Exception as e:
        logger.debug(f"Decision record error: {e}")


# ============================================================
# API Endpoints
# ============================================================

@app.get("/api/status", response_model=SystemStatus)
def get_status():
    return SystemStatus(
        status="running" if APP_STATE.simulation_running else "idle",
        controller_mode=APP_STATE.controller_mode,
        simulation_running=APP_STATE.simulation_running,
        sim_time=APP_STATE.latest_state.get("sim_time", 0) if APP_STATE.latest_state else 0,
        run_id=APP_STATE.run_id,
        sumo_available=is_sumo_available(),
        using_mock=APP_STATE.using_mock,
        message=APP_STATE.error_message or ("Simulation active" if APP_STATE.simulation_running else "Ready to start"),
    )


@app.get("/api/traffic")
def get_traffic():
    if APP_STATE.latest_state is None:
        return {"message": "No simulation running", "data": None}
    return {"data": APP_STATE.latest_state}


@app.get("/api/signals")
def get_signals():
    s = APP_STATE.latest_state
    if s is None:
        return {"phase": 0, "phase_name": "NS_GREEN", "phase_duration": 30, "next_switch_in": 30, "tl_id": "C"}
    return {
        "phase": s.get("phase", 0),
        "phase_name": s.get("phase_name", "NS_GREEN"),
        "phase_duration": s.get("phase_duration", 30),
        "next_switch_in": s.get("next_switch_in", 30),
        "tl_id": "C",
    }


@app.get("/api/agent/state")
def get_agent_state():
    state = APP_STATE.latest_state
    cycle = APP_STATE.latest_agent_cycle
    if state is None:
        return {"message": "No simulation data yet"}

    learning_stats = {}
    if APP_STATE.controller and hasattr(APP_STATE.controller, "agent"):
        learning_stats = APP_STATE.controller.agent.learning_stats

    return {
        "traffic_state": state,
        "latest_cycle": cycle,
        "learning_stats": learning_stats,
        "controller_mode": APP_STATE.controller_mode,
    }


@app.get("/api/agent/decision")
def get_agent_decision():
    if APP_STATE.latest_agent_cycle is None:
        return {"message": "No agent decisions yet (fixed controller or simulation not started)"}
    return APP_STATE.latest_agent_cycle


@app.get("/api/metrics")
def get_metrics():
    if APP_STATE.metrics is None:
        return {"message": "No metrics yet"}
    return APP_STATE.metrics


@app.get("/api/history")
def get_history(limit: int = 200):
    with APP_STATE.lock:
        hist = APP_STATE.history[-limit:]
    return {"history": hist, "count": len(hist)}


@app.get("/api/runs")
def get_runs():
    runs = get_all_runs()
    return {"runs": runs}


@app.get("/api/comparison")
def get_comparison():
    """Return latest fixed vs agentic metrics comparison."""
    all_metrics = get_comparison_metrics()
    fixed_m = next((m for m in all_metrics if m["controller"] == "fixed"), None)
    agnt_m  = next((m for m in all_metrics if m["controller"] == "agentic"), None)

    def pct(f, a):
        if f is None or a is None or f == 0:
            return None
        return round((f - a) / abs(f) * 100, 1)

    def row(metric, f_val, a_val, unit):
        return ComparisonRow(
            metric=metric,
            fixed=round(f_val, 2) if f_val is not None else None,
            agentic=round(a_val, 2) if a_val is not None else None,
            unit=unit,
            improvement_pct=pct(f_val, a_val),
        )

    rows = [
        row("Average Waiting Time",
            fixed_m["average_waiting_time"] if fixed_m else None,
            agnt_m["average_waiting_time"]  if agnt_m else None,
            "seconds"),
        row("Total Waiting Time",
            fixed_m["total_waiting_time"] if fixed_m else None,
            agnt_m["total_waiting_time"]  if agnt_m else None,
            "seconds"),
        row("Max NS Queue",
            fixed_m["max_ns_queue"] if fixed_m else None,
            agnt_m["max_ns_queue"]  if agnt_m else None,
            "vehicles"),
        row("Max EW Queue",
            fixed_m["max_ew_queue"] if fixed_m else None,
            agnt_m["max_ew_queue"]  if agnt_m else None,
            "vehicles"),
        row("Throughput",
            fixed_m["throughput"] if fixed_m else None,
            agnt_m["throughput"]  if agnt_m else None,
            "vehicles"),
        row("Average Speed",
            fixed_m["average_speed"] if fixed_m else None,
            agnt_m["average_speed"]  if agnt_m else None,
            "m/s"),
    ]

    has_data = fixed_m or agnt_m
    summary = (
        "Run both Fixed and Agentic experiments to populate the comparison table."
        if not has_data
        else "Comparison based on latest completed runs."
    )

    return ComparisonResult(rows=rows, summary=summary)


@app.post("/api/simulation/start")
def start_simulation(request: SimulationStartRequest, background_tasks: BackgroundTasks):
    if APP_STATE.simulation_running:
        raise HTTPException(status_code=409, detail="Simulation already running. Stop it first.")

    APP_STATE.reset()
    APP_STATE.controller_mode = request.controller
    APP_STATE.using_mock = not is_sumo_available()

    run_name = f"{request.controller}_{request.demand}_{datetime.utcnow().strftime('%H%M%S')}"
    run_id = create_run(
        run_name=run_name,
        controller=request.controller,
        demand=request.demand,
        seed=request.seed,
        duration=request.duration,
        use_sumo=is_sumo_available(),
    )
    APP_STATE.run_id = run_id
    APP_STATE.simulation_running = True
    APP_STATE.stop_event.clear()

    # Launch simulation in background thread
    t = threading.Thread(
        target=_run_simulation,
        args=(request, run_id, APP_STATE.stop_event),
        daemon=True,
        name=f"sim-{run_id}",
    )
    t.start()
    APP_STATE.sim_thread = t

    return {
        "message": f"Simulation started",
        "run_id": run_id,
        "controller": request.controller,
        "demand": request.demand,
        "using_mock": APP_STATE.using_mock,
    }


@app.post("/api/simulation/stop")
def stop_simulation():
    if not APP_STATE.simulation_running:
        return {"message": "No simulation running"}
    APP_STATE.stop_event.set()
    if APP_STATE.run_id:
        update_run_status(APP_STATE.run_id, "stopped")
    APP_STATE.simulation_running = False
    return {"message": "Simulation stop signal sent", "run_id": APP_STATE.run_id}


@app.post("/api/simulation/reset")
def reset_simulation():
    if APP_STATE.simulation_running:
        APP_STATE.stop_event.set()
        time.sleep(0.5)
    APP_STATE.reset()
    return {"message": "Simulation state reset"}


@app.post("/api/controller/mode")
def set_controller_mode(request: ControllerModeRequest):
    if request.mode not in ("fixed", "agentic"):
        raise HTTPException(status_code=400, detail="mode must be 'fixed' or 'agentic'")
    if APP_STATE.simulation_running:
        raise HTTPException(status_code=409, detail="Cannot change mode while simulation is running.")
    APP_STATE.controller_mode = request.mode
    return {"message": f"Controller mode set to '{request.mode}'", "mode": request.mode}


# ==================== Server-Sent Events (Live Stream) ====================

async def _sse_generator() -> AsyncGenerator[str, None]:
    """Generate SSE events with current simulation state."""
    while True:
        with APP_STATE.lock:
            state  = APP_STATE.latest_state
            cycle  = APP_STATE.latest_agent_cycle
            metrics = APP_STATE.metrics
            running = APP_STATE.simulation_running

        payload = {
            "running": running,
            "controller": APP_STATE.controller_mode,
            "state": state,
            "cycle": cycle,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(1.0)  # 1 Hz update


@app.get("/api/stream")
async def stream():
    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# Health check
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok", "sumo": is_sumo_available()}


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
