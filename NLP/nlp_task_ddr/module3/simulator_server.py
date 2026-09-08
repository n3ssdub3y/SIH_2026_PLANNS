"""
Live Telemetry Simulator — production version would connect directly to eRTMAC's WITSML feed.

NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 3: Step 1 - WebSocket & REST Streaming Server

Endpoints:
  WebSocket:
    /ws/telemetry              -> Live sequential row-by-row telemetry stream
  REST:
    GET  /                     -> Service info & operational guidelines
    GET  /api/telemetry/status -> Replay progress, streaming speed, active clients
    GET  /api/telemetry/current-> Latest emitted telemetry snapshot (polling fallback)
    POST /api/telemetry/config -> Update delay, speed multiplier, loop mode
    POST /api/telemetry/reset  -> Reset playback to row 0
    POST /api/telemetry/pause  -> Pause playback
    POST /api/telemetry/resume -> Resume playback

Usage:
  python simulator_server.py --port 5002 --interval 1.0 --speed 1.0
"""

import sys
import os
import json
import asyncio
import argparse
import logging
from typing import Set, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path

# Ensure local module directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telemetry_simulator import TelemetrySimulator, DEFAULT_DATA_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("simulator_server")


# ── Global State & Connection Manager ──────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections for live broadcasting."""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info("Client connected. Total active clients: %d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info("Client disconnected. Total active clients: %d", len(self.active_connections))

    async def broadcast(self, message: Dict[str, Any]):
        """Send message to all connected clients. Remove broken connections gracefully."""
        if not self.active_connections:
            return

        text = json.dumps(message)
        dead_connections = set()

        async with self._lock:
            clients = list(self.active_connections)

        for connection in clients:
            try:
                await connection.send_text(text)
            except Exception as e:
                logger.debug("Failed sending to client (%s), queueing removal", e)
                dead_connections.add(connection)

        if dead_connections:
            async with self._lock:
                for dead in dead_connections:
                    self.active_connections.discard(dead)
            logger.info("Cleaned up %d disconnected client(s)", len(dead_connections))

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()
simulator: Optional[TelemetrySimulator] = None
_broadcast_task: Optional[asyncio.Task] = None
_latest_emitted: Optional[Dict[str, Any]] = None


async def telemetry_broadcaster_loop():
    """
    Background continuous loop that advances the simulator row-by-row
    and broadcasts to all connected WebSocket clients.
    """
    global _latest_emitted
    logger.info("Telemetry broadcast background worker started.")

    while True:
        try:
            if simulator is None:
                await asyncio.sleep(0.5)
                continue

            if simulator.is_paused:
                await asyncio.sleep(0.2)
                continue

            # Advance to next telemetry record
            record = simulator.advance_next_record()
            if record:
                _latest_emitted = record
                await manager.broadcast(record)

            # Sleep for the configured inter-row interval
            delay = simulator.delay_seconds
            await asyncio.sleep(delay)

        except asyncio.CancelledError:
            logger.info("Telemetry broadcast worker cancelled.")
            break
        except Exception as e:
            logger.error("Error in telemetry broadcast loop: %s", e, exc_info=True)
            await asyncio.sleep(1.0)


# ── FastAPI Application Lifespan ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _broadcast_task, simulator
    # Initialize simulator if not already initialized
    if simulator is None:
        csv_path = os.getenv("TELEMETRY_CSV_PATH", str(DEFAULT_DATA_PATH))
        base_int = float(os.getenv("TELEMETRY_BASE_INTERVAL", "1.0"))
        speed_mult = float(os.getenv("TELEMETRY_SPEED_MULTIPLIER", "1.0"))
        simulator = TelemetrySimulator(
            csv_path=csv_path,
            base_interval=base_int,
            speed_multiplier=speed_mult,
            loop=True
        )

    _broadcast_task = asyncio.create_task(telemetry_broadcaster_loop())
    yield
    if _broadcast_task:
        _broadcast_task.cancel()
        try:
            await _broadcast_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="NWIS-Sentinel Live Telemetry Simulator",
    description="Simulates live eRTMAC/WITSML drilling telemetry feed row-by-row for Module 3 and Module 4 consumption.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────────

class ConfigUpdateRequest(BaseModel):
    base_interval: Optional[float] = Field(None, description="Delay between rows in seconds (e.g. 0.1, 0.5, 1.0, 2.0)")
    speed_multiplier: Optional[float] = Field(None, description="Playback speed multiplier (e.g. 1.0, 5.0, 10.0, 100.0)")
    loop: Optional[bool] = Field(None, description="Whether to loop back to row 0 when finished")


class TelemetryControlRequest(BaseModel):
    action: str = Field(..., description="Action: 'pause', 'resume', 'reset', 'set_speed', 'set_interval'")
    speed_multiplier: Optional[float] = Field(None, description="Playback speed multiplier")
    speed: Optional[float] = Field(None, description="Alias for speed_multiplier")
    base_interval: Optional[float] = Field(None, description="Base interval in seconds")
    interval: Optional[float] = Field(None, description="Alias for base_interval")


# ── REST Routes ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "NWIS-Sentinel Live Telemetry Simulator",
        "role": "Module 3 Step 1 Live Replay Service",
        "production_note": "Live Telemetry Simulator — production version would connect directly to eRTMAC's WITSML feed.",
        "websocket_endpoint": "/ws/telemetry",
        "dashboard_ui": "/monitor",
        "status_endpoint": "/api/telemetry/status",
        "current_snapshot_endpoint": "/api/telemetry/current"
    }


@app.get("/monitor")
def monitor_dashboard():
    """Serve the interactive live telemetry monitor dashboard."""
    html_file = Path(__file__).resolve().parent / "monitor.html"
    return FileResponse(html_file, media_type="text/html")


@app.get("/api/telemetry/status")
def get_telemetry_status():
    """Return simulator status, current depth, row index, and client count."""
    if simulator is None:
        raise HTTPException(status_code=503, detail="Simulator not initialized")
    status = simulator.get_status()
    status["active_websocket_clients"] = manager.client_count
    return status


@app.get("/api/telemetry/current")
def get_current_telemetry():
    """Polling fallback: returns the latest emitted row snapshot."""
    if _latest_emitted is not None:
        return _latest_emitted
    if simulator is not None:
        rec = simulator.get_current_record()
        if rec:
            return rec
    raise HTTPException(status_code=503, detail="No telemetry available yet")


@app.post("/api/telemetry/config")
def update_telemetry_config(req: ConfigUpdateRequest):
    """Update streaming speed, interval, or loop settings dynamically."""
    if simulator is None:
        raise HTTPException(status_code=503, detail="Simulator not initialized")

    if req.base_interval is not None:
        simulator.set_base_interval(req.base_interval)
    if req.speed_multiplier is not None:
        simulator.set_speed_multiplier(req.speed_multiplier)
    if req.loop is not None:
        simulator.loop = req.loop

    return {
        "message": "Configuration updated successfully",
        "new_status": simulator.get_status()
    }


@app.post("/api/telemetry/reset")
def reset_telemetry():
    """Reset stream back to row 0."""
    if simulator is None:
        raise HTTPException(status_code=503, detail="Simulator not initialized")
    simulator.reset()
    return {"message": "Stream reset to row 0", "status": simulator.get_status()}


@app.post("/api/telemetry/pause")
def pause_telemetry():
    """Pause stream."""
    if simulator is None:
        raise HTTPException(status_code=503, detail="Simulator not initialized")
    simulator.pause()
    return {"message": "Stream paused", "is_paused": True}


@app.post("/api/telemetry/resume")
def resume_telemetry():
    """Resume stream."""
    if simulator is None:
        raise HTTPException(status_code=503, detail="Simulator not initialized")
    simulator.resume()
    return {"message": "Stream resumed", "is_paused": False}


@app.post("/api/telemetry/control")
def control_telemetry(req: TelemetryControlRequest):
    """Unified control endpoint for pause, resume, reset, and speed changes."""
    if simulator is None:
        raise HTTPException(status_code=503, detail="Simulator not initialized")

    act = req.action.lower().strip()
    if act == "pause":
        simulator.pause()
        return {"status": "success", "action": "pause", "is_paused": True}
    elif act == "resume":
        simulator.resume()
        return {"status": "success", "action": "resume", "is_paused": False}
    elif act == "reset":
        simulator.reset()
        return {"status": "success", "action": "reset", "is_paused": False, "current_row": 0}
    elif act in ("set_speed", "speed"):
        speed_val = req.speed_multiplier if req.speed_multiplier is not None else req.speed
        if speed_val is None:
            speed_val = 1.0
        eff = simulator.set_speed_multiplier(speed_val)
        return {"status": "success", "action": "set_speed", "speed_multiplier": speed_val, "delay_seconds": eff}
    elif act in ("set_interval", "interval"):
        inv = req.base_interval if req.base_interval is not None else req.interval
        if inv is None:
            inv = 1.0
        eff = simulator.set_base_interval(inv)
        return {"status": "success", "action": "set_interval", "base_interval": inv, "delay_seconds": eff}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown control action: '{req.action}'")


# ── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for live row-by-row drilling telemetry.
    Clients receive each record as valid JSON with all original feature names.
    Clients can also send control commands:
      {"action": "set_speed", "speed": 10.0}
      {"action": "set_interval", "interval": 0.5}
      {"action": "pause"}
      {"action": "resume"}
      {"action": "reset"}
    """
    await manager.connect(websocket)

    # If there is already a latest record, send it immediately as initial state
    if _latest_emitted is not None:
        try:
            await websocket.send_text(json.dumps(_latest_emitted))
        except Exception:
            pass

    try:
        while True:
            # Listen for optional incoming control messages from client
            data_str = await websocket.receive_text()
            try:
                msg = json.loads(data_str)
                action = msg.get("action")
                if action == "set_speed":
                    speed = float(msg.get("speed", 1.0))
                    simulator.set_speed_multiplier(speed)
                    await websocket.send_text(json.dumps({"info": f"Speed multiplier updated to {speed}x"}))
                elif action == "set_interval":
                    interval = float(msg.get("interval", 1.0))
                    simulator.set_base_interval(interval)
                    await websocket.send_text(json.dumps({"info": f"Base interval updated to {interval}s"}))
                elif action == "pause":
                    simulator.pause()
                    await websocket.send_text(json.dumps({"info": "Stream paused"}))
                elif action == "resume":
                    simulator.resume()
                    await websocket.send_text(json.dumps({"info": "Stream resumed"}))
                elif action == "reset":
                    simulator.reset()
                    await websocket.send_text(json.dumps({"info": "Stream reset to row 0"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.warning("WebSocket client error: %s", e)
        await manager.disconnect(websocket)


# ── Server CLI Launcher ───────────────────────────────────────────────────────

def main():
    global simulator
    parser = argparse.ArgumentParser(description="Live Telemetry Simulator Server (NWIS-Sentinel Module 3)")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5002, help="Port to listen on (default: 5002)")
    parser.add_argument("--interval", type=float, default=1.0, help="Base interval in seconds between rows (default: 1.0)")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed multiplier (default: 1.0)")
    parser.add_argument("--csv", default=str(DEFAULT_DATA_PATH), help="Path to telemetry CSV")
    parser.add_argument("--no-loop", action="store_true", help="Stop at end of file instead of looping")
    args = parser.parse_args()

    # Pre-configure simulator
    simulator = TelemetrySimulator(
        csv_path=args.csv,
        base_interval=args.interval,
        speed_multiplier=args.speed,
        loop=not args.no_loop
    )

    import uvicorn
    print("=" * 70)
    print("NWIS-Sentinel — Module 3 Live Telemetry Simulator Server")
    print("Production Note: Production version would connect directly to eRTMAC WITSML feed.")
    print("=" * 70)
    print(f"  Dataset       : {args.csv}")
    print(f"  Total Rows    : {simulator.total_rows}")
    print(f"  Features      : {len(simulator.columns)}")
    print(f"  Interval      : {args.interval}s (Speed: {args.speed}x -> Delay: {simulator.delay_seconds:.3f}s)")
    print(f"  WebSocket URL : ws://{args.host}:{args.port}/ws/telemetry")
    print(f"  REST API URL  : http://{args.host}:{args.port}/api/telemetry/status")
    print("=" * 70)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
