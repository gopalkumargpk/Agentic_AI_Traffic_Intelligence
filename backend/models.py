"""
models.py
=========
Pydantic models for FastAPI request/response validation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ==================== REQUEST MODELS ====================

class SimulationStartRequest(BaseModel):
    controller: str = Field("agentic", description="'fixed' or 'agentic'")
    demand: str = Field("medium", description="'low'|'medium'|'high'|'asymmetric_ns'|'asymmetric_ew'")
    duration: int = Field(3600, ge=60, le=7200, description="Simulation duration in seconds")
    seed: int = Field(42, ge=0, description="Random seed")
    decision_interval: int = Field(10, ge=5, le=60, description="AI decision interval (agentic only)")
    ns_green: int = Field(30, ge=10, le=60, description="NS green time (fixed only)")
    ew_green: int = Field(30, ge=10, le=60, description="EW green time (fixed only)")
    use_gui: bool = Field(False, description="Open SUMO GUI (requires SUMO)")


class ControllerModeRequest(BaseModel):
    mode: str = Field(..., description="'fixed' or 'agentic'")


# ==================== RESPONSE MODELS ====================

class SystemStatus(BaseModel):
    status: str
    controller_mode: str
    simulation_running: bool
    sim_time: float
    run_id: Optional[int]
    sumo_available: bool
    using_mock: bool
    message: str


class DirectionStatsModel(BaseModel):
    direction: str
    queue_length: float
    waiting_time: float
    vehicle_count: int
    stopped: int


class TrafficStateModel(BaseModel):
    sim_time: float
    total_vehicles: int
    total_waiting_time: float
    average_waiting_time: float
    total_stopped: int
    average_speed: float
    density: float
    throughput_departed: int
    throughput_arrived: int
    phase: int
    phase_name: str
    phase_duration: float
    next_switch_in: float
    ns_queue: float
    ew_queue: float
    ns_wait: float
    ew_wait: float
    queue_imbalance: float
    congestion_level: str
    directions: Dict[str, DirectionStatsModel] = {}


class SignalStateModel(BaseModel):
    phase: int
    phase_name: str
    phase_duration: float
    next_switch_in: float
    tl_id: str = "C"


class AgentStateModel(BaseModel):
    cycle_id: int
    sim_time: float
    goal: str
    goal_priority: float
    goal_reason: str
    selected_action: str
    action_description: str
    action_duration: int
    decision_basis: str
    confidence: float
    q_value: float
    reward: float
    reward_detail: Dict[str, Any] = {}
    reasoning_summary: str
    learning_stats: Dict[str, Any] = {}


class MetricsModel(BaseModel):
    controller: str
    average_waiting_time_s: float
    total_waiting_time_s: float
    max_ns_queue: float
    max_ew_queue: float
    average_queue: float
    throughput_vehicles: int
    average_speed_ms: float
    average_reward: Optional[float] = None
    num_decisions: Optional[int] = None


class ComparisonRow(BaseModel):
    metric: str
    fixed: Optional[float]
    agentic: Optional[float]
    unit: str
    improvement_pct: Optional[float]


class ComparisonResult(BaseModel):
    rows: List[ComparisonRow]
    summary: str


class HistoryPoint(BaseModel):
    sim_time: float
    avg_waiting_time: float
    ns_queue: float
    ew_queue: float
    throughput: int
    avg_speed: float
    phase: int
    congestion_level: str


class SimulationRunModel(BaseModel):
    id: int
    run_name: str
    controller: str
    demand: str
    seed: int
    duration: int
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    use_sumo: bool
