# ARCHITECTURE.md
# Agentic AI Traffic Intelligence — Technical Architecture

## System Overview

The Agentic AI Traffic Intelligence prototype is structured as a three-tier system:

1. **Simulation Layer** — SUMO traffic simulator (or MockSumoRunner) producing real-time traffic data
2. **Intelligence Layer** — The agentic AI operating as a closed-loop controller
3. **Presentation Layer** — FastAPI REST API + React dashboard for monitoring and control

---

## Component Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                             │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  React Dashboard (Vite, Port 5173)                          │  │
│  │  Header | Status | Traffic | Signal | Agent | Metrics       │  │
│  │  Charts (Recharts) | Comparison Table                       │  │
│  │  SSE live stream + 5s polling                               │  │
│  └───────────────────────────┬─────────────────────────────────┘  │
└──────────────────────────────┼─────────────────────────────────────┘
                               | HTTP / SSE (Port 8000)
┌──────────────────────────────┼─────────────────────────────────────┐
│                     BACKEND LAYER                                  │
│  ┌───────────────────────────▼─────────────────────────────────┐  │
│  │  FastAPI (backend/main.py)                                  │  │
│  │  15 REST endpoints + SSE stream                             │  │
│  │  Background simulation thread                               │  │
│  │  CORS: localhost:5173                                       │  │
│  └────────────────┬──────────────────────────┬─────────────────┘  │
│                   |                          |                      │
│  ┌────────────────▼───────┐  ┌──────────────▼──────────────────┐  │
│  │  SQLAlchemy / SQLite   │  │  Pydantic Models (models.py)    │  │
│  │  Tables:               │  │  SystemStatus, TrafficState,    │  │
│  │  - simulation_runs     │  │  AgentState, Metrics,           │  │
│  │  - traffic_states      │  │  ComparisonResult, ...          │  │
│  │  - agent_decisions     │  └─────────────────────────────────┘  │
│  │  - performance_metrics │                                         │
│  └────────────────────────┘                                         │
└──────────────────────────────────────────────────────────────────────┘
                               | Python in-process
┌──────────────────────────────┼─────────────────────────────────────┐
│                     INTELLIGENCE LAYER                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  AdaptiveController / FixedController                       │  │
│  │  (traffic_controller/)                                      │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
│                             |                                        │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │  AgentController (ai_agent/agent.py)                        │  │
│  │                                                             │  │
│  │  OBSERVE ─► UNDERSTAND ─► GOAL ─► PLAN ─► DECIDE           │  │
│  │     ▲                                         |             │  │
│  │     |                                         |             │  │
│  │  LEARN ◄── REWARD ◄── MEASURE ◄── EXECUTE ◄──┘             │  │
│  │                                                             │  │
│  │  Components:                                                │  │
│  │  ├── state.py       (TrafficState, DirectionState)          │  │
│  │  ├── goal_manager.py (GoalManager, GoalAssessment)          │  │
│  │  ├── planner.py     (Planner, CandidateAction)              │  │
│  │  ├── decision_engine.py (DecisionEngine, DecisionResult)    │  │
│  │  ├── reward.py      (calculate_reward, RewardResult)        │  │
│  │  └── learning.py    (QLearner, Q-table)                     │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
└──────────────────────────────┼─────────────────────────────────────┘
                               | TraCI protocol / Mock
┌──────────────────────────────┼─────────────────────────────────────┐
│                     SIMULATION LAYER                               │
│  ┌───────────────────────────▼─────────────────────────────────┐  │
│  │  SumoRunner (simulation/sumo_runner.py)                     │  │
│  │  or                                                         │  │
│  │  MockSumoRunner (automatic fallback)                        │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
│                             |                                        │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │  SUMO Scenario (simulation/sumo/)                           │  │
│  │  network.net.xml    4-way intersection, 4 approaches        │  │
│  │  routes.rou.xml     12 turning movements, 5 demand phases   │  │
│  │  additional.add.xml Induction loops + area detectors        │  │
│  │  simulation.sumocfg Duration, seed, output config           │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Live Simulation Data Flow

```
SUMO/Mock
  |
  | TraCI.getLastStepVehicleNumber()
  | TraCI.getWaitingTime()
  | TraCI.getLastStepMeanSpeed()
  | TraCI.trafficlight.getPhase()
  |
  v
SumoRunner.get_state() -> dict
  |
  v
TrafficState.from_runner_dict() -> TrafficState dataclass
  |
  v
AgentController._run_cycle()
  |
  +---> GoalManager.evaluate(state) -> GoalAssessment
  |
  +---> Planner.generate_candidates(state, goal) -> [CandidateAction]
  |
  +---> DecisionEngine.decide(state, candidates) -> DecisionResult
  |         (Q-value lookup + planner score blend)
  |
  +---> SumoRunner.set_phase(phase, duration)  [EXECUTE]
  |
  +---> calculate_reward(prev_state, curr_state) -> RewardResult
  |
  +---> QLearner.update(state, action, reward, next_state)  [LEARN]
  |
  +---> AgentCycleLog (full decision record)
  |
  +---> on_cycle_complete callback -> database.record_agent_decision()
  |
  v
AppState.latest_agent_cycle / latest_state (thread-safe)
  |
  v
SSE stream -> React dashboard (1 Hz update)
```

### Q-Learning Update

```
Bellman equation:
  Q(s, a) <- Q(s, a) + alpha * [r + gamma * max_a' Q(s', a') - Q(s, a)]

Where:
  s      = current discrete state (5-tuple bin indices)
  a      = action taken (string ID)
  r      = reward from reward.calculate_reward()
  s'     = next observed state
  alpha  = 0.15 (learning rate)
  gamma  = 0.90 (discount factor)

State discretisation:
  (bin(ns_queue, 20, 5), bin(ew_queue, 20, 5),
   bin(avg_wait, 90, 5), bin(imbalance, 1.0, 5), phase % 6)
  -> 5^4 * 6 = 3750 possible discrete states
```

---

## Traffic Signal Safety Model

All signal transitions enforce the standard traffic engineering safety sequence:

```
Phase 0 (NS_GREEN)  -> Phase 1 (NS_YELLOW) -> Phase 2 (ALL_RED)
                                                    |
Phase 5 (ALL_RED) <- Phase 4 (EW_YELLOW) <- Phase 3 (EW_GREEN)
```

The DecisionEngine enforces SAFE_TRANSITIONS:
- No phase can jump to a non-adjacent phase
- Yellow duration is fixed at 4 seconds (non-negotiable)
- All-red clearance is fixed at 2 seconds (non-negotiable)
- Green minimum: 10 seconds
- Green maximum: 60 seconds

---

## Database Schema

### simulation_runs
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| run_name | TEXT | Human-readable name |
| controller | TEXT | 'fixed' or 'agentic' |
| demand | TEXT | Demand preset name |
| seed | INTEGER | Random seed |
| duration | INTEGER | Requested sim seconds |
| status | TEXT | running/completed/stopped/error |
| started_at | DATETIME | UTC timestamp |
| finished_at | DATETIME | UTC timestamp |

### traffic_states
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| run_id | INTEGER | FK to simulation_runs |
| sim_time | REAL | Simulation seconds |
| avg_waiting_time | REAL | Seconds |
| ns_queue | REAL | N+S halted vehicles |
| ew_queue | REAL | E+W halted vehicles |
| phase | INTEGER | 0-5 |
| congestion_level | TEXT | LOW/MEDIUM/HIGH/CRITICAL |

### agent_decisions
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| run_id | INTEGER | FK to simulation_runs |
| cycle_id | INTEGER | Decision sequence number |
| goal | TEXT | Active goal enum value |
| selected_action | TEXT | Chosen action ID |
| reward | REAL | Total reward signal |
| reward_detail | TEXT | JSON breakdown |
| reasoning_summary | TEXT | Full explanation text |

### performance_metrics
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| run_id | INTEGER | FK to simulation_runs |
| controller | TEXT | 'fixed' or 'agentic' |
| average_waiting_time | REAL | Final aggregated metric |
| throughput | INTEGER | Total arrived vehicles |
| average_reward | REAL | Agentic only |

---

## Extensibility

### Adding a New Intersection

1. Add junction node to network.net.xml with a new TL_ID
2. Create a second AgentController instance with the new runner and TL_ID
3. Each agent operates independently; coordination can be added via shared state

### Replacing Tabular RL with Deep RL (DQN)

1. Replace `ai_agent/learning.py` QLearner with a PyTorch/TensorFlow DQN
2. Change `state.feature_vector()` output as the neural network input
3. The rest of the system (agent, decision engine, reward) remains unchanged

### Custom Goals

1. Add a new entry to the `Goal` enum in `goal_manager.py`
2. Add a `_score_*` method in `GoalManager._score_all_goals()`
3. Add value estimation in `Planner._extend_value()` / `_shorten_value()`

---

## Performance Notes

- The simulation runs in a background Python thread (not async) to avoid blocking the FastAPI event loop
- State is shared via thread-safe `AppState` with a `threading.Lock`
- SSE updates at 1 Hz to the dashboard; internal simulation runs at up to 100 Hz (20x realtime)
- SQLite writes are batched every 30 simulation seconds to reduce I/O overhead
- Q-table is persisted to `models/q_table.pkl` at the end of each run (enables transfer learning between runs)
