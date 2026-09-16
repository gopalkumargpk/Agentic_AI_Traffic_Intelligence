@echo off
REM ============================================================
REM  Agentic AI Traffic Intelligence — One-Click Startup
REM  Windows Batch Script
REM  
REM  This script:
REM    1. Checks Python installation
REM    2. Checks required Python packages
REM    3. Checks SUMO installation
REM    4. Creates required directories
REM    5. Starts FastAPI backend
REM    6. Starts React frontend (if Node.js is available)
REM    7. Opens browser
REM ============================================================

title Agentic AI Traffic Intelligence

echo.
echo  ██████████████████████████████████████████████████████
echo   Agentic AI Traffic Intelligence — Research Prototype
echo   Autonomous Network Intelligence Layer
echo  ██████████████████████████████████████████████████████
echo.

REM ---- 1. Check Python ----
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Download: https://www.python.org/downloads/
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
echo [OK] Python found:
python --version

REM ---- 2. Install Python dependencies ----
echo.
echo [SETUP] Installing Python dependencies...
pip install -r requirements.txt --quiet --disable-pip-version-check
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Some packages may have failed to install. Continuing...
)
echo [OK] Python dependencies ready.

REM ---- 3. Check SUMO ----
echo.
sumo --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] SUMO is installed and on PATH. Full simulation enabled.
    set SUMO_STATUS=AVAILABLE
) else (
    echo [INFO] SUMO is NOT detected on PATH.
    echo        The system will use Mock Simulation (no real SUMO physics).
    echo        To install SUMO:
    echo          1. Download from: https://sumo.dlr.de/docs/Downloads.php
    echo          2. Install to: C:\Program Files (x86)\Eclipse\Sumo
    echo          3. Add to PATH: C:\Program Files (x86)\Eclipse\Sumo\bin
    echo          4. Set SUMO_HOME: C:\Program Files (x86)\Eclipse\Sumo
    echo        Re-run this script after installing SUMO.
    set SUMO_STATUS=MOCK
)

REM ---- 4. Check Node.js ----
node --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Node.js found:
    node --version
    set NODE_STATUS=AVAILABLE
) else (
    echo [INFO] Node.js not found. Frontend will not auto-start.
    echo        Download: https://nodejs.org/
    set NODE_STATUS=MISSING
)

REM ---- 5. Create required directories ----
echo.
echo [SETUP] Creating required directories...
if not exist "data\raw"      mkdir "data\raw"
if not exist "data\results"  mkdir "data\results"
if not exist "models"        mkdir "models"
if not exist "logs"          mkdir "logs"
echo [OK] Directories ready.

REM ---- 6. Run scenario generator (creates/validates SUMO files) ----
echo.
echo [SETUP] Generating simulation scenario files...
python simulation\generate_scenario.py --demand medium --seed 42 --duration 3600
echo [OK] Scenario files ready.

REM ---- 7. Start FastAPI Backend ----
echo.
echo [START] Starting FastAPI Backend on http://localhost:8000 ...
echo         API Docs: http://localhost:8000/docs
start "Traffic Intelligence Backend" cmd /k "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level info"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM ---- 8. Start React Frontend ----
if "%NODE_STATUS%"=="AVAILABLE" (
    echo.
    echo [START] Installing frontend dependencies and starting React dashboard...
    echo         Dashboard: http://localhost:5173
    cd frontend
    call npm install --silent
    start "Traffic Intelligence Dashboard" cmd /k "npm run dev"
    cd ..
    timeout /t 4 /nobreak >nul
    start "" "http://localhost:5173"
    echo [OK] Frontend started.
) else (
    echo.
    echo [INFO] Frontend not started (Node.js missing).
    echo        Install Node.js and then run:
    echo          cd frontend ^&^& npm install ^&^& npm run dev
)

REM ---- 9. Print instructions ----
echo.
echo  ════════════════════════════════════════════════════
echo   PROTOTYPE RUNNING
echo  ════════════════════════════════════════════════════
echo.
echo   Dashboard:      http://localhost:5173
echo   API:            http://localhost:8000
echo   API Docs:       http://localhost:8000/docs
echo   SUMO Status:    %SUMO_STATUS%
echo.
echo   QUICK START:
echo     1. Open http://localhost:5173 in your browser
echo     2. Select controller: Agentic AI or Fixed-Time
echo     3. Select demand: medium (or asymmetric_ns for dramatic effect)
echo     4. Click START
echo     5. Watch the AI make real-time decisions
echo.
echo   COMPARISON EXPERIMENT (from another terminal):
echo     python run_experiment.py --controller both --demand medium --duration 1800
echo.
echo   RUN TESTS:
echo     pytest tests\ -v
echo.
echo   Press Ctrl+C in each terminal to stop.
echo  ════════════════════════════════════════════════════
echo.
pause
