"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Gateway: Single-Port Orchestrator

Runs all modules on internal ports and exposes a single port 5000.

URL Map
-------
  GET  /                       - Dashboard UI
  GET  /module1                - Module 1 UI (served directly)
  POST /module1/upload         - Module 1 DDR ingestion server (internal :15006)
  GET  /module1/jobs/{id}      - Module 1 OCR/NLP job progress + results
  GET  /module1/health         - Module 1 OCR/NLP engine status
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
import textwrap
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
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# -- Paths -------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent              # NLP/nlp_task_ddr
PYTHON_EXE = sys.executable
LOGS_DIR   = BASE_DIR / "logs"

# -- Internal port assignments (hidden from outside world) -------------------
INTERNAL = {
    "module2":         15001,
    "module3_sim":     15002,
    "module3_anomaly": 15003,
    "module4":         15004,
    "module5":         15005,
    "module1":         15006,
}

# ---------------------------------------------------------------------------
# Silence noisy third-party loggers — only let gateway's own messages through
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.WARNING)
for _noisy in ("uvicorn", "uvicorn.error", "uvicorn.access",
               "httpx", "httpcore", "websockets", "fastapi"):
    logging.getLogger(_noisy).setLevel(logging.CRITICAL)
_gw_logger = logging.getLogger("gateway")
_gw_logger.setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
_C = {
    "reset":   "\033[0m",
    "bold":    "\033[1m",
    "dim":     "\033[2m",
    "cyan":    "\033[96m",
    "blue":    "\033[94m",
    "green":   "\033[92m",
    "yellow":  "\033[93m",
    "red":     "\033[91m",
    "white":   "\033[97m",
    "grey":    "\033[90m",
    "magenta": "\033[95m",
}

def _c(color: str, text: str) -> str:
    return f"{_C.get(color, '')}{text}{_C['reset']}"

W = 90  # inner box width


def _banner(port: int, speed: float) -> None:
    print()
    print(_c("blue",   "╔" + "═" * W + "╗"))
    title = "⬡  NWIS-SENTINEL  ·  SIH 2026  ·  PS SIH26121  ·  GATEWAY  ⬡"
    print(_c("blue",   "║") +
          _c("cyan", _c("bold", title.center(W))) +
          _c("blue",   "║"))
    print(_c("blue",   "╠" + "═" * W + "╣"))

    def row(label: str, value: str, val_color: str = "white") -> None:
        label_part = f"  {label:<10}"
        value_width = W - len(label_part)

        # Automatically wrap long values to fit inside the rectangle
        lines = textwrap.wrap(
            value,
            width=value_width,
            break_long_words=True,
            break_on_hyphens=False
        ) or [""]

        for i, line in enumerate(lines):
            prefix = label_part if i == 0 else " " * len(label_part)

            val_part = _c(val_color, line)
            pad = max(0, W - len(prefix) - len(line))

            print(
                _c("blue", "║") +
                prefix +
                val_part +
                " " * pad +
                _c("blue", "║")
            )

    row("SYSTEM",   "National Water Informatics System — Sentinel Subsurface Ops", "white")
    row("MISSION",  "Automated DDR Parsing · Anomaly Detection · Engineering Intel", "white")
    print(_c("blue",   "╠" + "═" * W + "╣"))
    row("PORTAL",   f"http://localhost:{port}", "cyan")
    row("LOGS",     str(LOGS_DIR), "dim")
    print(_c("blue",   "╚" + "═" * W + "╝"))
    print()


# User-facing modules (Module 3 = simulator + anomaly detector, shown as one row).
# (label, gateway path, internal services that must be up)
_DISPLAY = [
    ("MOD-1", "DDR Ingestion / OCR-NLP",   "/module1",         ["module1"]),
    ("MOD-2", "Well Analytics",            "/module2",         ["module2"]),
    ("MOD-3", "Telemetry & Anomaly Monitor", "/module3/monitor", ["module3_sim", "module3_anomaly"]),
    ("MOD-4", "Knowledge Graph / RAG",     "/module4",         ["module4"]),
    ("MOD-5", "Engineering Agent",         "/module5",         ["module5"]),
]


def _port_up(port: int) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _progress_bar(done: int, total: int, width: int = 40) -> str:
    filled = int(width * done / total) if total else width
    bar = _c("green", "█" * filled) + _c("grey", "░" * (width - filled))
    return f"  {bar} {_c('white', f'{done}/{total}')} services up"


def _modules_table(port: int, failed: set) -> None:
    print()
    print(_c("grey", "  ┌─ MODULES ─────────────────────────────────────────────────────"))
    for tag, label, path, services in _DISPLAY:
        ok = not any(s in failed for s in services)
        icon = _c("green", "●") if ok else _c("red", "○")
        url = _c("cyan", f"http://localhost:{port}{path}") if ok else _c("red", "unavailable - see logs")
        print(_c("grey", "  │ ") + icon + " " + _c("cyan", f"[{tag}]") + " " +
              _c("white", f"{label:<28}") + " " + url)
    print(_c("grey", "  └─────────────────────────────────────────────────────────────"))
    print()
    if failed:
        print(_c("yellow", f"  ⚠  Some services failed to start. Logs: {LOGS_DIR}"))
    else:
        print(_c("green", _c("bold", "  ✔  ALL SYSTEMS NOMINAL")) +
              _c("grey", f"  ·  Dashboard: http://localhost:{port}"))
    print(_c("grey", "     Press Ctrl+C to stop.\n"))


def _shutdown_msg() -> None:
    print()
    print(_c("yellow", "  ⬡  Gateway shutting down — terminating subsystems …"))


# -- Process registry --------------------------------------------------------
_processes = []

# -- Simulation speed (set via CLI) ------------------------------------------
_sim_speed = 5.0
_boot_state = {"stop": False, "port": 5000, "total": 0}


# -- Subprocess management ---------------------------------------------------

def _start_module(name, cmd, log_file):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / log_file
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
        {
            # Live DDR ingestion: real OCR + hybrid NLP. The HTTP port comes up
            # immediately; OCR/NLP model warm-up continues in its worker processes.
            "name": "module1",
            "cmd":  [PYTHON_EXE, str(BASE_DIR / "module1" / "server.py"),
                     "--port", str(INTERNAL["module1"])],
            "log":  "module1.log",
            "port": INTERNAL["module1"],
        },
    ]

    _boot_state["total"] = len(modules)
    for m in modules:
        _processes.append(_start_module(m["name"], m["cmd"], m["log"]))

    # Poll ports, redraw one progress bar, then print the module list once.
    deadlines = {m["name"]: time.time() + (180 if m["name"] == "module3_anomaly" else 90)
                 for m in modules}
    pending = {m["name"]: (m["port"], p) for m, p in zip(modules, _processes)}
    up, failed = set(), set()
    while pending and not _boot_state["stop"]:
        for name, (port, proc) in list(pending.items()):
            if _port_up(port):
                up.add(name); del pending[name]
            elif proc.poll() is not None or time.time() > deadlines[name]:
                failed.add(name); del pending[name]
        sys.stdout.write("\r" + _progress_bar(len(up) + len(failed), len(modules)))
        sys.stdout.flush()
        time.sleep(0.3)
    sys.stdout.write("\n")
    if not _boot_state["stop"]:
        _modules_table(_boot_state["port"], failed)


def stop_all_modules():
    _shutdown_msg()
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
    print(_c("green", "  ✔  All subsystems offline. Goodbye.\n"))


# -- HTTP Client State -------------------------------------------------------

_http_client: httpx.AsyncClient | None = None


# -- FastAPI Lifespan --------------------------------------------------------

@asynccontextmanager
async def lifespan(app):
    global _http_client
    _http_client = httpx.AsyncClient(timeout=600.0, follow_redirects=True)
    threading.Thread(target=start_all_modules, daemon=True).start()
    yield
    _boot_state["stop"] = True
    stop_all_modules()
    if _http_client is not None:
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


# -- Generic HTTP reverse proxy ----------------------------------------------

HOP_BY_HOP = {"host", "content-length", "transfer-encoding", "connection",
               "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailers", "upgrade"}


async def proxy_http(request, target_url):
    global _http_client
    client = _http_client
    if client is None:
        client = _http_client = httpx.AsyncClient(timeout=600.0, follow_redirects=True)
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in HOP_BY_HOP}
    body = await request.body()
    try:
        resp = await client.request(
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
        _gw_logger.warning("WebSocket proxy error: %s", e)
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


# Module 1 — UI served directly; upload/jobs/health proxied to the ingestion
# server (:15006), which runs real OCR (PaddleOCR) + hybrid NLP.
@app.get("/module1")
async def module1_ui():
    from fastapi.responses import FileResponse
    return FileResponse(BASE_DIR / "module1" / "module1.html")

@app.post("/module1/upload")
async def module1_upload(request: Request):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module1']}/upload")

@app.get("/module1/jobs/{job_id}")
async def module1_job(request: Request, job_id: str):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module1']}/jobs/{job_id}")

@app.get("/module1/health")
async def module1_health(request: Request):
    return await proxy_http(request, f"http://localhost:{INTERNAL['module1']}/health")


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

    for _s in (sys.stdout, sys.stderr):      # box/bar glyphs on legacy Windows codepages
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="NWIS-Sentinel Single-Port Gateway")
    # Render.com (and other PaaS) inject $PORT — fall back to 5000 for local dev
    import os
    default_port = int(os.environ.get("PORT", 5000))
    parser.add_argument("--port",       type=int,   default=default_port)
    parser.add_argument("--speed",      type=float, default=5.0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    _sim_speed = args.speed
    _boot_state["port"] = args.port

    # Refuse to start if a previous gateway/module is still holding a port.
    busy = [(n, p) for n, p in [("gateway", args.port), *INTERNAL.items()] if _port_up(p)]
    if busy:
        print()
        print(_c("red", "  ✖  Ports already in use (a previous run is probably still alive):"))
        for n, p in busy:
            print(_c("red", f"       {n:<16} :{p}"))
        print(_c("yellow", "     Stop the old process (Ctrl+C in its terminal, or "
                           "`Get-NetTCPConnection -LocalPort 5000 | % { Stop-Process -Id $_.OwningProcess }`)"
                           " and retry."))
        print()
        sys.exit(1)

    _banner(args.port, args.speed)

    if not args.no_browser:
        def _open():
            time.sleep(5)
            webbrowser.open(f"http://localhost:{args.port}")
        threading.Thread(target=_open, daemon=True).start()

    # Run uvicorn with access logs suppressed — the dashboard already shows
    # what matters. Only genuine errors will surface.
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=args.port,
        log_level="error",             # hide access spam but surface bind errors
        access_log=False,
    )


if __name__ == "__main__":
    main()
