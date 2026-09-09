# eRTMAC-NWIS — Nearby Wells Intelligence System
### An AI-Powered Offset Well Knowledge, Real-Time Telemetry & Decision Support Platform
**Smart India Hackathon (SIH) 2026 | Problem Statement: SIH26121 | Organization: Oil India Limited**

---

## ⚡ Quick Start (One Command, All 5 Modules)

> **Working directory for ALL commands: `NLP/nlp_task_ddr/`**
>
> Clone the repo, install dependencies once, then launch everything together.

```bash
# Step 1 — go to the working directory
cd NLP/nlp_task_ddr

# Step 2 — install all dependencies (do this once)
pip install -r requirements.txt

# Step 3 — launch all 5 modules simultaneously
python run_all_modules.py
```

That's it. Four interactive browser tabs will open automatically.

| Module | URL | What You See |
|---|---|---|
| **Module 2** — Geospatial Map | [http://localhost:5001](http://localhost:5001) | Leaflet interactive map, 159 wells, AHP hazard rankings |
| **Module 3** — Live Risk Monitor | [http://localhost:5003/monitor](http://localhost:5003/monitor) | Real-time CUSUM/Z-score alerts, +106.5 m early warning dashboard |
| **Module 4** — Knowledge Graph & AI Studio | [http://localhost:5004](http://localhost:5004) | 4,037-node Vis.js graph, GraphRAG search, Gemini AI briefings |
| **Module 5** — Engineering Decision Support | [http://localhost:5005](http://localhost:5005) | Dark console, 1-click scenarios, Gemini RAG, ChromaDB vector store |

> Press **Ctrl+C** in the terminal to stop all services cleanly.

---

## 🖥️ Windows — 1-Click Launcher

If you don't want to type anything, just double-click:

```
start_all.bat          ← in the root SIH_2026_PLANNS/ folder
```

or from PowerShell:
```powershell
.\start_all.ps1
```

---

## 🛠️ Manual Launch (Separate Terminals)

If you want full control — open separate terminals, all inside `NLP/nlp_task_ddr/`.

**Terminal 1 — Module 2 (Geospatial & AHP Similarity Map)**
```bash
python module2/app.py
# → http://localhost:5001
```

**Terminal 2 — Module 3 Simulator (Live Telemetry Stream)**
```bash
python module3/simulator_server.py --port 5002 --speed 5.0
# WebSocket: ws://localhost:5002/ws/telemetry
# --speed controls replay speed (5.0 = 5× real time; 1.0 = real time)
```

**Terminal 3 — Module 3 Anomaly Server (Risk Detection & Monitor)**
> ⚠️ Start Terminal 2 FIRST — this server connects to Terminal 2's WebSocket.
```bash
python module3/anomaly_server.py --port 5003 --simulator-url ws://localhost:5002/ws/telemetry
# → http://localhost:5003/monitor
```

**Terminal 4 — Module 4 (Knowledge Graph, GraphRAG & AI Briefing)**
```bash
python module4/app.py
# → http://localhost:5004
```

**Terminal 5 — Module 5 (Engineering RAG + LLM Agent)**
```bash
python module5_engineering_agent/app.py
# → http://localhost:5005
```

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

## 🔌 API Health Check (Quick Sanity Test While Servers Are Running)

```bash
# Module 2 — analog wells for a given well + hazard
curl "http://localhost:5001/api/analogs?well_id=15/9-F-9A&hazard=stuck_pipe&top=3"

# Module 3 — anomaly server status (buffer size, detector config)
curl "http://localhost:5003/api/anomaly/status"

# Module 4 — graph stats (node + edge counts)
curl "http://localhost:5004/api/graph/stats"

# Module 4 — status summary
curl "http://localhost:5004/api/status"

# Module 5 — engineering agent UI (returns HTTP 200) & health check
curl -I "http://localhost:5005"
curl "http://localhost:5005/api/health"
```

---

## 📦 Dependencies

All dependencies are in `NLP/nlp_task_ddr/requirements.txt`. **Python 3.10+ required.**

Key libraries used:

| Library | Used In |
|---|---|
| `Flask`, `flask-cors` | Module 2, 4 & 5 web servers |
| `fastapi`, `uvicorn`, `websockets` | Module 3 real-time servers |
| `networkx` | Module 4 knowledge graph |
| `sentence-transformers` | Module 4 GraphRAG semantic search |
| `chromadb` | Module 5 vector store (2,022 offset records) |
| `google-generativeai`, `google-genai` | Module 4 & 5 Gemini AI briefings & agent |
| `scikit-learn`, `scipy`, `numpy`, `pandas` | Anomaly detection & AHP calculations |
| `statsmodels` | Wilson Score confidence intervals (Module 3) |
| `fastdtw` | Fast Dynamic Time Warping (Module 3) |
| `matplotlib` | Backtest plots (Module 3) |

---

## 🌐 Port Reference

| Port | Service | Protocol |
|---|---|---|
| **5001** | Module 2 Flask Map Server | HTTP |
| **5002** | Module 3 Telemetry Simulator | HTTP + WebSocket (`ws://localhost:5002/ws/telemetry`) |
| **5003** | Module 3 Anomaly & Risk Server | HTTP + WebSocket (`ws://localhost:5003/ws/anomaly`) + Monitor UI |
| **5004** | Module 4 Knowledge Graph & Briefing Studio | HTTP |
| **5005** | Module 5 Engineering Decision Support Console | HTTP |

---

## 🔑 Optional: Gemini API Key (for Modules 4 & 5)

Modules 4 and 5 generate AI briefings and decision support using Google Gemini. Both modules also feature an automated **Local Evidence Synthesis Engine** as an offline fallback if no API key is provided. To use live Gemini generation:

**Option A — Enter in the browser UI:**  
Open [http://localhost:5004](http://localhost:5004) → paste your key in the *API Key* field → click Generate Briefing.

**Option B — Set as environment variable (auto-loads):**
```bash
# Windows (PowerShell)
$env:GOOGLE_API_KEY = "AIza..."

# Windows (CMD)
set GOOGLE_API_KEY=AIza...

# Then launch as normal
python run_all_modules.py
```

> ✅ All Knowledge Graph, GraphRAG, and map features work completely **without** an API key.
> Only the AI briefing generation step needs one.

---

## 🏗️ Architecture Overview

```
╔══════════════════════════════════════════════════════════════════════════╗
║                     DATA FOUNDATION (Module 1)                          ║
║  159 wells · 1,959 DDR events (18 token classes) · 16,670 telemetry rows║
╚═════════════════════════════╦════════════════════════════════════════════╝
                              │
            ┌─────────────────┴──────────────────┐
            ▼                                    ▼
╔═══════════════════════════╗     ╔══════════════════════════════════════╗
║  MODULE 2 (Port 5001)     ║     ║  MODULE 3 (Ports 5002 & 5003)        ║
║  Geospatial & AHP         ║     ║  Real-Time Telemetry & Anomaly       ║
║  • 5-hazard AHP ranking   ║     ║  • WITSML replay simulator           ║
║  • 59 formation tops      ║     ║  • CUSUM + Z-score detection         ║
║  • Leaflet map UI         ║     ║  • Smith-Waterman + Wilson CI        ║
╚═════════════╦═════════════╝     ║  • +106.48 m early warning           ║
              │                   ╚═════════════════╦════════════════════╝
              └─────────────────────────────────────┘
                                  │
                                  ▼
╔══════════════════════════════════════════════════════════════════════════╗
║                      MODULE 4 (Port 5004)                               ║
║  Knowledge Graph + GraphRAG + Gemini AI Briefing Studio                 ║
║  • 4,037 nodes · 12,392 edges — Vis.js interactive canvas               ║
║  • Two-stage GraphRAG: AHP pre-filter → semantic retrieval              ║
║  • Forced-citation AI briefings (immutable risk scores from Module 3)   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 📁 Repository Structure

```
SIH_2026_PLANNS/
├── start_all.bat                      ← Windows double-click launcher
├── start_all.ps1                      ← PowerShell launcher
├── README.md                          ← This file
│
└── NLP/nlp_task_ddr/                  ← ALL project code lives here
    ├── requirements.txt               ← pip install -r requirements.txt
    ├── run_all_modules.py             ← Master launcher (start all 4)
    ├── start_all.bat / start_all.ps1  ← Local launcher scripts
    ├── check_setup.py                 ← Module 1 data integrity check
    ├── final_verify_m2.py             ← Module 2 AHP & outputs check
    │
    ├── results/
    │   └── module1_outputs/
    │       ├── wells_metadata.json    ← 159 wells
    │       ├── events.jsonl           ← 1,959 drilling events
    │       ├── flagged_real_incidents.json
    │       └── telemetry/15_9-F-9A.csv  ← 16,670 rows real Volve MWD
    │
    ├── module2/                       ← Port 5001
    │   ├── app.py
    │   ├── compute_similarity.py
    │   ├── templates/map.html
    │   └── outputs/
    │       ├── analog_wells.json      ← 159 wells × 5 hazards
    │       ├── ahp_weights.json
    │       └── formation_correlation.json
    │
    ├── module3/                       ← Ports 5002 & 5003
    │   ├── simulator_server.py        ← Port 5002
    │   ├── anomaly_server.py          ← Port 5003
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
    └── module4/                       ← Port 5004
        ├── app.py
        ├── knowledge_graph.py
        ├── graph_rag.py
        ├── llm_briefing.py
        ├── test_module4.py            ← 14 automated tests
        ├── templates/
        │   ├── module4.html
        │   └── vis-network.min.js     ← Bundled offline (no CDN needed)
        └── outputs/
            ├── knowledge_graph.gpickle  ← Pre-built, loads in ~1 sec
            ├── graph_stats.json
            └── BRF_*.json               ← Generated briefings (runtime output)
```

---

## ❓ Troubleshooting

**Port already in use?**
```bash
# Windows — find what is using a port, e.g. 5004
netstat -ano | findstr :5004
# Kill by PID
taskkill /PID <pid> /F
```

**`ModuleNotFoundError` on startup?**
```bash
pip install -r requirements.txt
```

**Module 4 loads but graph is empty / 0 nodes?**
Make sure `module4/outputs/knowledge_graph.gpickle` exists and is not 0 bytes. It is ~1.6 MB and pre-built — no need to regenerate it.

**Module 3 anomaly server shows "not connected"?**
Start Module 3 Simulator (port 5002) **before** starting the anomaly server (port 5003). The anomaly server connects to the simulator's WebSocket on startup.

**Gemini AI briefing button does nothing / errors?**
Enter your Google AI Studio API key (`AIza...`) in the key field on the Module 4 UI page. All other features (graph, search, RAG) work without a key.

---

## 🤖 For Antigravity / AI Coding Agents

1. Working directory is always `NLP/nlp_task_ddr/`.
2. Start all services: `python run_all_modules.py --no-browser` (daemon mode).
3. Each module logs to `NLP/nlp_task_ddr/logs/<module_id>.log`.
4. Health checks:
   - `GET http://localhost:5001/api/analogs?well_id=15/9-F-9A&hazard=stuck_pipe&top=1`
   - `GET http://localhost:5003/api/anomaly/status`
   - `GET http://localhost:5004/api/graph/stats`
5. Run tests: `python -m pytest module3/ module4/ -v` — expect **64 passed**.