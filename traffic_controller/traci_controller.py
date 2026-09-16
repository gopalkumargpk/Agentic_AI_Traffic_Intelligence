"""
traci_controller.py
===================
Low-level TraCI interface wrapper.
Provides helper utilities for direct signal manipulation.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

TL_ID = "C"

PHASE_NS_GREEN  = 0
PHASE_NS_YELLOW = 1
PHASE_ALL_RED_1 = 2
PHASE_EW_GREEN  = 3
PHASE_EW_YELLOW = 4
PHASE_ALL_RED_2 = 5

PHASE_NAMES = {
    PHASE_NS_GREEN:  "NS_GREEN",
    PHASE_NS_YELLOW: "NS_YELLOW",
    PHASE_ALL_RED_1: "ALL_RED",
    PHASE_EW_GREEN:  "EW_GREEN",
    PHASE_EW_YELLOW: "EW_YELLOW",
    PHASE_ALL_RED_2: "ALL_RED",
}

MIN_GREEN = 10
MAX_GREEN = 60
YELLOW_DURATION = 4
ALL_RED_DURATION = 2


def safe_set_phase(runner, target_phase: int, duration: int) -> bool:
    """
    Set traffic light phase with safety validation.
    Returns True if successfully set, False if blocked.
    """
    current_phase = runner.get_phase()

    # Cannot skip: must go through yellow → all-red → green
    valid_next = {
        PHASE_NS_GREEN:  [PHASE_NS_GREEN, PHASE_NS_YELLOW],
        PHASE_NS_YELLOW: [PHASE_NS_YELLOW, PHASE_ALL_RED_1],
        PHASE_ALL_RED_1: [PHASE_ALL_RED_1, PHASE_EW_GREEN],
        PHASE_EW_GREEN:  [PHASE_EW_GREEN, PHASE_EW_YELLOW],
        PHASE_EW_YELLOW: [PHASE_EW_YELLOW, PHASE_ALL_RED_2],
        PHASE_ALL_RED_2: [PHASE_ALL_RED_2, PHASE_NS_GREEN],
    }

    if target_phase not in valid_next.get(current_phase, []):
        logger.warning(
            f"[SAFETY] Blocked unsafe phase transition: "
            f"{PHASE_NAMES.get(current_phase)} → {PHASE_NAMES.get(target_phase)}"
        )
        return False

    # Clamp duration
    if target_phase in (PHASE_NS_GREEN, PHASE_EW_GREEN):
        duration = max(MIN_GREEN, min(duration, MAX_GREEN))
    elif target_phase in (PHASE_NS_YELLOW, PHASE_EW_YELLOW):
        duration = YELLOW_DURATION
    else:
        duration = ALL_RED_DURATION

    runner.set_phase(target_phase, duration)
    logger.debug(f"Phase set: {PHASE_NAMES.get(target_phase)} for {duration}s")
    return True
