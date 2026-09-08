"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 3: Step 2+3 — Anomaly & Sequence Matching Server

Port: 5003

This server:
  1. Subscribes to the Step 1 WebSocket (ws://localhost:5002/ws/telemetry)
     and ingests every telemetry row into a rolling buffer.
  2. On each new row, runs the AnomalyDetector (Z-score + CUSUM).
  3. Accumulates recent alerts and periodically runs SequenceMatcher
     (Smith-Waterman + Wilson CI) for each active hazard.
  4. Broadcasts both alerts and sequence-match results to connected UI clients
     via its own WebSocket (/ws/anomaly).
  5. Writes results to module3/outputs/risk_predictions.jsonl.

Endpoints
---------
  WebSocket:
    /ws/anomaly                          → Live alerts + risk updates
  REST:
    GET  /                               → Service info
    GET  /api/anomaly/status             → Buffer size, row count, detector config
    GET  /api/anomaly/alerts             → Last K alerts (JSON array)
    GET  /api/anomaly/buffer/stats       → Per-channel rolling stats
    GET  /api/sequence/match/latest      → Latest Wilson CI result per hazard
    POST /api/anomaly/ingest             → Manually ingest a single telemetry row
    POST /api/anomaly/reset              → Reset buffer + CUSUM state

Usage
-----
  python module3/anomaly_server.py --port 5003 --simulator-url ws://localhost:5002/ws/telemetry

IMPORTANT: Start simulator_server.py (port 5002) BEFORE starting this server.
"""

import asyncio
import json
import logging
import os
import sys
import argparse
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure module3 is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anomaly_detector import AnomalyDetector, HAZARD_CHANNEL_CONFIG
from sequence_matcher import SequenceMatcher, tokenize_alerts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("anomaly_server")


# ── Configuration ──────────────────────────────────────────────────────────────

BUFFER_MAX_ROWS: int = 300            # rolling telemetry buffer size
ALERT_HISTORY_MAX: int = 500          # max alerts retained in memory
SEQUENCE_ALERT_WINDOW: int = 50       # last N alerts fed into sequence matcher
SEQUENCE_MATCH_EVERY_N_ROWS: int = 25 # run SW alignment every N new rows
TARGET_WELL_ID: str = "15/9-F-9A"    # current well being drilled

# Outputs directory — created automatically
_MODULE3_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = _MODULE3_DIR / "outputs"
RISK_PREDICTIONS_PATH = OUTPUTS_DIR / "risk_predictions.jsonl"


# ── Global State ───────────────────────────────────────────────────────────────

# Rolling telemetry buffer: oldest at left, newest at right
telemetry_buffer: deque = deque(maxlen=BUFFER_MAX_ROWS)

# Alert history (newest appended)
alert_history: List[Dict[str, Any]] = []

# Latest sequence match results per hazard
latest_sequence_results: Dict[str, Dict[str, Any]] = {}

# Anomaly detector instance (stateful CUSUM)
detector: Optional[AnomalyDetector] = None

# Sequence matcher instance
matcher: Optional[SequenceMatcher] = None

# Row counter
row_count: int = 0

# Background task handles
_simulator_consumer_task: Optional[asyncio.Task] = None
_broadcast_task: Optional[asyncio.Task] = None

# Simulator WebSocket URL (set via CLI)
_simulator_url: str = "ws://localhost:5002/ws/telemetry"


# ── WebSocket Manager ─────────────────────────────────────────────────────────

class AlertBroadcastManager:
    """Manages connected UI clients on /ws/anomaly."""

    def __init__(self):
        self.clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.clients.add(ws)
        logger.info("Anomaly client connected. Total: %d", len(self.clients))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self.clients.discard(ws)

    async def broadcast(self, payload: Dict[str, Any]):
        if not self.clients:
            return
        text = json.dumps(payload)
        dead = set()
        async with self._lock:
            clients = list(self.clients)
        for ws in clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self.clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self.clients)


broadcast_manager = AlertBroadcastManager()


# ── Outputs Setup ─────────────────────────────────────────────────────────────

def ensure_outputs_dir():
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Outputs directory: %s", OUTPUTS_DIR)


def append_risk_prediction(result: Dict[str, Any]):
    """Append a hazard risk result to risk_predictions.jsonl."""
    try:
        with open(RISK_PREDICTIONS_PATH, "a", encoding="utf-8") as f:
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "well_id": TARGET_WELL_ID,
                **result,
            }
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error("Failed to write risk_predictions.jsonl: %s", e)


# ── Core Processing ───────────────────────────────────────────────────────────

def process_telemetry_row(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Ingest a single telemetry row:
      1. Add to rolling buffer.
      2. Run anomaly detection.
      3. Store new alerts.
    Returns list of new alerts (may be empty).
    """
    global row_count

    # Extract telemetry dict from the simulator message envelope
    # Simulator wraps data as: {"well_id":..., "row_index":..., "telemetry":{...}}
    if "telemetry" in row:
        telem = row["telemetry"]
        row_idx = row.get("row_index", row_count)
    else:
        # Fallback: raw row dict (for /api/anomaly/ingest)
        telem = row
        row_idx = row_count

    telemetry_buffer.append(telem)
    row_count += 1

    buf_list = list(telemetry_buffer)
    new_alerts = detector.detect(buffer=buf_list, current_row_index=row_idx)

    alert_dicts = [a.to_dict() for a in new_alerts]
    alert_history.extend(alert_dicts)

    # Trim history to max
    while len(alert_history) > ALERT_HISTORY_MAX:
        alert_history.pop(0)

    return alert_dicts


async def run_sequence_matching():
    """
    Run Smith-Waterman + Wilson CI for all hazards present in recent alerts.
    Updates `latest_sequence_results` and writes to risk_predictions.jsonl.
    Broadcasts results to connected clients.
    """
    global latest_sequence_results

    recent_alerts = alert_history[-SEQUENCE_ALERT_WINDOW:]
    if not recent_alerts:
        return

    try:
        results = matcher.match_all_hazards(
            alerts=recent_alerts,
            target_well_id=TARGET_WELL_ID,
        )
        for r in results:
            hazard = r["hazard"]
            latest_sequence_results[hazard] = r
            append_risk_prediction(r)

        if results:
            await broadcast_manager.broadcast({
                "type": "sequence_match",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "row_count": row_count,
                "results": results,
            })
            logger.info(
                "Sequence match complete: %d hazards evaluated.", len(results)
            )
    except Exception as e:
        logger.error("Sequence matching error: %s", e, exc_info=True)


# ── Simulator WebSocket Consumer ──────────────────────────────────────────────

async def consume_simulator_websocket():
    """
    Background task: connects to the Step 1 telemetry WebSocket and
    processes each incoming row.
    Reconnects automatically on disconnection.
    """
    global row_count

    logger.info("Starting simulator consumer → %s", _simulator_url)
    rows_since_match = 0

    while True:
        try:
            async with websockets.connect(
                _simulator_url,
                ping_interval=20,
                ping_timeout=10,
            ) as ws:
                logger.info("Connected to simulator WebSocket.")
                async for message in ws:
                    try:
                        row = json.loads(message)
                    except json.JSONDecodeError:
                        continue

                    # Skip control messages (event=stream_completed, info=...)
                    if "event" in row or "info" in row:
                        continue

                    new_alerts = process_telemetry_row(row)
                    rows_since_match += 1

                    # Broadcast new alerts immediately
                    if new_alerts:
                        await broadcast_manager.broadcast({
                            "type": "anomaly_alerts",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "row_count": row_count,
                            "buffer_size": len(telemetry_buffer),
                            "alerts": new_alerts,
                        })

                    # Run sequence match every N rows
                    if rows_since_match >= SEQUENCE_MATCH_EVERY_N_ROWS:
                        rows_since_match = 0
                        await run_sequence_matching()

        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            logger.warning(
                "Simulator WebSocket disconnected (%s). Retrying in 5s...", e
            )
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            logger.info("Simulator consumer task cancelled.")
            break
        except Exception as e:
            logger.error("Unexpected error in simulator consumer: %s", e, exc_info=True)
            await asyncio.sleep(5.0)


# ── FastAPI Lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector, matcher, _simulator_consumer_task

    ensure_outputs_dir()

    # Initialise detector
    detector = AnomalyDetector()
    logger.info("AnomalyDetector initialised.")

    # Initialise and load sequence matcher
    matcher = SequenceMatcher()
    try:
        matcher.load()
        logger.info("SequenceMatcher loaded all backing data.")
    except Exception as e:
        logger.error("SequenceMatcher failed to load: %s", e)

    # Start simulator consumer background task
    _simulator_consumer_task = asyncio.create_task(consume_simulator_websocket())

    yield

    # Shutdown
    if _simulator_consumer_task:
        _simulator_consumer_task.cancel()
        try:
            await _simulator_consumer_task
        except asyncio.CancelledError:
            pass
    logger.info("Anomaly server shutdown complete.")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="NWIS-Sentinel Anomaly & Sequence Matching Server",
    description=(
        "Module 3 Step 2+3: Real-time precursor/anomaly detection "
        "(Z-score + CUSUM) and Smith-Waterman sequence matching with "
        "Wilson Score CI against analog well historical sequences."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount outputs directory as static files for plots and JSONs
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")


# ── Web UI & REST Endpoints ───────────────────────────────────────────────────

@app.get("/monitor", response_class=FileResponse)
def get_monitor_page():
    """Serve the interactive NWIS-Sentinel Module 3 Web Monitor."""
    monitor_path = _MODULE3_DIR / "monitor.html"
    if not monitor_path.exists():
        raise HTTPException(status_code=404, detail="monitor.html not found")
    return FileResponse(monitor_path)


@app.get("/api/backtest/results")
def get_backtest_results():
    """Return the flagship Step 4 time-travel backtest results."""
    p = OUTPUTS_DIR / "backtest_result.json"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="Backtest results not found. Run module3/backtest_runner.py first.")


@app.get("/api/sequence/matches")
def get_sequence_matches():
    """Return the Step 5 sequence_matches.json data."""
    p = OUTPUTS_DIR / "sequence_matches.json"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    raise HTTPException(status_code=404, detail="sequence_matches.json not found.")


@app.get("/")
def root():
    return {
        "service": "NWIS-Sentinel Anomaly & Sequence Matching Server",
        "role": "Module 3 Predictive Intelligence & Backtest Engine",
        "methods": ["Rolling Z-score", "CUSUM", "Smith-Waterman alignment", "Wilson Score CI"],
        "simulator_source": _simulator_url,
        "websocket_endpoint": "/ws/anomaly",
        "web_ui": "GET /monitor",
        "flagship_backtest_plot": "GET /outputs/backtest_plot.png",
        "endpoints": {
            "monitor_ui":    "GET /monitor",
            "backtest":      "GET /api/backtest/results",
            "sequence_all":  "GET /api/sequence/matches",
            "status":        "GET /api/anomaly/status",
            "alerts":        "GET /api/anomaly/alerts",
            "buffer_stats":  "GET /api/anomaly/buffer/stats",
            "sequence":      "GET /api/sequence/match/latest",
            "ingest":        "POST /api/anomaly/ingest",
            "reset":         "POST /api/anomaly/reset",
        },
    }


@app.get("/api/anomaly/status")
def get_status():
    """Operational status: buffer size, alert count, detector config."""
    return {
        "well_id": TARGET_WELL_ID,
        "simulator_url": _simulator_url,
        "total_rows_processed": row_count,
        "buffer_size": len(telemetry_buffer),
        "buffer_max": BUFFER_MAX_ROWS,
        "total_alerts_generated": len(alert_history),
        "active_websocket_clients": broadcast_manager.client_count,
        "detector_config": {
            "zscore_window": detector.zscore_window if detector else None,
            "zscore_threshold": detector.zscore_threshold if detector else None,
            "cusum_k_sigma": detector.cusum_k_sigma if detector else None,
            "cusum_h_sigma": detector.cusum_h_sigma if detector else None,
            "min_rows_needed": detector.min_rows if detector else None,
            "monitored_channels": len(HAZARD_CHANNEL_CONFIG),
        },
        "sequence_matcher_loaded": matcher.store.is_loaded if matcher else False,
        "latest_hazards_assessed": list(latest_sequence_results.keys()),
    }


@app.get("/api/anomaly/alerts")
def get_alerts(last_n: int = 50):
    """Return the last N anomaly alerts."""
    if last_n <= 0 or last_n > ALERT_HISTORY_MAX:
        last_n = 50
    alerts = alert_history[-last_n:]
    return {
        "count": len(alerts),
        "last_n": last_n,
        "alerts": alerts,
    }


@app.get("/api/anomaly/buffer/stats")
def get_buffer_stats():
    """Per-channel rolling statistics from the current telemetry buffer."""
    if detector is None:
        raise HTTPException(status_code=503, detail="Detector not initialised")
    buf = list(telemetry_buffer)
    stats = detector.compute_channel_stats(buf)
    return {
        "buffer_size": len(buf),
        "row_count": row_count,
        "channel_stats": stats,
    }


@app.get("/api/sequence/match/latest")
def get_latest_sequence():
    """Return the latest Wilson CI sequence match results for all evaluated hazards."""
    if not latest_sequence_results:
        return {
            "message": "No sequence match results yet. "
                       "Sequence matching runs every "
                       f"{SEQUENCE_MATCH_EVERY_N_ROWS} rows once "
                       "alerts are generated.",
            "results": [],
        }
    # Sort by risk level for readability
    risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_results = sorted(
        latest_sequence_results.values(),
        key=lambda r: risk_order.get(r.get("risk_level", "LOW"), 4),
    )
    return {
        "well_id": TARGET_WELL_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": sorted_results,
    }


class IngestRequest(BaseModel):
    row: Dict[str, Any] = Field(..., description="Single telemetry row dict")


@app.post("/api/anomaly/ingest")
async def ingest_row(req: IngestRequest):
    """
    Manually ingest a single telemetry row (polling/testing fallback).
    Returns any new alerts generated by this row.
    """
    if detector is None:
        raise HTTPException(status_code=503, detail="Detector not initialised")
    new_alerts = process_telemetry_row(req.row)
    if new_alerts:
        await broadcast_manager.broadcast({
            "type": "anomaly_alerts",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "row_count": row_count,
            "buffer_size": len(telemetry_buffer),
            "alerts": new_alerts,
        })
    return {
        "new_alerts": len(new_alerts),
        "alerts": new_alerts,
        "buffer_size": len(telemetry_buffer),
        "total_row_count": row_count,
    }


@app.post("/api/anomaly/reset")
def reset_state():
    """Reset rolling buffer, CUSUM state, alert history, and row counter."""
    global row_count, alert_history, latest_sequence_results
    telemetry_buffer.clear()
    alert_history.clear()
    latest_sequence_results.clear()
    row_count = 0
    if detector:
        detector.reset_cusum_state()
    return {"message": "Buffer, CUSUM state, alert history, and row counter reset."}


# ── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/anomaly")
async def websocket_anomaly(websocket: WebSocket):
    """
    Live WebSocket stream of anomaly alerts and sequence match results.
    Clients receive:
      - {"type": "anomaly_alerts", "alerts": [...]}    when new alerts fire
      - {"type": "sequence_match", "results": [...]}   every N rows
    """
    await broadcast_manager.connect(websocket)

    # Send current state snapshot to newly connected client
    try:
        snapshot = {
            "type": "snapshot",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "buffer_size": len(telemetry_buffer),
            "row_count": row_count,
            "recent_alerts": alert_history[-20:],
            "latest_sequence": list(latest_sequence_results.values()),
        }
        await websocket.send_text(json.dumps(snapshot))
    except Exception:
        pass

    try:
        while True:
            # Keep connection open; all output is pushed by the broadcaster
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        await broadcast_manager.disconnect(websocket)
    except Exception:
        await broadcast_manager.disconnect(websocket)


# ── CLI Launcher ──────────────────────────────────────────────────────────────

def main():
    global _simulator_url

    parser = argparse.ArgumentParser(
        description="NWIS-Sentinel Anomaly & Sequence Matching Server (Module 3 Step 2+3)"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=5003, help="Port to listen on (default: 5003)"
    )
    parser.add_argument(
        "--simulator-url",
        default="ws://localhost:5002/ws/telemetry",
        help="Step 1 simulator WebSocket URL (default: ws://localhost:5002/ws/telemetry)",
    )
    args = parser.parse_args()

    _simulator_url = args.simulator_url

    import uvicorn

    print("=" * 70)
    print("NWIS-Sentinel — Module 3 Anomaly & Sequence Matching Server")
    print("Step 2: Z-score + CUSUM Anomaly Detector")
    print("Step 3: Smith-Waterman Alignment + Wilson Score CI")
    print("=" * 70)
    print(f"  Listening on : http://{args.host}:{args.port}")
    print(f"  Simulator    : {_simulator_url}")
    print(f"  WebSocket    : ws://{args.host}:{args.port}/ws/anomaly")
    print(f"  Alerts API   : http://{args.host}:{args.port}/api/anomaly/alerts")
    print(f"  Sequence API : http://{args.host}:{args.port}/api/sequence/match/latest")
    print(f"  Outputs      : {OUTPUTS_DIR}")
    print("=" * 70)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
