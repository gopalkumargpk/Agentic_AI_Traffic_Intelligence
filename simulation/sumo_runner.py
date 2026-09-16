"""
sumo_runner.py
==============
Manages the SUMO process and TraCI connection.

Responsibilities:
- Start/stop SUMO (headless or GUI)
- Detect SUMO installation
- Provide a fallback MockSumoRunner when SUMO is unavailable
- Expose a unified interface to the rest of the system
"""

from __future__ import annotations

import logging
import math
import os
import random
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SUMO detection helpers
# ---------------------------------------------------------------------------

SUMO_DIR = Path(__file__).parent / "sumo"
SUMOCFG = SUMO_DIR / "simulation.sumocfg"

INCOMING_EDGES = {
    "N": ["N2C_0", "N2C_1"],
    "S": ["S2C_0", "S2C_1"],
    "E": ["E2C_0", "E2C_1"],
    "W": ["W2C_0", "W2C_1"],
}

TL_ID = "C"

PHASE_NAMES = {
    0: "NS_GREEN",
    1: "NS_YELLOW",
    2: "ALL_RED",
    3: "EW_GREEN",
    4: "EW_YELLOW",
    5: "ALL_RED",
}


def _find_sumo_binary(gui: bool = False) -> Optional[str]:
    """Return path to sumo or sumo-gui binary, or None if not found."""
    name = "sumo-gui" if gui else "sumo"
    candidates = [name, name + ".exe"]
    for c in candidates:
        found = shutil.which(c)
        if found:
            return found
    # Try SUMO_HOME
    sumo_home = os.environ.get("SUMO_HOME", "")
    if sumo_home:
        candidate = Path(sumo_home) / "bin" / (name + ".exe")
        if candidate.exists():
            return str(candidate)
        candidate = Path(sumo_home) / "bin" / name
        if candidate.exists():
            return str(candidate)
    return None


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def is_sumo_available() -> bool:
    return _find_sumo_binary(gui=False) is not None


# ---------------------------------------------------------------------------
# TraCI import (optional)
# ---------------------------------------------------------------------------

try:
    import traci
    import traci.constants as tc
    TRACI_AVAILABLE = True
except ImportError:
    TRACI_AVAILABLE = False
    logger.warning("traci not importable — will use MockSumoRunner.")


# ---------------------------------------------------------------------------
# Real SUMO Runner
# ---------------------------------------------------------------------------

class SumoRunner:
    """
    Manages a headless SUMO process connected via TraCI.

    Uses an explicit TraCI connection object (self._conn) so that:
    - Multiple runs never collide on the 'default' connection label.
    - The connection is fully isolated per SumoRunner instance.
    - start() may be safely called more than once (stops first if running).

    Interface:
        start()       → connect to SUMO
        step()        → advance simulation by 1 second
        get_state()   → return TrafficState dict
        set_phase()   → set traffic light phase
        get_phase()   → get current phase
        stop()        → close TraCI & kill process
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        gui: bool = False,
        seed: int = 42,
        step_length: float = 1.0,
    ):
        self.config_path = config_path or SUMOCFG
        self.gui = gui
        self.seed = seed
        self.step_length = step_length
        self._proc: Optional[subprocess.Popen] = None
        self._port: int = 0
        self._conn = None  # explicit TraCI connection object
        self.sim_time: float = 0.0
        self.running: bool = False
        self._departed_total: int = 0
        self._arrived_total: int = 0

    def start(self) -> None:
        # If already running, stop cleanly before starting a new run.
        if self.running or self._conn is not None or self._proc is not None:
            logger.info("SumoRunner.start(): previous run detected — stopping first.")
            self.stop()

        sumo_bin = _find_sumo_binary(self.gui)
        if sumo_bin is None:
            raise RuntimeError(
                "SUMO binary not found. Install SUMO and set SUMO_HOME.\n"
                "Download: https://sumo.dlr.de/docs/Downloads.php"
            )
        if not TRACI_AVAILABLE:
            raise RuntimeError("traci Python package not installed. Run: pip install traci")

        self._port = _find_free_port()
        cmd = [
            sumo_bin,
            "-c", str(self.config_path),
            "--remote-port", str(self._port),
            "--seed", str(self.seed),
            "--step-length", str(self.step_length),
            "--no-warnings", "true",
            "--no-step-log", "true",
        ]
        logger.info(f"Starting SUMO: {' '.join(cmd)}")
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Wait for SUMO to be ready, with early-exit check if it crashes.
        deadline = time.time() + 15.0
        connected = False
        while time.time() < deadline:
            # Check if SUMO exited prematurely
            if self._proc.poll() is not None:
                try:
                    last_err = self._proc.stderr.read().decode(errors="replace")
                except Exception:
                    last_err = "(could not read stderr)"
                exit_code = self._proc.returncode
                self._proc = None
                raise RuntimeError(
                    f"SUMO process exited (code {exit_code}) before TraCI could connect.\n"
                    f"SUMO stderr:\n{last_err}"
                )

            # Try connecting — label=None means the connection is NOT registered
            # in traci's global connection pool, so the 'default' slot is never
            # touched and multiple runs cannot collide.
            try:
                conn = traci.connect(
                    port=self._port,
                    host="localhost",
                    numRetries=0,
                    label=None,
                )
                self._conn = conn
                connected = True
                break
            except Exception:
                time.sleep(0.25)

        if not connected:
            # SUMO is still alive but unresponsive — kill it.
            self._terminate_proc()
            raise RuntimeError(
                f"TraCI could not connect to SUMO on port {self._port} within 15 seconds."
            )

        self.sim_time = 0.0
        self.running = True
        self._departed_total = 0
        self._arrived_total = 0
        logger.info(f"TraCI connected (explicit connection) on port {self._port}")

    def step(self, n: int = 1) -> None:
        if not self.running:
            raise RuntimeError("Simulation not running.")
        for _ in range(n):
            self._conn.simulationStep()
            self.sim_time += self.step_length
            self._departed_total += self._conn.simulation.getDepartedNumber()
            self._arrived_total += self._conn.simulation.getArrivedNumber()

    def get_state(self) -> dict:
        """Collect traffic state via TraCI and return structured dict."""
        if not self.running:
            raise RuntimeError("Simulation not running.")

        direction_stats = {}
        total_vehicles = 0
        total_waiting = 0.0
        total_speed = 0.0
        speed_count = 0
        total_stopped = 0

        for direction, lanes in INCOMING_EDGES.items():
            q_len = 0
            wait = 0.0
            veh_count = 0
            stopped = 0

            for lane_id in lanes:
                try:
                    lane_vehs = self._conn.lane.getLastStepVehicleNumber(lane_id)
                    lane_halt = self._conn.lane.getLastStepHaltingNumber(lane_id)
                    lane_speed = self._conn.lane.getLastStepMeanSpeed(lane_id)
                    lane_wait = self._conn.lane.getWaitingTime(lane_id)
                    q_len += lane_halt
                    wait += lane_wait
                    veh_count += lane_vehs
                    stopped += lane_halt
                    if lane_vehs > 0:
                        total_speed += lane_speed * lane_vehs
                        speed_count += lane_vehs
                except traci.TraCIException:
                    pass

            direction_stats[direction] = {
                "queue_length": q_len,
                "waiting_time": round(wait, 2),
                "vehicle_count": veh_count,
                "stopped": stopped,
            }
            total_vehicles += veh_count
            total_waiting += wait
            total_stopped += stopped

        avg_speed = (total_speed / speed_count) if speed_count > 0 else 0.0
        density = total_vehicles / 4.0  # vehicles per approach (normalised)

        # Traffic light state
        try:
            phase = self._conn.trafficlight.getPhase(TL_ID)
            phase_duration = self._conn.trafficlight.getPhaseDuration(TL_ID)
            phase_name = PHASE_NAMES.get(phase, "UNKNOWN")
            next_switch = self._conn.trafficlight.getNextSwitch(TL_ID) - self.sim_time
        except traci.TraCIException:
            phase, phase_duration, phase_name, next_switch = 0, 30, "NS_GREEN", 30

        return {
            "sim_time": self.sim_time,
            "total_vehicles": total_vehicles,
            "total_waiting_time": round(total_waiting, 2),
            "average_waiting_time": round(total_waiting / max(total_vehicles, 1), 2),
            "total_stopped": total_stopped,
            "average_speed": round(avg_speed, 2),
            "density": round(density, 2),
            "throughput_departed": self._departed_total,
            "throughput_arrived": self._arrived_total,
            "phase": phase,
            "phase_name": phase_name,
            "phase_duration": phase_duration,
            "next_switch_in": round(max(next_switch, 0), 1),
            "direction_stats": direction_stats,
        }

    def set_phase(self, phase: int, duration: Optional[int] = None) -> None:
        """Set TL phase via TraCI. Respects phase safety (yellow enforced externally)."""
        if not self.running:
            return
        try:
            self._conn.trafficlight.setPhase(TL_ID, phase)
            if duration is not None:
                self._conn.trafficlight.setPhaseDuration(TL_ID, duration)
        except Exception as e:
            logger.warning(f"set_phase failed: {e}")

    def get_phase(self) -> int:
        try:
            return self._conn.trafficlight.getPhase(TL_ID)
        except Exception:
            return 0

    def stop(self) -> None:
        """Close TraCI connection and terminate SUMO process robustly."""
        # Close the explicit connection first
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as exc:
                logger.debug(f"TraCI close error (ignored): {exc}")
            finally:
                self._conn = None

        self.running = False
        self._terminate_proc()
        logger.info("SUMO simulation stopped.")

    def _terminate_proc(self) -> None:
        """Terminate the SUMO subprocess if it is still alive."""
        if self._proc is None:
            return
        proc = self._proc
        self._proc = None
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            except Exception as exc:
                logger.debug(f"SUMO process termination error (ignored): {exc}")


# ---------------------------------------------------------------------------
# Mock SUMO Runner (when SUMO is not installed)
# ---------------------------------------------------------------------------

class MockSumoRunner:
    """
    Simulates traffic state mathematically when SUMO is unavailable.
    Produces realistic-looking data suitable for demonstrating the AI agent
    and the full dashboard without an actual SUMO installation.
    """

    PHASE_DURATIONS = {0: 30, 1: 4, 2: 2, 3: 30, 4: 4, 5: 2}
    TOTAL_CYCLE = 72  # sum of all phase durations

    def __init__(self, seed: int = 42, step_length: float = 1.0, demand: str = "medium"):
        self.seed = seed
        self.step_length = step_length
        self.demand = demand
        self.sim_time: float = 0.0
        self.running: bool = False
        self._phase: int = 0
        self._phase_timer: float = 0.0
        self._rng = random.Random(seed)
        self._departed: int = 0
        self._arrived: int = 0
        self._queues = {"N": 2, "S": 2, "E": 2, "W": 2}
        self._waiting = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
        self._forced_phase: Optional[int] = None
        self._forced_duration: Optional[float] = None

    def start(self) -> None:
        logger.warning(
            "SUMO not available — using MockSumoRunner. "
            "Install SUMO to run full physics-based simulation."
        )
        self.running = True
        self.sim_time = 0.0
        self._phase = 0
        self._phase_timer = self.PHASE_DURATIONS[0]

    def _demand_rate(self) -> float:
        """Returns a demand multiplier based on sim time (simulates rush hours)."""
        t = self.sim_time
        if t < 300:
            base = 0.3
        elif t < 1800:
            base = 0.8
        elif t < 2700:
            base = 1.2  # peak
        elif t < 3200:
            base = 0.9
        else:
            base = 0.5
        return base + self._rng.uniform(-0.05, 0.05)

    def step(self, n: int = 1) -> None:
        for _ in range(n):
            self.sim_time += self.step_length
            dr = self._demand_rate()

            # Advance phase timer
            self._phase_timer -= self.step_length
            if self._phase_timer <= 0:
                if self._forced_phase is not None:
                    self._phase = self._forced_phase
                    self._phase_timer = self._forced_duration or self.PHASE_DURATIONS.get(self._forced_phase, 30)
                    self._forced_phase = None
                    self._forced_duration = None
                else:
                    self._phase = (self._phase + 1) % 6
                    self._phase_timer = self.PHASE_DURATIONS.get(self._phase, 30)

            # Update queues per direction
            ns_green = self._phase == 0
            ew_green = self._phase == 3

            for d in ["N", "S"]:
                arrival = self._rng.poisson_approx(dr * 0.8)
                departure = (self._rng.poisson_approx(1.5) if ns_green else 0)
                self._queues[d] = max(0, self._queues[d] + arrival - departure)
                if not ns_green:
                    self._waiting[d] += self.step_length

            for d in ["E", "W"]:
                arrival = self._rng.poisson_approx(dr * 0.6)
                departure = (self._rng.poisson_approx(1.5) if ew_green else 0)
                self._queues[d] = max(0, self._queues[d] + arrival - departure)
                if not ew_green:
                    self._waiting[d] += self.step_length

            # Throughput
            departed_this_step = 0
            if ns_green:
                departed_this_step += min(self._queues["N"] + self._queues["S"], 3)
            if ew_green:
                departed_this_step += min(self._queues["E"] + self._queues["W"], 3)
            self._departed += departed_this_step + self._rng.randint(0, 1)
            self._arrived += max(0, departed_this_step - 1)

    def get_state(self) -> dict:
        direction_stats = {}
        total_vehicles = 0
        total_waiting = 0.0
        total_stopped = 0

        for d in ["N", "S", "E", "W"]:
            q = self._queues[d]
            w = round(self._waiting[d], 2)
            veh = q + self._rng.randint(0, 3)
            direction_stats[d] = {
                "queue_length": q,
                "waiting_time": w,
                "vehicle_count": veh,
                "stopped": q,
            }
            total_vehicles += veh
            total_waiting += w
            total_stopped += q

        ns_green = self._phase == 0
        ew_green = self._phase == 3
        avg_speed = (
            6.5 + self._rng.uniform(-1, 1) if (ns_green or ew_green) else
            1.2 + self._rng.uniform(-0.5, 0.5)
        )

        return {
            "sim_time": self.sim_time,
            "total_vehicles": total_vehicles,
            "total_waiting_time": round(total_waiting, 2),
            "average_waiting_time": round(total_waiting / max(total_vehicles, 1), 2),
            "total_stopped": total_stopped,
            "average_speed": round(max(0, avg_speed), 2),
            "density": round(total_vehicles / 4.0, 2),
            "throughput_departed": self._departed,
            "throughput_arrived": self._arrived,
            "phase": self._phase,
            "phase_name": PHASE_NAMES.get(self._phase, "UNKNOWN"),
            "phase_duration": self.PHASE_DURATIONS.get(self._phase, 30),
            "next_switch_in": round(max(self._phase_timer, 0), 1),
            "direction_stats": direction_stats,
        }

    def set_phase(self, phase: int, duration: Optional[int] = None) -> None:
        self._forced_phase = phase
        self._forced_duration = float(duration) if duration else self.PHASE_DURATIONS.get(phase, 30)

    def get_phase(self) -> int:
        return self._phase

    def stop(self) -> None:
        self.running = False


# Monkey-patch random to add Poisson approx
import random as _random_module

class _EnhancedRandom(_random_module.Random):
    def poisson_approx(self, lam: float) -> int:
        """Approximate Poisson(lam) using Knuth algorithm for small lam."""
        if lam <= 0:
            return 0
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= self.random()
        return max(0, k - 1)

# Re-assign MockSumoRunner to use enhanced RNG
_orig_init = MockSumoRunner.__init__

def _new_init(self, seed=42, step_length=1.0, demand="medium"):
    _orig_init(self, seed, step_length, demand)
    self._rng = _EnhancedRandom(seed)

MockSumoRunner.__init__ = _new_init


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_runner(
    gui: bool = False,
    seed: int = 42,
    demand: str = "medium",
    force_mock: bool = False,
) -> "SumoRunner | MockSumoRunner":
    """
    Return a SumoRunner if SUMO + traci are available, else MockSumoRunner.
    """
    if force_mock or not is_sumo_available() or not TRACI_AVAILABLE:
        logger.warning("Returning MockSumoRunner (SUMO/TraCI unavailable).")
        return MockSumoRunner(seed=seed, demand=demand)
    return SumoRunner(gui=gui, seed=seed)
