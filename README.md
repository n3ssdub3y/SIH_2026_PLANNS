# eRTMAC-NWIS — Nearby Wells Intelligence System
### An AI-Powered Offset Well Knowledge, Real-Time Telemetry & Decision Support Platform
**Smart India Hackathon (SIH) 2026 | Problem Statement: SIH26121 | Organization: Oil India Limited**

---

>  **Judges & Evaluators:** For a complete breakdown of the project — problem statement, all five modules, technical novelties, dataset details, and the validated backtest result — see **[NWIS_PROJECT_SHOWCASE.md](./NWIS_PROJECT_SHOWCASE.md)**.

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
| **Central Operations Dashboard** | [http://localhost:5000](http://localhost:5000) | Unified portal — system overview, live module health & navigation |
| **Module 2** — Geospatial Map | [http://localhost:5000/module2/](http://localhost:5000/module2/) | Leaflet interactive map, 159 wells, AHP hazard rankings |
| **Module 3** — Live Risk Monitor | [http://localhost:5000/module3/monitor](http://localhost:5000/module3/monitor) | Real-time CUSUM/Z-score alerts, +106.5 m early warning dashboard |
| **Module 4** — Knowledge Graph & AI Studio | [http://localhost:5000/module4/](http://localhost:5000/module4/) | 4,037-node Vis.js graph, GraphRAG search, Gemini AI briefings |
| **Module 5** — Engineering Decision Support | [http://localhost:5000/module5/](http://localhost:5000/module5/) | Dark console, 1-click scenarios, Qwen 2.5-72B / Gemini RAG, ChromaDB vector store |
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
| `huggingface-hub` | Module 5 — Qwen 2.5-72B via Hugging Face Inference API (primary LLM) |
| `google-generativeai`, `google-genai` | Module 4 Gemini AI briefings; Module 5 Gemini fallback |
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

## 🔑 API Keys (for LLM features)

### Module 5 — Hugging Face Token (Qwen 2.5-72B, Primary LLM)

Module 5 uses `Qwen/Qwen2.5-72B-Instruct` via the Hugging Face Inference API as its primary LLM. Get a **free token** at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

```bash
# Copy the example file and fill in your token
cp NLP/nlp_task_ddr/module5_engineering_agent/.env.example \
   NLP/nlp_task_ddr/module5_engineering_agent/.env
# Then edit .env and replace hf_XXX... with your real token
```

Or set as an environment variable before launching:
```bash
# Windows (PowerShell)
$env:HF_TOKEN = "hf_your_token_here"

# Windows (CMD)
set HF_TOKEN=hf_your_token_here

# Then launch
python gateway.py
```

### Module 4 & 5 — Google Gemini API Key (Optional Fallback)

Module 4 uses Gemini for AI briefings. Module 5 uses it as a fallback when `HF_TOKEN` is not set. Get a **free key** at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY = "AIza..."

# Windows (CMD)
set GEMINI_API_KEY=AIza...

# Then launch gateway
python gateway.py
```

Or add it to the same `.env` file in `module5_engineering_agent/`:
```
GEMINI_API_KEY=AIza...
```

> ✅ All Knowledge Graph, GraphRAG, map, and telemetry features work completely **without** any API key.
> Only the AI briefing / agent response generation needs one. Module 5 also has a **Local Evidence Synthesis** fallback that always works offline.

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
║        Engineering RAG + Decision Support (Qwen 2.5-72B / Gemini)       ║
║  • ChromaDB vector store (2,022 indexed offset event records)            ║
║  • Qwen 2.5-72B primary LLM · Gemini fallback · Local synthesis         ║
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
├── ARCHITECTURE.md                    ← Detailed system architecture
├── PROJECT.md                         ← Research foundations & background
├── nwis_data_sources.md               ← Data sources reference
│
└── NLP/nlp_task_ddr/                  ← ALL project code lives here
    ├── gateway.py                     ← Unified Gateway (port 5000 reverse-proxy orchestrator)
    ├── requirements.txt               ← pip install -r requirements.txt
    ├── start_all.bat / start_all.ps1  ← Subdirectory 1-click launchers
    ├── check_setup.py                 ← Module 1 data integrity check
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
    │   ├── backtest_runner.py
    │   ├── monitor.html               ← Live dashboard UI
    │   ├── test_anomaly.py / test_leakage.py / test_sequence_matcher.py / test_simulator.py
    │   └── outputs/
    │       ├── backtest_result.json   ← +106.48 m early warning result
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
        ├── config.py                  ← HF/Qwen + Gemini + ChromaDB config
        ├── .env.example               ← Token setup template (copy to .env)
        ├── README.md                  ← Module 5 documentation
        ├── templates/module5.html     ← Bespoke engineering console
        ├── agent/                     ← EngineeringAgent (Qwen primary, Gemini fallback, Local synthesis)
        ├── retrieval/                 ← Analog lookup + ChromaDB vector search
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
Set `GEMINI_API_KEY` as an environment variable (see *API Keys* section above). All core features (graph, search, RAG, scenarios) work offline without a key.

**Module 5 agent gives generic responses without real LLM analysis?**
Set `HF_TOKEN` (Hugging Face token) in `module5_engineering_agent/.env` or as an environment variable. Without it, the app falls back to local evidence synthesis which is functional but less conversational.