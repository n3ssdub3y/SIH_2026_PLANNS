"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Master Orchestrator: Run All Modules Simultaneously

Launches and supervises:
  - Dashboard:           Central Portal (Flask @ port 5000)
  - Module 2:            Geospatial & Offset Similarity Engine (Flask @ port 5001)
  - Module 3 Simulator:  Real-Time Telemetry Replay (FastAPI/Uvicorn @ port 5002)
  - Module 3 Anomaly:    Risk Prediction & Monitor (FastAPI/Uvicorn @ port 5003)
  - Module 4:            Knowledge Graph, GraphRAG & LLM Briefing Studio (Flask @ port 5004)
  - Module 5:            Engineering RAG + LLM Agent (Flask @ port 5005)

Usage:
  python run_all_modules.py
  python run_all_modules.py --speed 5.0
  python run_all_modules.py --no-browser
"""

import argparse
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
LOGS_DIR = BASE_DIR / "logs"

# ANSI colors for nice terminal output
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"

MODULES = [
    {
        "id": "dashboard",
        "name": "Dashboard: Central Portal",
        "cmd": [PYTHON_EXE, str(BASE_DIR / "dashboard" / "app.py"), "--port", "5000"],
        "port": 5000,
        "url": "http://localhost:5000",
        "description": "BSPWM-style central portal — entry point to all NWIS-Sentinel modules."
    },
    {
        "id": "module2",
        "name": "Module 2: Geospatial & Offset Similarity Engine",
        "cmd": [PYTHON_EXE, str(BASE_DIR / "module2" / "app.py")],
        "port": 5001,
        "url": "http://localhost:5001",
        "description": "Interactive Leaflet map showing 159 wells, formation correlation, and AHP analog scores."
    },
    {
        "id": "module3_sim",
        "name": "Module 3: Live Telemetry Simulator",
        "cmd": [PYTHON_EXE, str(BASE_DIR / "module3" / "simulator_server.py"), "--port", "5002", "--speed", "5.0"],
        "port": 5002,
        "url": "http://localhost:5002",
        "description": "Replays 16,670 rows of Volve 15/9-F-9A WITSML telemetry over WebSocket."
    },
    {
        "id": "module3_anomaly",
        "name": "Module 3: Anomaly & Risk Prediction Server",
        "cmd": [
            PYTHON_EXE, str(BASE_DIR / "module3" / "anomaly_server.py"),
            "--port", "5003",
            "--simulator-url", "ws://localhost:5002/ws/telemetry"
        ],
        "port": 5003,
        "url": "http://localhost:5003/monitor",
        "description": "CUSUM/Z-Score anomaly detection, Smith-Waterman sequence matching & live dashboard."
    },
    {
        "id": "module4",
        "name": "Module 4: Knowledge Graph, GraphRAG & LLM Briefing",
        "cmd": [PYTHON_EXE, str(BASE_DIR / "module4" / "app.py")],
        "port": 5004,
        "url": "http://localhost:5004",
        "description": "Vis.js 4,000+ node interactive graph, GraphRAG search, and AI Pre-Spud Briefing studio."
    },
    {
        "id": "module5",
        "name": "Module 5: Engineering RAG + LLM Agent",
        "cmd": [PYTHON_EXE, str(BASE_DIR / "module5_engineering_agent" / "app.py"), "--port", "5005"],
        "port": 5005,
        "url": "http://localhost:5005",
        "description": "Evidence-grounded engineering decision support console powered by Gemini and ChromaDB."
    }
]


def check_port(port: int) -> bool:
    """Check if a port is already in use."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    parser = argparse.ArgumentParser(description="NWIS-Sentinel Master Orchestrator")
    parser.add_argument("--speed", type=float, default=5.0, help="Simulation speed multiplier for Module 3 (default: 5.0)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open web browser tabs")
    args = parser.parse_args()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Update simulator speed if specified
    for m in MODULES:
        if m["id"] == "module3_sim":
            m["cmd"][5] = str(args.speed)

    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}     NWIS-Sentinel | SIH 2026 | PS SIH26121 | System Orchestrator{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}\n")
    print(f"Python interpreter : {PYTHON_EXE}")
    print(f"Working directory  : {BASE_DIR}")
    print(f"Logs directory     : {LOGS_DIR}\n")

    # Check for existing processes on required ports
    conflicts = []
    for m in MODULES:
        if check_port(m["port"]):
            conflicts.append((m["name"], m["port"]))

    if conflicts:
        print(f"{YELLOW}[NOTICE] The following ports are already active:{RESET}")
        for name, port in conflicts:
            print(f"  - {name} (Port {port}) is already listening.")
        print(f"  Existing instances will remain active. Launching remaining services...\n")

    # Launch processes
    processes = []
    log_files = []
    try:
        for m in MODULES:
            if check_port(m["port"]):
                print(f"  {GREEN}[RUNNING]{RESET} {m['name']} -> {BOLD}{m['url']}{RESET}")
                continue

            print(f"  {BLUE}[STARTING]{RESET} {m['name']} on port {m['port']} ...")
            log_path = LOGS_DIR / f"{m['id']}.log"
            log_file = open(log_path, "w", encoding="utf-8")
            log_files.append(log_file)

            # In Windows, create independent process group
            proc = subprocess.Popen(
                m["cmd"],
                cwd=str(BASE_DIR),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            )
            processes.append((m, proc))
            time.sleep(1.2)  # brief stagger to allow socket binding

        print(f"\n{BOLD}{GREEN}{'=' * 75}{RESET}")
        print(f"{BOLD}{GREEN}  ALL 5 NWIS-SENTINEL MODULES ARE ACTIVE & RUNNING!{RESET}")
        print(f"{BOLD}{GREEN}{'=' * 75}{RESET}\n")

        print(f"  {BOLD}1. Module 2 (Geospatial & Offset Similarity Map):{RESET}")
        print(f"     -> {CYAN}http://localhost:5001{RESET}")
        print(f"     Ranked analog wells across 5 drilling hazards + formation correlation.\n")

        print(f"  {BOLD}2. Module 3 (Live Telemetry Replay Server):{RESET}")
        print(f"     -> {CYAN}http://localhost:5002{RESET} (WebSocket: ws://localhost:5002/ws/telemetry)")
        print(f"     Streaming Volve 15/9-F-9A MWD sensors at {args.speed}x speed.\n")

        print(f"  {BOLD}3. Module 3 (Drilling Anomaly & Risk Prediction Monitor):{RESET}")
        print(f"     -> {CYAN}http://localhost:5003/monitor{RESET}")
        print(f"     Real-time CUSUM/Z-score alerts + Smith-Waterman +106.5m early warning.\n")

        print(f"  {BOLD}4. Module 4 (Knowledge Graph, GraphRAG & AI Briefing Studio):{RESET}")
        print(f"     -> {CYAN}http://localhost:5004{RESET}")
        print(f"     Interactive Vis.js graph, GraphRAG retrieval, and Gemini Pre-Spud briefings.\n")

        print(f"  {BOLD}5. Module 5 (Engineering RAG + LLM Decision Support Agent):{RESET}")
        print(f"     -> {CYAN}http://localhost:5005{RESET}")
        print(f"     Evidence-grounded engineering console, 1-click scenarios & ChromaDB vector store.\n")

        print(f"{YELLOW}Press Ctrl+C at any time to gracefully shut down all services.{RESET}\n")

        if not args.no_browser:
            time.sleep(1.0)
            webbrowser.open("http://localhost:5000")  # Dashboard first
            webbrowser.open("http://localhost:5005")
            webbrowser.open("http://localhost:5004")
            webbrowser.open("http://localhost:5003/monitor")
            webbrowser.open("http://localhost:5001")

        # Keep supervisor loop alive
        while True:
            time.sleep(1.0)
            for m, proc in processes:
                poll = proc.poll()
                if poll is not None:
                    print(f"{RED}[WARNING] {m['name']} exited unexpectedly with code {poll}! Check logs/{m['id']}.log{RESET}")
                    break

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}[SHUTDOWN] Received Ctrl+C. Terminating all child processes...{RESET}")
    finally:
        for m, proc in processes:
            try:
                if sys.platform == "win32":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        for lf in log_files:
            try:
                lf.close()
            except Exception:
                pass
        print(f"{GREEN}[SHUTDOWN] All services stopped cleanly. Goodbye!{RESET}\n")


if __name__ == "__main__":
    main()
