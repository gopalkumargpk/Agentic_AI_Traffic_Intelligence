"""
learning.py
===========
Tabular Q-Learning implementation for the traffic signal agent.

State space:  Discretised TrafficState (ns_queue, ew_queue, avg_wait, imbalance, phase)
Action space: {EXTEND_GREEN_10, SHORTEN_GREEN_10, HOLD_CURRENT, WAIT_TRANSITION}

Q-update rule (Bellman):
    Q(s,a) ← Q(s,a) + α * [r + γ * max_a'Q(s',a') - Q(s,a)]

Where:
    α = learning rate (how fast new info replaces old)
    γ = discount factor (importance of future rewards)
    r = observed reward

Epsilon-greedy exploration is supported but disabled in production
(the Decision Engine handles exploration via planner diversity).
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"

# Q-Learning hyperparameters
DEFAULT_ALPHA   = 0.15   # learning rate
DEFAULT_GAMMA   = 0.90   # discount factor
DEFAULT_EPSILON = 0.10   # exploration rate (for future use)

KNOWN_ACTIONS = [
    "EXTEND_GREEN_10",
    "SHORTEN_GREEN_10",
    "HOLD_CURRENT",
    "WAIT_TRANSITION",
]


class QLearner:
    """
    Tabular Q-Learning agent.

    The Q-table maps (state_key, action_id) → Q-value.
    State keys are produced by TrafficState.discretize().
    """

    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        gamma: float = DEFAULT_GAMMA,
        epsilon: float = DEFAULT_EPSILON,
        model_path: Optional[Path] = None,
    ):
        self.alpha   = alpha
        self.gamma   = gamma
        self.epsilon = epsilon
        self.model_path = model_path or (MODELS_DIR / "q_table.pkl")

        # Q-table: default value 0.0
        self._q: Dict[Tuple, Dict[str, float]] = defaultdict(
            lambda: {a: 0.0 for a in KNOWN_ACTIONS}
        )

        self._total_updates  = 0
        self._total_reward   = 0.0
        self._episode_rewards: list = []
        self._running_avg    = 0.0

        # Attempt to load existing Q-table
        self.load()

    # ------------------------------------------------------------------ #
    # Core Q-learning methods                                             #
    # ------------------------------------------------------------------ #

    def get_q_value(self, state: tuple, action: str) -> float:
        """Return Q(state, action). Initialise to 0.0 if unseen."""
        return self._q[state].get(action, 0.0)

    def max_q(self, state: tuple) -> float:
        """Return max_a Q(state, a)."""
        vals = self._q[state]
        return max(vals.values()) if vals else 0.0

    def update(
        self,
        state: tuple,
        action: str,
        reward: float,
        next_state: tuple,
    ) -> float:
        """
        Perform a single Q-learning update (Bellman equation).
        Returns the TD error (for monitoring).
        """
        current_q = self.get_q_value(state, action)
        target    = reward + self.gamma * self.max_q(next_state)
        td_error  = target - current_q
        new_q     = current_q + self.alpha * td_error

        self._q[state][action] = new_q
        self._total_updates   += 1
        self._total_reward    += reward

        # Running average reward (exponential moving average)
        self._running_avg = 0.95 * self._running_avg + 0.05 * reward

        logger.debug(
            f"Q-update: s={state} a={action} r={reward:.3f} "
            f"Q: {current_q:.3f}→{new_q:.3f} (TDE={td_error:.3f})"
        )
        return td_error

    # ------------------------------------------------------------------ #
    # Statistics                                                          #
    # ------------------------------------------------------------------ #

    def get_stats(self) -> dict:
        return {
            "total_updates": self._total_updates,
            "total_reward": round(self._total_reward, 3),
            "running_avg_reward": round(self._running_avg, 4),
            "q_table_size": len(self._q),
            "alpha": self.alpha,
            "gamma": self.gamma,
        }

    # ------------------------------------------------------------------ #
    # Persistence                                                         #
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        try:
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump({
                    "q": dict(self._q),
                    "total_updates": self._total_updates,
                    "total_reward": self._total_reward,
                    "running_avg": self._running_avg,
                    "alpha": self.alpha,
                    "gamma": self.gamma,
                }, f)
            logger.info(f"Q-table saved: {self.model_path} ({len(self._q)} states)")
        except Exception as e:
            logger.warning(f"Failed to save Q-table: {e}")

    def load(self) -> bool:
        if not self.model_path.exists():
            logger.info("No existing Q-table found — starting fresh.")
            return False
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            loaded_q = data.get("q", {})
            self._q = defaultdict(lambda: {a: 0.0 for a in KNOWN_ACTIONS}, loaded_q)
            self._total_updates = data.get("total_updates", 0)
            self._total_reward  = data.get("total_reward", 0.0)
            self._running_avg   = data.get("running_avg", 0.0)
            logger.info(f"Q-table loaded: {len(self._q)} states, {self._total_updates} prior updates")
            return True
        except Exception as e:
            logger.warning(f"Failed to load Q-table: {e}")
            return False

    def reset(self) -> None:
        """Reset Q-table (start fresh learning)."""
        self._q = defaultdict(lambda: {a: 0.0 for a in KNOWN_ACTIONS})
        self._total_updates = 0
        self._total_reward  = 0.0
        self._running_avg   = 0.0
        logger.info("Q-table reset.")
