# Agentic AI Traffic Intelligence

## Autonomous Network Intelligence Layer for Adaptive and Self-Optimizing Smart Traffic Networks

> A complete research/patent prototype demonstrating closed-loop agentic AI traffic control.

---

## 1. Project Overview

This prototype demonstrates an **Agentic AI-Driven Autonomous Network Intelligence Layer** for smart traffic control. The system operates as an intelligence overlay above a traffic simulator (SUMO), making autonomous signal-control decisions using a closed-loop Observe->Understand->Goal->Plan->Decide->Execute->Measure->Reward->Learn cycle.

### Key Features

- **Closed-loop agentic control** - the AI observes, decides, acts, and learns continuously
- **Goal-directed optimization** - dynamically selects goals (reduce waiting time, reduce congestion, improve throughput, balance directions)
- **Tabular Q-Learning** - online reinforcement learning updates after every action
- **Explainable decisions** - every AI action is logged with goal, reason, candidates, reward breakdown
- **Fixed vs AI comparison** - reproducible experiment mode for quantitative evaluation
- **SUMO-compatible** - real TraCI integration when SUMO is installed; mock simulation when not
- **FastAPI backend** - REST API + Server-Sent Events for live dashboard updates
- **React dashboard** - professional real-time visualization with charts

---

## 2. Architecture

```
React Dashboard (Vite)
       | HTTP / SSE
FastAPI Backend (Python)
       | Python in-process call
AI Agent (Observe->Goal->Plan->Decide->Execute->Reward->Learn)
       | TraCI / Mock
SUMO Simulation (4-way intersection)
       | SQLite
Performance Database
```

### The Closed-Loop Control Cycle

```
OBSERVE         -> Read traffic state from TraCI
UNDERSTAND      -> Build TrafficState (queues, wait times, speeds)
GOAL SELECT     -> GoalManager evaluates urgency and picks goal
PLAN            -> Planner generates candidate signal actions
DECIDE          -> DecisionEngine combines Q-values + planner scores
EXECUTE         -> Set traffic light phase via TraCI
MEASURE         -> Re-observe state after decision interval
REWARD          -> Calculate multi-component reward
LEARN           -> Q-learning Bellman update
NEXT DECISION   -> Repeat
```

---

## 3. Technology Stack

| Component | Technology |
|-----------|------------|
| Traffic simulator | SUMO (eclipse.sumo) |
| TraCI communication | traci Python library |
| AI framework | Tabular Q-Learning (custom) |
| Backend API | FastAPI + Uvicorn |
| Database | SQLite via SQLAlchemy |
| Frontend | React 18 + Vite |
| Charts | Recharts |
| Testing | Pytest |
| Language | Python 3.9+ |

---

## 4. Installation

### Prerequisites

- Python 3.9 or higher
- Node.js 18 or higher (for frontend)
- SUMO (optional - mock simulation works without it)

### Step 1: Clone / Open Workspace

```
cd Agentic_AI_Traffic_Intelligence
```

### Step 2: Install Python dependencies

```powershell
pip install -r requirements.txt
```

### Step 3: Install Frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

### Step 4: Verify setup

```powershell
python setup_check.py
```

---

## 5. SUMO Installation (Optional but Recommended)

SUMO provides real traffic physics simulation.

**Windows:**
1. Download from: https://sumo.dlr.de/docs/Downloads.php
2. Install to: C:\Program Files (x86)\Eclipse\Sumo
3. Set environment variables in PowerShell:
   ```
   $env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
   $env:PATH += ";C:\Program Files (x86)\Eclipse\Sumo\bin"
   ```
4. Install TraCI Python package:
   ```
   pip install traci sumolib
   ```

**Without SUMO:** The system automatically uses a MockSumoRunner that generates mathematically realistic traffic patterns. The AI agent, dashboard, and all experiments work fully in mock mode.

---

## 6. How to Run

### One-Click Start (Windows)

```
Double-click: run_prototype.bat
```

### Manual Start

**Terminal 1 - Backend:**
```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```powershell
cd frontend
npm run dev
```

**Open browser:** http://localhost:5173

---

## 7. How to Run Experiments

### Quick comparison (120 seconds):
```powershell
python run_experiment.py --controller both --demand medium --duration 120
```

### Full experiment (30 minutes):
```powershell
python run_experiment.py --controller fixed --demand medium --duration 1800 --seed 42
python run_experiment.py --controller agentic --demand medium --duration 1800 --seed 42
```

### Available options:
```
--controller  fixed | agentic | both
--demand      low | medium | high | asymmetric_ns | asymmetric_ew
--duration    seconds (60 to 7200)
--seed        integer (for reproducibility)
--decision-interval  AI decision frequency in seconds (default 10)
--ns-green    fixed NS green duration (fixed controller only)
--ew-green    fixed EW green duration (fixed controller only)
```

Results are saved to: data/results/

---

## 8. How the Agent Works

### State Observation
At every decision interval (default: 10 seconds), the agent reads:
- Queue length per direction (N, S, E, W)
- Waiting time per direction
- Current signal phase and remaining duration
- Average vehicle speed
- Throughput (arrived vehicles)

### Goal Selection (GoalManager)
The agent evaluates 6 possible goals:
- REDUCE_NS_CONGESTION - when North-South queue is high
- REDUCE_EW_CONGESTION - when East-West queue is high  
- REDUCE_WAITING_TIME - when average wait exceeds threshold
- BALANCE_DIRECTIONS - when queue imbalance is high
- INCREASE_THROUGHPUT - when network is congested and slow
- MAINTAIN_FLOW - default during low demand

### Action Planning (Planner)
Given the state and goal, the Planner generates candidate actions:
- EXTEND_GREEN_10 - extend current green by 10 seconds
- SHORTEN_GREEN_10 - shorten current green by 10 seconds
- HOLD_CURRENT - maintain current timing
- WAIT_TRANSITION - complete safety yellow/all-red phase

### Decision (DecisionEngine)
Final action = argmax(0.6 * Q_value + 0.4 * planner_score)

Safety constraints enforced: no unsafe phase jumps; yellow always transitions before next green.

---

## 9. Reward Function

```
reward =
    0.40 * clip(delta_avg_wait / 60)          [waiting time improvement]
  + 0.20 * clip(delta_ns_queue / 15)          [NS queue reduction]
  + 0.20 * clip(delta_ew_queue / 15)          [EW queue reduction]
  + 0.10 * clip(delta_throughput / 20)        [throughput increase]
  + 0.05 * (avg_speed / 14 * 2 - 1)           [speed improvement]
  - 0.05 * queue_imbalance                    [fairness penalty]
```

Where delta = (previous - current), so decrease in waiting = positive reward.
All components are clipped to [-1, +1]. Final reward is clipped to [-1, +1].

---

## 10. API Documentation

### Base URL: http://localhost:8000

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/status | System status |
| GET | /api/traffic | Current traffic state |
| GET | /api/signals | Current signal phase |
| GET | /api/agent/state | Full agent state |
| GET | /api/agent/decision | Latest agent decision |
| GET | /api/metrics | Performance metrics |
| GET | /api/history | Time-series history |
| GET | /api/runs | All simulation runs |
| GET | /api/comparison | Fixed vs AI comparison |
| GET | /api/stream | SSE live stream |
| POST | /api/simulation/start | Start simulation |
| POST | /api/simulation/stop | Stop simulation |
| POST | /api/simulation/reset | Reset state |
| POST | /api/controller/mode | Set controller mode |

Interactive API docs: http://localhost:8000/docs

---

## 11. Experiment Methodology

1. Set identical parameters for both runs: --demand medium --seed 42 --duration 1800
2. Run fixed controller: python run_experiment.py --controller fixed ...
3. Run agentic controller: python run_experiment.py --controller agentic ...
4. Compare results in terminal output, JSON file, and dashboard /api/comparison

Results are deterministic for a given seed (MockSumoRunner) or statistically comparable (SUMO).

---

## 12. Results Interpretation

| Metric | Lower is better | Notes |
|--------|----------------|-------|
| Average Waiting Time | Yes | Primary KPI |
| Total Waiting Time | Yes | Sum over simulation |
| Max Queue Length | Yes | Peak congestion |
| Average Speed | No | Higher = less congestion |
| Throughput | No | More vehicles = better |

The AI agent requires warm-up time (200-500 simulated seconds) before Q-values become meaningful.
For the best comparison results, run experiments of at least 1800 seconds.

---

## 13. Project Structure

```
Agentic_AI_Traffic_Intelligence/
|-- simulation/               # SUMO files + runner
|   |-- sumo/                 # .net.xml .rou.xml .add.xml .sumocfg
|   |-- generate_scenario.py  # Demand-parameterised scenario generator
|   +-- sumo_runner.py        # TraCI + MockSumoRunner factory
|-- ai_agent/                 # Core intelligence layer
|   |-- agent.py              # Closed-loop agent orchestrator
|   |-- state.py              # TrafficState dataclass
|   |-- goal_manager.py       # Dynamic goal selection
|   |-- planner.py            # Candidate action generation
|   |-- decision_engine.py    # Q+planner action selection
|   |-- reward.py             # Multi-component reward function
|   +-- learning.py           # Tabular Q-learning
|-- traffic_controller/       # Signal controllers
|   |-- fixed_controller.py   # Fixed-time baseline
|   |-- adaptive_controller.py # AI controller wrapper
|   +-- traci_controller.py   # Phase safety utilities
|-- backend/                  # FastAPI
|   |-- main.py               # App + all endpoints + SSE
|   |-- database.py           # SQLite CRUD
|   +-- models.py             # Pydantic schemas
|-- frontend/                 # React + Vite dashboard
|   +-- src/components/       # All UI panels
|-- tests/                    # Pytest test suite (54 tests)
|-- data/
|   |-- raw/                  # SUMO detector outputs
|   +-- results/              # Experiment CSVs + JSON
|-- models/                   # Saved Q-tables
|-- run_experiment.py         # CLI experiment runner
|-- run_prototype.bat         # One-click Windows start
|-- setup_check.py            # Dependency checker
+-- requirements.txt
```

---

## 14. Running Tests

```powershell
# All tests
pytest tests/ -v

# Individual test suites
pytest tests/test_reward.py -v
pytest tests/test_decision_engine.py -v
pytest tests/test_database.py -v
pytest tests/test_api.py -v
```

Expected: 54 tests passing.

---

## 15. Future Improvements

1. Deep RL (DQN/PPO) - the code is structured to replace QLearner with a neural network
2. Multi-intersection - AgentController can be instantiated per junction
3. Real SUMO scenarios - replace mock network with city OSM data
4. Incident detection - detect unusual waiting patterns and trigger emergency goals
5. Green wave coordination - coordinate multiple intersections for arterial throughput
6. Federated learning - share Q-table updates across intersections
7. LSTM state encoding - temporal sequence for better state representation
8. WebSocket - replace SSE with full bidirectional WebSocket

---

## 16. Research / Patent Alignment

This prototype demonstrates:
- Overlay intelligence layer - operates above existing traffic infrastructure
- Goal-directed autonomous control - self-selects optimization objectives
- Closed-loop learning - continuously updates decision policy from observed outcomes
- Explainable AI decisions - every action logged with state, goal, reason, and reward
- Adaptive signal control - dynamically adjusts green times based on real-time demand
- Multi-metric optimization - balances waiting time, throughput, fairness simultaneously

> Disclaimer: This is a research prototype. Patent claims should be reviewed by qualified IP professionals.
