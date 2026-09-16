"""
setup_check.py
==============
Checks all dependencies and configuration for the prototype.
Run before starting for the first time.

Usage:
    python setup_check.py
"""
import sys
import shutil
import importlib
from pathlib import Path

ROOT = Path(__file__).parent
REQUIRED_DIRS = [
    "data/raw",
    "data/results",
    "models",
    "logs",
    "simulation/sumo",
]
REQUIRED_FILES = [
    "simulation/sumo/network.net.xml",
    "simulation/sumo/routes.rou.xml",
    "simulation/sumo/additional.add.xml",
    "simulation/sumo/simulation.sumocfg",
]
PYTHON_PACKAGES = [
    ("fastapi",      "FastAPI",         True),
    ("uvicorn",      "Uvicorn",         True),
    ("sqlalchemy",   "SQLAlchemy",      True),
    ("numpy",        "NumPy",           True),
    ("pytest",       "Pytest",          True),
    ("httpx",        "HTTPX",           True),
    ("traci",        "TraCI (SUMO)",    False),  # optional
]


def check_python():
    v = sys.version_info
    ok = v >= (3, 9)
    status = "[OK]" if ok else "[!!] (need 3.9+)"
    print(f"  Python {v.major}.{v.minor}.{v.micro}  {status}")
    return ok


def check_sumo():
    sumo = shutil.which("sumo") or shutil.which("sumo.exe")
    if sumo:
        print(f"  SUMO:  [OK] {sumo}")
        return True
    else:
        print("  SUMO:  [--] NOT FOUND -- Mock simulation will be used")
        print("         Install from: https://sumo.dlr.de/docs/Downloads.php")
        return False


def check_node():
    node = shutil.which("node")
    npm  = shutil.which("npm")
    if node and npm:
        print(f"  Node:  [OK] {node}")
        return True
    else:
        print("  Node:  [--] NOT FOUND -- Frontend will need manual start")
        print("         Install from: https://nodejs.org/")
        return False


def check_packages():
    all_ok = True
    for pkg, name, required in PYTHON_PACKAGES:
        try:
            importlib.import_module(pkg)
            print(f"  {name:<20} [OK]")
        except ImportError:
            marker = "[!!] (required)" if required else "[--] (optional)"
            print(f"  {name:<20} {marker}")
            if required:
                all_ok = False
    return all_ok


def check_files():
    all_ok = True
    for f in REQUIRED_FILES:
        p = ROOT / f
        if p.exists():
            print(f"  {f:<50} [OK]")
        else:
            print(f"  {f:<50} [MISSING]")
            all_ok = False
    return all_ok


def create_dirs():
    for d in REQUIRED_DIRS:
        p = ROOT / d
        p.mkdir(parents=True, exist_ok=True)
    print("  [OK] All required directories created/verified")


def main():
    print("\n[>>] Agentic AI Traffic Intelligence -- Setup Check")
    print("=" * 55)

    print("\n[Python]")
    py_ok = check_python()

    print("\n[SUMO]")
    sumo_ok = check_sumo()

    print("\n[Node.js]")
    node_ok = check_node()

    print("\n[Python Packages]")
    pkg_ok = check_packages()

    print("\n[Required Files]")
    files_ok = check_files()

    print("\n[Directories]")
    create_dirs()

    print("\n" + "=" * 55)
    print("SUMMARY:")
    print(f"  Python:           {'[OK]' if py_ok else '[FAIL]'}")
    print(f"  SUMO:             {'[OK]' if sumo_ok else '[MOCK] (mock mode)'}")
    print(f"  Node.js:          {'[OK]' if node_ok else '[--] (no frontend auto-start)'}")
    print(f"  Python packages:  {'[OK]' if pkg_ok else '[FAIL] (run: pip install -r requirements.txt)'}")
    print(f"  Required files:   {'[OK]' if files_ok else '[FAIL]'}")

    if py_ok and pkg_ok:
        print("\n[OK] Prototype is ready to run!")
        print("\nNext steps:")
        print("  1. pip install -r requirements.txt   (if not done)")
        print("  2. cd frontend && npm install        (if Node.js available)")
        print("  3. Double-click run_prototype.bat    (Windows one-click start)")
        print("     OR manually:")
        print("       python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000")
        print("       cd frontend && npm run dev")
        print("  4. Open http://localhost:5173")
        if not sumo_ok:
            print("\n[MOCK] SUMO not installed -- using Mock Simulation.")
            print("   The AI agent, dashboard, and experiments all work without SUMO.")
            print("   Install SUMO for real traffic physics simulation.")
    else:
        print("\n[FAIL] Some required components are missing. See above.")

    print()


if __name__ == "__main__":
    main()
