# NWIS-Sentinel — Intelligent Drilling Hazard Prediction System
### SIH 2026 | Problem Statement SIH26121 | Oil India Limited

NWIS-Sentinel is a full-stack, AI-powered drilling intelligence platform that integrates real-time telemetry, geospatial analytics, knowledge graphs, and LLM-based decision support into a single unified portal.

---

## ⚡ Quick Start — One Command, One Port

### Step 1 — Install dependencies
```bash
pip install -r ../../requirements.txt
```

### Step 2 — Launch the gateway
```bash
python gateway.py
```
**Or double-click `start_all.bat` on Windows.**

### Step 3 — Open the portal
```
http://localhost:5000
```

That's it. All modules start automatically and are accessible through **a single port**.

---

## 🌐 URL Structure (Single Port: 5000)

| URL | Module |
|:----|:-------|
| `http://localhost:5000/` | Central Operations Dashboard |
| `http://localhost:5000/module2/` | Module 2 — Geospatial & Offset Similarity Map |
| `http://localhost:5000/module3/monitor` | Module 3 — Live Telemetry & Anomaly Monitor |
| `http://localhost:5000/module4/` | Module 4 — Knowledge Graph, GraphRAG & AI Briefing |
| `http://localhost:5000/module5/` | Module 5 — Engineering RAG & Decision Support Agent |
| `ws://localhost:5000/ws/telemetry` | WebSocket — Live Telemetry Stream |
| `ws://localhost:5000/ws/anomaly` | WebSocket — Live Anomaly & Alert Stream |
| `http://localhost:5000/gateway/health` | Gateway Health Check (all modules status) |

---

## ⚙️ Gateway Options

```bash
python gateway.py                        # Default: port 5000, speed 5x
python gateway.py --speed 2.0            # Slower telemetry replay (1x = real time)
python gateway.py --no-browser           # Skip auto browser open
python gateway.py --port 8080            # Run on a different port
```

---



## 📋 Module Deliverables & Outputs

### Gateway (Port 5000)
- `gateway.py`: FastAPI reverse-proxy gateway. Starts all modules on internal ports (15001–15005) and exposes a unified API on port 5000. Handles HTTP and WebSocket proxying.

### Central Operations Dashboard
- `dashboard/app.py`: Flask portal server (served directly by gateway at `/`).
- `dashboard/templates/dashboard.html`: BSPWM-themed command center with real-time module health polling.

### Module 1 — Data Foundation, OCR & NLP Extraction
- `results/module1_outputs/wells_metadata.json`: 159 wells with trajectory, coordinates, and formation tops.
- `results/module1_outputs/events.jsonl`: 1,959 daily drilling events mapped into 18 canonical token classes.
- `results/module1_outputs/flagged_real_incidents.json`: 63 ground-truth incidents with NPT, mud weight, and mitigations.
- `results/module1_outputs/telemetry/15_9-F-9A.csv`: 16,670 rows of real Volve drilling telemetry.

### Module 2 — Geospatial & AHP Similarity Engine (`/module2/`)
- `module2/app.py`: Flask server with well map and similarity API.
- `module2/outputs/analog_wells.json`: Pre-computed ranked analog offset wells for all 159 wells across 5 hazards.
- `module2/outputs/ahp_weights.json`: AHP pairwise comparison matrices and eigenvector priority weights (CR < 0.05).
- `module2/outputs/formation_correlation.json`: 59 formations depth correlation across 159 wells.

### Module 3 — Real-Time Telemetry, Anomaly Detection & Backtesting (`/module3/monitor`)
- `module3/simulator_server.py`: FastAPI WebSocket server replaying 16,670 rows of Volve telemetry.
- `module3/anomaly_server.py`: FastAPI server running Z-score + CUSUM anomaly detection and Smith-Waterman sequence matching.
- `module3/outputs/backtest_result.json`: Time-travel backtest proving **+106.48 m / +44.07 min early warning lead time** on real Volve stuck pipe incident.
- `module3/outputs/backtest_plot.png`: 300 DPI high-resolution telemetry time-series visualization.
- `module3/monitor.html`: Live interactive telemetry and risk prediction monitoring console.

### Module 4 — Knowledge Graph, GraphRAG & AI Briefing Studio (`/module4/`)
- `module4/app.py`: Flask server with graph, RAG, and briefing APIs.
- `module4/outputs/knowledge_graph.gpickle`: 4,037 nodes and 12,392 edges multi-relational directed graph.
- `module4/templates/module4.html`: Full-screen dark Vis.js canvas with hazard filters and GraphRAG search.
- `module4/llm_briefing.py`: Google Gemini AI briefing generator with strict anti-hallucination and `[NODE_ID]` citation verification.

### Module 5 — Engineering RAG & Decision Support Agent (`/module5/`)
- `module5_engineering_agent/app.py`: Flask server with REST API (`/api/ask`, `/api/scenarios`, `/api/health`).
- `module5_engineering_agent/templates/module5.html`: Dark glassmorphic engineering console with slide-out scenario selector.
- `module5_engineering_agent/vector_store/chroma_db/`: Persistent ChromaDB collection with 2,022 indexed offset event records.
- `module5_engineering_agent/agent/agent.py`: Engineering decision support agent with automated local synthesis fallback.