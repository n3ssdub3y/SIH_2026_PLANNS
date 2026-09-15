# eRTMAC-NWIS — Nearby Wells Intelligence System
### An AI-Powered Offset Well Knowledge, Real-Time Telemetry & Decision Support Platform
**Smart India Hackathon (SIH) 2026 | Problem Statement: SIH26121 | Organization: Oil India Limited**

---

## ⚡ Quick Start (Single-Port Unified Gateway)

> **Working directory for ALL commands: `NLP/nlp_task_ddr/`**
>
> All 5 modules, real-time WebSocket feeds, and the central command center are served through **a single entry point: port 5000**.

```bash
# Step 1 — go to the working directory
cd NLP/nlp_task_ddr

# Step 2 — install all dependencies (do this once)
pip install -r requirements.txt

# Step 3 — launch unified gateway (starts all modules + opens dashboard)
python gateway.py
```

That's it. The gateway starts all internal microservices and automatically opens the central dashboard at **`http://localhost:5000`**.

| Service / View | Unified Gateway URL | Description |
|---|---|---|
| **Central Operations Dashboard** | [http://localhost:5000](http://localhost:5000) | BSPWM/terminal unified portal, system specs, live module health & navigation |
| **Module 2** — Geospatial Map | [http://localhost:5000/module2/](http://localhost:5000/module2/) | Leaflet interactive map, 159 wells, AHP hazard rankings |
| **Module 3** — Live Risk Monitor | [http://localhost:5000/module3/monitor](http://localhost:5000/module3/monitor) | Real-time CUSUM/Z-score alerts, +106.5 m early warning dashboard |
| **Module 4** — Knowledge Graph & AI Studio | [http://localhost:5000/module4/](http://localhost:5000/module4/) | 4,037-node Vis.js graph, GraphRAG search, Gemini AI briefings |
| **Module 5** — Engineering Decision Support | [http://localhost:5000/module5/](http://localhost:5000/module5/) | Dark console, 1-click scenarios, Gemini RAG, ChromaDB vector store |
| **Live Telemetry WebSocket** | `ws://localhost:5000/ws/telemetry` | WITSML-style real-time drilling data stream |
| **Live Risk WebSocket** | `ws://localhost:5000/ws/anomaly` | Real-time CUSUM anomaly & early warning alert stream |

> Press **Ctrl+C** in the terminal to stop all services cleanly.

---

## 🖥️ Windows — 1-Click Launcher

If you don't want to type commands, just double-click `start_all.bat` from the repo root, or from PowerShell:

```powershell
.\start_all.ps1
```

Both launch `gateway.py` automatically and open your browser to `http://localhost:5000`.

---

## 🧪 Verify Everything is Working (Run Before Presenting)

```bash
cd NLP/nlp_task_ddr

# Module 1 — data contract check (wells, events, telemetry)
python check_setup.py

# Module 2 — AHP weights & analog rankings check
python final_verify_m2.py

# Module 3 — unit tests: leakage, anomaly detector, sequence matcher (50 tests)
python -m pytest module3/test_leakage.py module3/test_sequence_matcher.py module3/test_anomaly.py module3/test_simulator.py -v

# Module 4 — unit tests: knowledge graph, GraphRAG, REST API (14 tests)
python -m pytest module4/test_module4.py -v
```

Expected result: **64 passed**.

---

## 🔌 API Health Check (Quick Sanity Test on Port 5000)

```bash
# Dashboard — central portal UI
curl -I "http://localhost:5000/"

# Module 2 — analog wells for a given well + hazard
curl "http://localhost:5000/api/analogs?well_id=15/9-F-9A&hazard=stuck_pipe&top=3"

# Module 3 — anomaly server status (buffer size, detector config)
curl "http://localhost:5000/api/anomaly/status"

# Module 4 — graph stats (node + edge counts)
curl "http://localhost:5000/api/graph/stats"

# Module 4 — status summary
curl "http://localhost:5000/api/status"

# Module 5 — engineering agent UI (returns HTTP 200) & health check
curl -I "http://localhost:5000/module5/"
curl "http://localhost:5000/module5/api/health"
```

---

## 📦 Dependencies

All dependencies are in `NLP/nlp_task_ddr/requirements.txt`. **Python 3.10+ required.**

Key libraries used:

| Library | Used In |
|---|---|
| `fastapi`, `uvicorn`, `httpx`, `websockets` | Port 5000 Gateway, WebSocket proxying & Module 3 real-time servers |
| `Flask`, `flask-cors` | Module 2, 4 & 5 web engines and Dashboard |
| `networkx` | Module 4 knowledge graph |
| `sentence-transformers` | Module 4 GraphRAG semantic search |
| `chromadb` | Module 5 vector store (2,022 indexed offset records) |
| `google-generativeai`, `google-genai` | Module 4 & 5 Gemini AI briefings & agent |
| `scikit-learn`, `scipy`, `numpy`, `pandas` | Anomaly detection & AHP calculations |
| `statsmodels` | Wilson Score confidence intervals (Module 3) |
| `fastdtw` | Fast Dynamic Time Warping (Module 3) |
| `matplotlib` | Backtest plots (Module 3) |

---

## 🌐 Unified Port Architecture

| Port | Exposure | Role | Protocol |
|---|---|---|---|
| **5000** | **Public Entry Point** | **Unified Gateway & Operations Portal** | **HTTP + WebSockets** |
| `15001` | Internal Loopback | Module 2 — Geospatial & AHP Flask App | HTTP (Proxied) |
| `15002` | Internal Loopback | Module 3 — Telemetry Replay Server | HTTP + WS (Proxied) |
| `15003` | Internal Loopback | Module 3 — Anomaly & Risk Engine | HTTP + WS (Proxied) |
| `15004` | Internal Loopback | Module 4 — Knowledge Graph & Briefing Studio | HTTP (Proxied) |
| `15005` | Internal Loopback | Module 5 — Engineering Decision Support Console | HTTP (Proxied) |

> 💡 **Why Single-Port?** In enterprise drilling operations, IT security firewalls strictly limit open ports. A single gateway on port 5000 cleanly satisfies single-origin CORS policies, avoids browser mixed-port warnings, and guarantees zero port collision issues.

---

## 🔑 Optional: Gemini API Key (for Modules 4 & 5)

Modules 4 and 5 generate AI briefings and decision support using Google Gemini. Both modules also feature an automated **Local Evidence Synthesis Engine** as an offline fallback if no API key is provided. To use live Gemini generation:

**Option A — Enter in the browser UI:**  
Open [http://localhost:5000/module4/](http://localhost:5000/module4/) or [http://localhost:5000/module5/](http://localhost:5000/module5/) → paste your key in the *API Key* field.

**Option B — Set as environment variable (auto-loads):**
```bash
# Windows (PowerShell)
$env:GOOGLE_API_KEY = "AIza..."

# Windows (CMD)
set GOOGLE_API_KEY=AIza...

# Then launch gateway
python gateway.py
```

> ✅ All Knowledge Graph, GraphRAG, and map features work completely **without** an API key.
> Only the AI briefing generation step needs one.

---

## 🏗️ Architecture Overview

```
╔══════════════════════════════════════════════════════════════════════════╗
║             UNIFIED SENTINEL GATEWAY & DASHBOARD (Port 5000)             ║
║    Reverse-Proxy · WebSockets · Single-Port Access · Command Center      ║
╚═════════════════════════════╦════════════════════════════════════════════╝
                              │
╔═════════════════════════════╩════════════════════════════════════════════╗
║                     DATA FOUNDATION (Module 1)                          ║
║  159 wells · 1,959 DDR events (18 token classes) · 16,670 telemetry rows║
╚═════════════════════════════╦════════════════════════════════════════════╝
                              │
            ┌─────────────────┼──────────────────┐
            ▼                 ▼                  ▼
╔═════════════════════╗ ╔═════════════════════╗ ╔══════════════════════════╗
║ MODULE 2 (/module2) ║ ║ MODULE 3 (/module3) ║ ║ MODULE 4 (/module4)     ║
║ Geospatial & AHP    ║ ║ Real-Time Telemetry ║ ║ Knowledge Graph,         ║
║ • 5-hazard AHP      ║ ║ • WITSML simulator  ║ ║   GraphRAG & Gemini      ║
║ • 59 formations     ║ ║ • CUSUM / Z-score   ║ ║ • 4,037 nodes            ║
║ • Leaflet map UI    ║ ║ • +106.5m warning   ║ ║ • AI Briefings           ║
╚═══════════╦═════════╝ ╚══════════╦══════════╝ ╚════════════╦═════════════╝
            │                      │                         │
            └──────────────────────┼─────────────────────────┘
                                   ▼
╔══════════════════════════════════════════════════════════════════════════╗
║                     MODULE 5 (/module5)                                 ║
║           Engineering RAG + LLM Decision Support Agent                   ║
║  • ChromaDB vector store (2,022 indexed offset event records)            ║
║  • Multi-turn rig-floor engineering advisor with citations               ║
║  • 5 one-click realistic drilling crisis scenarios                       ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 📁 Repository Structure

```
SIH_2026_PLANNS/
├── start_all.bat                      ← Windows 1-click launcher (runs gateway.py)
├── start_all.ps1                      ← PowerShell 1-click launcher (runs gateway.py)
├── README.md                          ← This file
├── ARCHITECTURE.md                    ← System architecture specification
│
└── NLP/nlp_task_ddr/                  ← ALL project code lives here
    ├── gateway.py                     ← Unified Gateway (port 5000 reverse-proxy orchestrator)
    ├── requirements.txt               ← pip install -r requirements.txt
    ├── start_all.bat / start_all.ps1  ← Subdirectory 1-click launchers
    ├── check_setup.py                 ← Module 1 data integrity check
    ├── final_verify_m2.py             ← Module 2 AHP & outputs check
    │
    ├── dashboard/                     ← Central Operations Portal (port 5000 root)
    │   ├── app.py
    │   ├── README.md
    │   └── templates/dashboard.html
    │
    ├── results/
    │   └── module1_outputs/
    │       ├── wells_metadata.json    ← 159 wells
    │       ├── events.jsonl           ← 1,959 daily drilling events
    │       ├── flagged_real_incidents.json
    │       └── telemetry/15_9-F-9A.csv  ← 16,670 rows real Volve MWD
    │
    ├── module2/                       ← Geospatial & AHP Similarity Engine
    │   ├── app.py
    │   ├── compute_similarity.py
    │   ├── templates/map.html
    │   └── outputs/
    │       ├── analog_wells.json      ← 159 wells × 5 hazards
    │       ├── ahp_weights.json
    │       └── formation_correlation.json
    │
    ├── module3/                       ← Real-Time Telemetry & Anomaly Detection
    │   ├── simulator_server.py        ← WITSML replay server
    │   ├── anomaly_server.py          ← Real-time risk detection server
    │   ├── anomaly_detector.py
    │   ├── sequence_matcher.py
    │   ├── monitor.html               ← Live dashboard UI
    │   ├── test_*.py                  ← 50 automated tests
    │   └── outputs/
    │       ├── backtest_result.json   ← +106.48 m result
    │       ├── backtest_plot.png
    │       ├── risk_predictions.jsonl ← Live risk scores (grows at runtime)
    │       └── sequence_matches.json
    │
    ├── module4/                       ← Knowledge Graph & AI Studio
    │   ├── app.py
    │   ├── knowledge_graph.py
    │   ├── graph_rag.py
    │   ├── llm_briefing.py
    │   ├── test_module4.py            ← 14 automated tests
    │   ├── templates/
    │   │   ├── module4.html
    │   │   └── vis-network.min.js     ← Bundled offline (no CDN needed)
    │   └── outputs/
    │       ├── knowledge_graph.gpickle  ← Pre-built, loads in ~1 sec
    │       ├── graph_stats.json
    │       └── BRF_*.json               ← Generated briefings (runtime output)
    │
    └── module5_engineering_agent/     ← Engineering Decision Support Console
        ├── app.py                     ← Flask server
        ├── README.md                  ← Module 5 documentation
        ├── templates/module5.html     ← Bespoke engineering console
        ├── agent/                     ← Hybrid LLM / Local synthesis agent
        ├── retrieval/                 ← ChromaDB vector store wrapper
        ├── ingestion/                 ← Data loader for Modules 1 & 2
        ├── schemas/                   ← Pydantic data schemas
        └── vector_store/
            └── chroma_db/             ← 2,022 indexed records
```

---

## ❓ Troubleshooting

**Port 5000 already in use?**
```powershell
# PowerShell — find what is using port 5000
Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | Select-Object OwningProcess
# Stop python processes
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
```

**`ModuleNotFoundError` on startup?**
```bash
pip install -r requirements.txt
```

**Module 4 loads but graph is empty / 0 nodes?**
Make sure `module4/outputs/knowledge_graph.gpickle` exists and is not 0 bytes. It is ~1.6 MB and pre-built — no need to regenerate it.

**Gemini AI briefing button does nothing / errors?**
Enter your Google AI Studio API key (`AIza...`) in the key field on the Module 4 or Module 5 UI page. All core features (graph, search, RAG, scenarios) work offline without a key.