# eRTMAC-NWIS (Nearby Wells Intelligence System)
### An AI-Powered Offset Well Knowledge, Real-Time Telemetry & Decision Support Platform for Drilling Operations
**Smart India Hackathon (SIH) 2026 | Problem Statement: SIH26121 | Organization: Oil India Limited**

---

## 🚀 Quick Start — One-Command Instant Launch

Whether you are a **human developer** or an **AI Coding Agent (Antigravity/Cursor/Claude)**, you can launch the entire 4-module system simultaneously with a single command.

### 1. Install Dependencies
```bash
cd NLP/nlp_task_ddr
pip install -r requirements.txt
```

### 2. Launch All 4 Modules Simultaneously

**Option A (Python Orchestrator - Cross-Platform):**
```bash
python run_all_modules.py
```
*(Optional parameters: `--speed 5.0` to set telemetry replay speed; `--no-browser` to suppress opening browser tabs)*

**Option B (Windows 1-Click Batch Script):**
- Double click `start_all.bat` (in root or inside `NLP/nlp_task_ddr/`)
- Or in PowerShell: `.\start_all.ps1`

### 3. Access Active Portals & Dashboards

| Module | Service | Port / URL | Key Capabilities |
|---|---|---|---|
| **Module 2** | Geospatial & Offset Similarity | [`http://localhost:5001`](http://localhost:5001) | Interactive Leaflet map, 159 wells, AHP hazard similarity, 59 formation correlations |
| **Module 3** | Live Telemetry Replay Server | [`http://localhost:5002`](http://localhost:5002) | Real-time WITSML / MWD telemetry streaming (WebSocket `ws://localhost:5002/ws/telemetry`) |
| **Module 3** | Anomaly & Early Warning Monitor | [`http://localhost:5003/monitor`](http://localhost:5003/monitor) | CUSUM / Z-Score anomaly detection, Smith-Waterman sequence matching, **+106.5 m lead time** |
| **Module 4** | Knowledge Graph & AI Briefing | [`http://localhost:5004`](http://localhost:5004) | 4,037 nodes & 12,392 edges Vis.js graph, Hybrid GraphRAG, Gemini AI Pre-Spud Briefing studio |

*(To stop all services cleanly, simply press `Ctrl+C` in the orchestrator terminal).*

---

## 🤖 Guide for AI Agents (Antigravity / LLM Autonomous Execution)

If you are an **Antigravity AI Agent** assisting a teammate:
1. **Working Directory**: Always execute commands from `NLP/nlp_task_ddr/`.
2. **Environment**: Python 3.10+ with `pandas`, `numpy`, `Flask`, `fastapi`, `uvicorn`, `networkx`, `sentence-transformers`, `scipy`, `scikit-learn`.
3. **Running in Background**:
   To start the full system as a background process:
   ```bash
   python run_all_modules.py --no-browser
   ```
   Or start modules individually in separate background tasks (see manual guide below).
4. **Health Check Verification**:
   - Module 2: `GET http://localhost:5001/api/analogs/15%2F9-F-9A/stuck_pipe`
   - Module 3: `GET http://localhost:5003/api/status`
   - Module 4: `GET http://localhost:5004/api/status` & `GET http://localhost:5004/api/graph/stats`
5. **Test Suites**:
   Run full automated verification across all modules:
   ```bash
   python check_setup.py
   python final_verify_m2.py
   python -m pytest module3/ -v
   python -m pytest module4/ -v
   ```
   *(All 64+ automated unit & integration tests pass 100%).*

---

## 🏗️ System Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES & INGESTION                        │
│   • 159 Wells Metadata (Volve, FORCE 2020, Synthetic)                  │
│   • 1,959 Structured Daily Drilling Report (DDR) Events               │
│   • 16,670 Rows Volve 15/9-F-9A High-Frequency WITSML Telemetry        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│               MODULE 1: DATA FOUNDATION & NLP EXTRACTION               │
│   • DDR Event Extraction & Normalization into 18 Canonical Tokens      │
│   • 63 Real Ground-Truth Incidents Flagged (Stuck Pipe, Mud Loss, etc.)│
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│ MODULE 2: GEOSPATIAL & SIMILARITY│        │ MODULE 3: TELEMETRY & ANOMALY    │
│ • Analytical Hierarchy Process   │        │ • Telemetry Simulator (Port 5002)│
│   (AHP) Pairwise Eigenvector     │        │ • Recursive CUSUM & Z-Score      │
│ • 5 Drilling Hazards Weighting   │        │ • Smith-Waterman Dynamic Align   │
│ • 59 Formation Tops Correlation  │        │ • Wilson Score Confidence Interv.│
│ • Flask UI @ Port 5001           │        │ • +106.48m Early Warning Lead    │
└────────────────┬─────────────────┘        │ • Monitor Dashboard @ Port 5003  │
                 │                          └────────────────┬─────────────────┘
                 │                                           │
                 └─────────────────────────┬─────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│            MODULE 4: KNOWLEDGE GRAPH, GRAPHRAG & AI BRIEFING           │
│   • 4,037 Nodes & 12,392 Edges Multi-Relational Directed Graph         │
│   • Vis.js Physics Simulation with Spacing Controls & Dynamic Clust.   │
│   • Two-Stage GraphRAG (AHP Subgraph Pre-filter + Semantic Retrieval)  │
│   • Gemini 1.5 Flash AI Pre-Spud & Pre-Tour Drilling Briefings         │
│   • Strict PS Rules: Immutable Risk Scores + Automated [NODE_ID] Checks│
│   • Web Studio @ Port 5004                                             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Step-by-Step Manual Execution (Individual Terminals)

If you prefer to run each service in its own terminal window:

### Terminal 1: Module 2 — Geospatial & Offset Similarity Map
```bash
cd NLP/nlp_task_ddr
python module2/app.py
```
- Open: [`http://localhost:5001`](http://localhost:5001)

### Terminal 2: Module 3 — Real-Time Telemetry Replay Server
```bash
cd NLP/nlp_task_ddr
python module3/simulator_server.py --port 5002 --speed 5.0
```
- Listens on port 5002; WebSocket endpoint: `ws://localhost:5002/ws/telemetry`

### Terminal 3: Module 3 — Anomaly Detection & Live Risk Monitor
```bash
cd NLP/nlp_task_ddr
python module3/anomaly_server.py --port 5003 --simulator-url ws://localhost:5002/ws/telemetry
```
- Open: [`http://localhost:5003/monitor`](http://localhost:5003/monitor)

### Terminal 4: Module 4 — Knowledge Graph, GraphRAG & LLM Briefing
```bash
cd NLP/nlp_task_ddr
python module4/app.py
```
- Open: [`http://localhost:5004`](http://localhost:5004)

---

## 🌟 Key Features & Problem Statement Compliance

### 1. Analytical Hierarchy Process (AHP) Offset Well Similarity (Module 2)
- Ranks offset wells per hazard using 5 multi-criteria parameters:
  - Spatial Distance (Haversine UTM31N)
  - Formation Sequence Match (Jaccard Index)
  - Trajectory & Well Profile (Dogleg severity & inclination)
  - Mud System & BHA Compatibility
  - Target Depth Proximity
- Consistency Ratio ($CR < 0.10$) mathematically validated for all 5 hazards.

### 2. Zero-Leakage Causal Anomaly Detection & Backtesting (Module 3)
- Real 2014 Volve North Sea Well `15/9-F-9A` stuck pipe incident backtest:
  - **Actionable Lead Distance:** **+106.48 metres** prior to lockup.
  - **Actionable Lead Time:** **+44.07 minutes** (over **4.2 hours** at 25 m/hr ROP).
- CUSUM self-resetting drift detector + rolling Z-score filters.
- Smith-Waterman local sequence alignment with Wilson Score Confidence Intervals.
- Strict temporal causality: past data only, zero future leakage verified by test suite.

### 3. Multi-Relational Knowledge Graph & Vis.js Interactive Canvas (Module 4)
- **Scale:** 4,037 nodes and 12,392 directed edges.
- **Node Types:** Well (159), Event (1,898), Formation (59), Hazard (5), Intervention (12), Outcome (5), ReportSnippet (1,898).
- **Edge Types:** `DRILLED_THROUGH`, `HAD_EVENT`, `LED_TO`, `MITIGATED_BY`, `ANALOG_FOR_HAZARD`, `EXTRACTED_FROM`, `FOLLOWED_BY`.
- **Interactive Controls:**
  - Physics simulation with spring distance slider (prevents graph cluttering).
  - Hazard filtering (Stuck Pipe, Mud Loss, Overpressure, Torque Spike, Cementing).
  - Search by well ID or formation name.
  - Subgraph node inspector with metadata cards.

### 4. Hybrid GraphRAG & Gemini Pre-Spud Briefing Engine (Module 4)
- **Two-Stage Retrieval:** Pre-filters graph using Module 2's AHP analog subgraph first, then applies `all-MiniLM-L6-v2` dense embeddings on incident snippets.
- **Strict Anti-Hallucination Constraints:**
  - Risk score numbers and Wilson CIs are injected exclusively from Module 3 (never hallucinated).
  - Every factual sentence forces a `[NODE_ID]` citation.
  - Automated keyword verification pass checks every citation against the Knowledge Graph node data.
  - Disagreements among offset analogs are explicitly highlighted for rig engineers.

---

## 🧪 Verification & Quality Assurance

To verify that all components are functioning properly:

```bash
cd NLP/nlp_task_ddr

# 1. Module 1 Data Contracts
python check_setup.py

# 2. Module 2 Geospatial & AHP Weights
python final_verify_m2.py

# 3. Module 3 Leakage, Anomaly & Sequence Matcher Tests (50/50 Pass)
python -m pytest module3/test_leakage.py module3/test_sequence_matcher.py module3/test_anomaly.py module3/test_simulator.py -v

# 4. Module 4 Knowledge Graph, GraphRAG, Citations & REST API (14/14 Pass)
python -m pytest module4/test_module4.py -v
```

---

## 📁 Repository Directory Layout

```
SIH_2026_PLANNS/
├── start_all.bat                           # 1-Click Windows Batch Launcher
├── start_all.ps1                           # 1-Click PowerShell Launcher
├── README.md                               # This master documentation
│
└── NLP/nlp_task_ddr/
    ├── requirements.txt                    # Consolidated project dependencies
    ├── run_all_modules.py                  # Master multi-process supervisor
    ├── start_all.bat                       # Local batch launcher
    ├── start_all.ps1                       # Local PowerShell launcher
    │
    ├── results/
    │   ├── module1_outputs/                # Module 1 Deliverables
    │   │   ├── wells_metadata.json         # 159 wells
    │   │   ├── events.jsonl                # 1,959 drilling events
    │   │   ├── flagged_real_incidents.json # 63 real ground truth incidents
    │   │   └── telemetry/15_9-F-9A.csv     # 16,670 rows real Volve telemetry
    │   │
    │   └── module3_outputs/                # Module 3 Backtest & Risk Deliverables
    │       ├── backtest_result.json        # +106.48m early warning result
    │       ├── backtest_plot.png           # 300 DPI time-series plot
    │       └── risk_predictions.jsonl      # Causal timestamped predictions
    │
    ├── module2/                            # Module 2: Geospatial & Similarity
    │   ├── app.py                          # Flask server (Port 5001)
    │   ├── compute_similarity.py           # AHP calculation engine
    │   ├── templates/map.html              # Leaflet.js interactive map
    │   └── outputs/
    │       ├── analog_wells.json           # 159 wells x 5 hazards ranked analogs
    │       └── ahp_weights.json            # Pairwise comparison matrices
    │
    ├── module3/                            # Module 3: Telemetry & Anomaly
    │   ├── simulator_server.py             # Telemetry replay server (Port 5002)
    │   ├── anomaly_server.py               # Risk & Anomaly server (Port 5003)
    │   ├── anomaly_detector.py             # CUSUM & Z-Score algorithms
    │   ├── sequence_matcher.py             # Smith-Waterman & Wilson score
    │   ├── monitor.html                    # Real-time monitoring dashboard
    │   └── test_*.py                       # Unit tests (50 tests)
    │
    └── module4/                            # Module 4: Knowledge Graph & LLM
        ├── app.py                          # Flask web server (Port 5004)
        ├── knowledge_graph.py              # 4,037-node NetworkX graph engine
        ├── graph_rag.py                    # Graph-anchored semantic retrieval
        ├── llm_briefing.py                 # Gemini briefing generator with citations
        ├── test_module4.py                 # Automated test suite (14 tests)
        ├── templates/
        │   ├── module4.html                # Vis.js interactive studio UI
        │   └── vis-network.min.js          # Standalone offline Vis.js library
        └── outputs/
            ├── knowledge_graph.gpickle     # Serialized Knowledge Graph
            ├── graph_stats.json            # Graph node/edge summary stats
            └── BRF_*.json                  # Generated briefing reports
```

---

## ⚙️ Environment Variables (Optional)

- `GOOGLE_API_KEY`: Google AI Studio API key for Gemini 1.5 Flash.
  - Can also be entered dynamically directly in the Module 4 UI at `http://localhost:5004`.
  - If no API key is provided, offline briefing mode and all graph/RAG functionalities continue to operate smoothly.