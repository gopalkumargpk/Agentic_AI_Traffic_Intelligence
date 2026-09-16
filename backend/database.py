"""
database.py
===========
SQLite database setup and access layer using SQLAlchemy (Core, not ORM).

Tables:
  simulation_runs    - Each experiment run
  traffic_states     - Time-series traffic observations
  agent_decisions    - AI agent decision cycles
  performance_metrics - Aggregated performance per run
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional, Any

from sqlalchemy import (
    create_engine, text, Column, Integer, Float, String,
    Text, Boolean, DateTime, MetaData, Table, select, desc
)
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "traffic_intelligence.db"


def get_engine() -> Engine:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{DB_PATH}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    return engine


ENGINE: Engine = get_engine()
metadata = MetaData()

# ==================== TABLE DEFINITIONS ====================

simulation_runs = Table(
    "simulation_runs", metadata,
    Column("id",          Integer, primary_key=True, autoincrement=True),
    Column("run_name",    String(100)),
    Column("controller",  String(20)),      # "fixed" / "agentic"
    Column("demand",      String(30)),
    Column("seed",        Integer),
    Column("duration",    Integer),
    Column("status",      String(20)),      # running / completed / stopped / error
    Column("started_at",  DateTime),
    Column("finished_at", DateTime, nullable=True),
    Column("use_sumo",    Boolean, default=False),
)

traffic_states = Table(
    "traffic_states", metadata,
    Column("id",              Integer, primary_key=True, autoincrement=True),
    Column("run_id",          Integer),
    Column("sim_time",        Float),
    Column("total_vehicles",  Integer),
    Column("avg_waiting_time",Float),
    Column("total_waiting_time", Float),
    Column("total_stopped",   Integer),
    Column("avg_speed",       Float),
    Column("density",         Float),
    Column("throughput_arrived", Integer),
    Column("phase",           Integer),
    Column("phase_name",      String(20)),
    Column("ns_queue",        Float),
    Column("ew_queue",        Float),
    Column("ns_wait",         Float),
    Column("ew_wait",         Float),
    Column("queue_imbalance", Float),
    Column("congestion_level",String(20)),
    Column("recorded_at",     DateTime),
)

agent_decisions = Table(
    "agent_decisions", metadata,
    Column("id",               Integer, primary_key=True, autoincrement=True),
    Column("run_id",           Integer),
    Column("cycle_id",         Integer),
    Column("sim_time",         Float),
    Column("goal",             String(50)),
    Column("goal_priority",    Float),
    Column("goal_reason",      Text),
    Column("selected_action",  String(50)),
    Column("action_description", String(200)),
    Column("action_duration",  Integer),
    Column("decision_basis",   String(30)),
    Column("confidence",       Float),
    Column("q_value",          Float),
    Column("reward",           Float),
    Column("reward_detail",    Text),  # JSON
    Column("reasoning_summary",Text),
    Column("recorded_at",      DateTime),
)

performance_metrics = Table(
    "performance_metrics", metadata,
    Column("id",                    Integer, primary_key=True, autoincrement=True),
    Column("run_id",                Integer),
    Column("controller",            String(20)),
    Column("average_waiting_time",  Float),
    Column("total_waiting_time",    Float),
    Column("max_ns_queue",          Float),
    Column("max_ew_queue",          Float),
    Column("average_queue",         Float),
    Column("throughput",            Integer),
    Column("average_speed",         Float),
    Column("average_reward",        Float, nullable=True),
    Column("num_decisions",         Integer, nullable=True),
    Column("recorded_at",           DateTime),
)


def init_db() -> None:
    """Create all tables if they don't exist."""
    metadata.create_all(ENGINE)
    logger.info(f"Database initialized at {DB_PATH}")


@contextmanager
def get_conn():
    with ENGINE.connect() as conn:
        yield conn
        conn.commit()


# ==================== WRITE OPERATIONS ====================

def create_run(
    run_name: str,
    controller: str,
    demand: str = "medium",
    seed: int = 42,
    duration: int = 3600,
    use_sumo: bool = False,
) -> int:
    with get_conn() as conn:
        result = conn.execute(
            simulation_runs.insert().values(
                run_name=run_name,
                controller=controller,
                demand=demand,
                seed=seed,
                duration=duration,
                status="running",
                started_at=datetime.utcnow(),
                use_sumo=use_sumo,
            )
        )
        return result.inserted_primary_key[0]


def update_run_status(run_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            simulation_runs.update()
            .where(simulation_runs.c.id == run_id)
            .values(status=status, finished_at=datetime.utcnow())
        )


def record_traffic_state(run_id: int, state: dict) -> None:
    with get_conn() as conn:
        conn.execute(traffic_states.insert().values(
            run_id=run_id,
            sim_time=state.get("sim_time", 0),
            total_vehicles=state.get("total_vehicles", 0),
            avg_waiting_time=state.get("average_waiting_time", 0),
            total_waiting_time=state.get("total_waiting_time", 0),
            total_stopped=state.get("total_stopped", 0),
            avg_speed=state.get("average_speed", 0),
            density=state.get("density", 0),
            throughput_arrived=state.get("throughput_arrived", 0),
            phase=state.get("phase", 0),
            phase_name=state.get("phase_name", ""),
            ns_queue=state.get("ns_queue", 0),
            ew_queue=state.get("ew_queue", 0),
            ns_wait=state.get("ns_wait", 0),
            ew_wait=state.get("ew_wait", 0),
            queue_imbalance=state.get("queue_imbalance", 0),
            congestion_level=state.get("congestion_level", "LOW"),
            recorded_at=datetime.utcnow(),
        ))


def record_agent_decision(run_id: int, cycle_log: dict) -> None:
    with get_conn() as conn:
        conn.execute(agent_decisions.insert().values(
            run_id=run_id,
            cycle_id=cycle_log.get("cycle_id", 0),
            sim_time=cycle_log.get("sim_time", 0),
            goal=cycle_log.get("goal", ""),
            goal_priority=cycle_log.get("goal_priority", 0),
            goal_reason=cycle_log.get("goal_reason", ""),
            selected_action=cycle_log.get("selected_action", ""),
            action_description=cycle_log.get("action_description", ""),
            action_duration=cycle_log.get("action_duration", 0),
            decision_basis=cycle_log.get("decision_basis", ""),
            confidence=cycle_log.get("confidence", 0),
            q_value=cycle_log.get("q_value", 0),
            reward=cycle_log.get("reward", 0),
            reward_detail=json.dumps(cycle_log.get("reward_detail", {})),
            reasoning_summary=cycle_log.get("reasoning_summary", ""),
            recorded_at=datetime.utcnow(),
        ))


def record_performance(run_id: int, metrics: dict) -> None:
    with get_conn() as conn:
        conn.execute(performance_metrics.insert().values(
            run_id=run_id,
            controller=metrics.get("controller", ""),
            average_waiting_time=metrics.get("average_waiting_time_s", 0),
            total_waiting_time=metrics.get("total_waiting_time_s", 0),
            max_ns_queue=metrics.get("max_ns_queue", 0),
            max_ew_queue=metrics.get("max_ew_queue", 0),
            average_queue=metrics.get("average_queue", 0),
            throughput=metrics.get("throughput_vehicles", 0),
            average_speed=metrics.get("average_speed_ms", 0),
            average_reward=metrics.get("average_reward", None),
            num_decisions=metrics.get("num_decisions", None),
            recorded_at=datetime.utcnow(),
        ))


# ==================== READ OPERATIONS ====================

def get_recent_traffic_states(run_id: int, limit: int = 100) -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            select(traffic_states)
            .where(traffic_states.c.run_id == run_id)
            .order_by(desc(traffic_states.c.sim_time))
            .limit(limit)
        ).fetchall()
    return [dict(r._mapping) for r in reversed(rows)]


def get_recent_decisions(run_id: int, limit: int = 20) -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            select(agent_decisions)
            .where(agent_decisions.c.run_id == run_id)
            .order_by(desc(agent_decisions.c.sim_time))
            .limit(limit)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r._mapping)
        try:
            d["reward_detail"] = json.loads(d.get("reward_detail") or "{}")
        except Exception:
            d["reward_detail"] = {}
        result.append(d)
    return result


def get_all_runs() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            select(simulation_runs).order_by(desc(simulation_runs.c.started_at))
        ).fetchall()
    return [dict(r._mapping) for r in rows]


def get_run(run_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            select(simulation_runs).where(simulation_runs.c.id == run_id)
        ).fetchone()
    return dict(row._mapping) if row else None


def get_comparison_metrics() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            select(performance_metrics).order_by(desc(performance_metrics.c.recorded_at))
        ).fetchall()
    return [dict(r._mapping) for r in rows]
