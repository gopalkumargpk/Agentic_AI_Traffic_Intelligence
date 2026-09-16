"""
conftest.py
===========
Pytest configuration — ensures project root is on sys.path
so all test imports resolve correctly.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
