"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Gateway: Single-Port Orchestrator

Runs all modules on internal ports and exposes a single port 5000.

URL Map
-------
  GET  /                       - Dashboard UI
  GET  /module2/*              - Module 2  (internal :15001)
  GET  /module3/monitor        - Module 3 Monitor UI (proxied from :15003)
  ANY  /module3/sim/*          - Module 3 Simulator REST (internal :15002)
  ANY  /module3/anomaly/*      - Module 3 Anomaly REST  (internal :15003)
  WS   /ws/telemetry           - WebSocket proxy - :15002/ws/telemetry
  WS   /ws/anomaly             - WebSocket proxy - :15003/ws/anomaly
  GET  /module4/*              - Module 4  (internal :15004)
  GET  /module5/*              - Module 5  (internal :15005)

Usage:
  python gateway.py
  python gateway.py --port 5000 --speed 5.0 --no-browser
"""

import argparse
import asyncio
import logging
import subprocess
import sys
import time
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

# -- Paths -------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
LOGS_DIR   = BASE_DIR / "logs"

# -- Internal port assignments (hidden from outside world) -------------------
INTERNAL = {
    "module2":         15001,
    "module3_sim":     15002,
    "module3_anomaly": 15003,
    "module4":         15004,
    "module5":         15005,
}

# -- Logging -----------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gateway")

# -- Process registry --------------------------------------------------------
_processes = []

# -- Simulation speed (set via CLI) ------------------------------------------
_sim_speed = 5.0


# -- Subprocess management ---------------------------------------------------

def _start_module(name, cmd, log_file):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / log_file
    logger.info("Starting %-20s -> %s", name, " ".join(cmd))
    with open(log_path, "w") as lf:
        p = subprocess.Popen(cmd, stdout=lf, stderr=lf, cwd=str(BASE_DIR))
    return p


def _wait_for_port(port, timeout=60.0):
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def start_all_modules():
    global _processes, _sim_speed

    modules = [
        {
            "name": "module2",
            "cmd":  [PYTHON_EXE, str(BASE_DIR / "module2" / "app.py"),
                     "--port", str(INTERNAL["module2"])],
            "log":  "module2.log",
            "port": INTERNAL["module2"],
        },
        {
            "name": "module3_sim",
            "cmd":  [PYTHON_EXE, str(BASE_DIR / "module3" / "simulator_server.py"),
                     "--port", str(INTERNAL["module3_sim"]),
                     "--speed", str(_sim_speed)],
            "log":  "module3_sim.log",
            "port": INTERNAL["module3_sim"],
        },
        {
            "name": "module3_anomaly",
            "cmd":  [PYTHON_EXE, str(BASE_DIR / "module3" / "anomaly_server.py"),
                     "--port", str(INTERNAL["module3_anomaly"]),
                     "--simulator-url",
                     f"ws://localhost:{INTERNAL['module3_sim']}/ws/telemetry"],
            "log":  "module3_anomaly.log",
            "port": INTERNAL["module3_anomaly"],
        },
        {
            "name": "module4",
            "cmd":  [PYTHON_EXE, str(BASE_DIR / "module4" / "app.py"),
                     "--port", str(INTERNAL["module4"])],
            "log":  "module4.log",
            "port": INTERNAL["module4"],
        },
        {
            "name": "module5",
            "cmd":  [PYTHON_EXE,
                     str(BASE_DIR / "module5_engineering_agent" / "app.py"),
                     "--port", str(INTERNAL["module5"])],
            "log":  "module5.log",
            "port": INTERNAL["module5"],
        },
    ]

    for m in modules:
        p = _start_module(m["name"], m["cmd"], m["log"])
        _processes.append(p)

    logger.info("Waiting for all modules to come online (parallel check)...")
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def check_module(m):
        # module3_anomaly loads a 78MB JSON — give it more time, others 90s
        timeout = 180 if m["name"] == "module3_anomaly" else 90
        ok = _wait_for_port(m["port"], timeout=timeout)
        return m["name"], m["port"], ok

    with ThreadPoolExecutor(max_workers=len(modules)) as pool:
        futures = {pool.submit(check_module, m): m for m in modules}
        for fut in as_completed(futures):
            name, port, ok = fut.result()
            logger.info("  %-20s port:%d  %s", name, port, "UP" if ok else "TIMEOUT")


    logger.info("All modules started. Gateway ready -> http://localhost:5000")



def stop_all_modules():
    for p in _processes:
        try:
            p.terminate()
        except Exception:
            pass
    for p in _processes:
        try:
            p.wait(timeout=5)
        except Exception:
            pass
    logger.info("All module processes terminated.")


# -- FastAPI Lifespan --------------------------------------------------------

@asynccontextmanager
async def lifespan(app):
    global _http_client
    _http_client = httpx.AsyncClient(timeout=120.0, follow_redirects=True)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, start_all_modules)
    yield
    stop_all_modules()
    await _http_client.aclose()


# -- FastAPI App -------------------------------------------------------------

app = FastAPI(lifespan=lifespan, title="NWIS-Sentinel Gateway")

app.mount("/assets", StaticFiles(directory=str(BASE_DIR.parent.parent / "assets")), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_http_client = None


# -- Generic HTTP reverse proxy ----------------------------------------------

HOP_BY_HOP = {"host", "content-length", "transfer-encoding", "connection",
               "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailers", "upgrade"}


async def proxy_http(request, target_url):
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in HOP_BY_HOP}
    body = await request.body()
    try:
        resp = await _http_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            params=dict(request.query_params),
        )
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return Response(
            content=f"Gateway: upstream unavailable ({e})",
            status_code=503,
            media_type="text/plain",
        )

    resp_headers = {k: v for k, v in resp.headers.items()
                    if k.lower() not in {"content-encoding", "transfer-encoding",
                                         "connection"}}
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=resp.headers.get("content-type"),
    )


# -- WebSocket reverse proxy -------------------------------------------------

async def proxy_websocket(client_ws, backend_ws_url):
    await client_ws.accept()
    try:
        async with websockets.connect(
            backend_ws_url,
            ping_interval=20,
            ping_timeout=10,
            open_timeout=15,
        ) as backend_ws:

            async def browser_to_backend():
                try:
                    async for msg in client_ws.iter_text():
                        await backend_ws.send(msg)
                except Exception:
                    pass

            async def backend_to_browser():
                try:
                    async for msg in backend_ws:
                        text = msg if isinstance(msg, str) else msg.decode()
                        await client_ws.send_text(text)
                except Exception:
                    pass

            await asyncio.gather(browser_to_backend(), backend_to_browser())

    except Exception as e:
        logger.warning("WebSocket proxy error: %s", e)
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass


# -- Routes ------------------------------------------------------------------

# Dashboard
@app.get("/")
async def dashboard():
    from fastapi.responses import FileResponse
    return FileResponse(BASE_DIR / "dashboard" / "templates" / "dashboard.html")


# Module 2
@app.api_route("/module2", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_module2_root(request: Request):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module2']}/")

@app.api_route("/module2/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_module2(request: Request, path: str):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module2']}/{path}")


# Module 3 - Monitor UI
@app.get("/module3/monitor")
async def module3_monitor(request: Request):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module3_anomaly']}/monitor")


# Module 3 - Static outputs (plots, JSONs)
@app.api_route("/module3/outputs/{path:path}", methods=["GET", "HEAD"])
async def proxy_module3_outputs(request: Request, path: str):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module3_anomaly']}/outputs/{path}")


# Module 3 - Simulator REST
@app.api_route("/module3/sim/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_module3_sim(request: Request, path: str):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module3_sim']}/{path}")


# Module 3 - Anomaly REST
@app.api_route("/module3/anomaly/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy_module3_anomaly(request: Request, path: str):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module3_anomaly']}/{path}")


# Module 3 - WebSocket proxies
@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await proxy_websocket(websocket, f"ws://localhost:{INTERNAL['module3_sim']}/ws/telemetry")

@app.websocket("/ws/anomaly")
async def ws_anomaly(websocket: WebSocket):
    await proxy_websocket(websocket, f"ws://localhost:{INTERNAL['module3_anomaly']}/ws/anomaly")


# Module 4
@app.api_route("/module4", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_module4_root(request: Request):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module4']}/")

@app.api_route("/module4/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_module4(request: Request, path: str):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module4']}/{path}")


# Module 5
@app.api_route("/module5", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_module5_root(request: Request):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module5']}/")

@app.api_route("/module5/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_module5(request: Request, path: str):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module5']}/{path}")


# Unified top-level /api/* routing (supports curl and direct API clients)
@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_unified_api(request: Request, path: str):
    if path.startswith("anomaly/"):
        target = f"http://localhost:{INTERNAL['module3_anomaly']}/api/{path}"
    elif path.startswith("telemetry/"):
        target = f"http://localhost:{INTERNAL['module3_sim']}/api/{path}"
    elif path.startswith("graph/") or path.startswith("rag/") or path.startswith("briefing/") or path in ("status", "backtest"):
        target = f"http://localhost:{INTERNAL['module4']}/api/{path}"
    else:
        # Default to module2 (wells, analogs, well, ahp_weights, formation, etc.)
        target = f"http://localhost:{INTERNAL['module2']}/api/{path}"
    return await proxy_http(request, target)


# Gateway health
@app.get("/gateway/health")
async def gateway_health():
    import socket
    status = {}
    for name, port in INTERNAL.items():
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                status[name] = {"port": port, "status": "up"}
        except OSError:
            status[name] = {"port": port, "status": "down"}
    all_up = all(s["status"] == "up" for s in status.values())
    return {"gateway": "up", "all_modules_up": all_up, "modules": status}


# -- Entry point -------------------------------------------------------------

def main():
    global _sim_speed

    parser = argparse.ArgumentParser(description="NWIS-Sentinel Single-Port Gateway")
    # Render.com (and other PaaS) inject $PORT — fall back to 5000 for local dev
    import os
    default_port = int(os.environ.get("PORT", 5000))
    parser.add_argument("--port",       type=int,   default=default_port)
    parser.add_argument("--speed",      type=float, default=5.0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    _sim_speed = args.speed

    print("\n" + "=" * 70)
    print("     NWIS-Sentinel | SIH 2026 | PS SIH26121 | Single-Port Gateway")
    print("=" * 70)
    print(f"\n  Portal  ->  http://localhost:{args.port}")
    print(f"  Speed   ->  {args.speed}x simulation")
    print(f"  Logs    ->  {LOGS_DIR}\n")

    if not args.no_browser:
        import threading
        def _open():
            time.sleep(5)
            webbrowser.open(f"http://localhost:{args.port}")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
