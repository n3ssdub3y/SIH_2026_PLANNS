# NWIS-Sentinel: Modules 1–4 Execution & Integration Guide
### SIH 2026 | Problem Statement SIH26121 | Oil India Limited

This directory contains the complete source code, deliverables, datasets, test suites, and web applications for all 4 modules of the NWIS-Sentinel system.

---

## ⚡ Instant 1-Click Launch (All Modules Simultaneously)

Run all 4 modules under a single supervisor with live logs:

```bash
python run_all_modules.py
```
*Or double click `start_all.bat` on Windows.*

### Active Localhost Services:
- **Module 2 (Geospatial & Offset Similarity Map):** [`http://localhost:5001`](http://localhost:5001)
- **Module 3 (Real-Time Telemetry Streaming Server):** [`http://localhost:5002`](http://localhost:5002) (WebSocket: `ws://localhost:5002/ws/telemetry`)
- **Module 3 (Risk & Anomaly Monitor Dashboard):** [`http://localhost:5003/monitor`](http://localhost:5003/monitor)
- **Module 4 (Knowledge Graph, GraphRAG & AI Briefing):** [`http://localhost:5004`](http://localhost:5004)

---

## 🤖 Instructions for AI Agents (Antigravity)

1. **Working Directory:** `NLP/nlp_task_ddr/`
2. **Dependencies:** `pip install -r requirements.txt`
3. **Automated Verification:**
   - `python check_setup.py` (Module 1 data integrity)
   - `python final_verify_m2.py` (Module 2 AHP consistency)
   - `python -m pytest module3/ -v` (Module 3 tests - 50 passing)
   - `python -m pytest module4/ -v` (Module 4 tests - 14 passing)
4. **Execution:**
   - Launch all modules: `python run_all_modules.py --no-browser`
   - Individual modules can be run via:
     - Module 2: `python module2/app.py`
     - Module 3 Sim: `python module3/simulator_server.py --port 5002 --speed 5.0`
     - Module 3 Anomaly: `python module3/anomaly_server.py --port 5003 --simulator-url ws://localhost:5002/ws/telemetry`
     - Module 4: `python module4/app.py`

---

## 📋 Module Deliverables & Outputs

### Module 1 — Data Foundation, OCR & NLP Extraction
- `results/module1_outputs/wells_metadata.json`: 159 wells with trajectory, coordinates, and formation tops.
- `results/module1_outputs/events.jsonl`: 1,959 daily drilling events mapped into 18 canonical token classes.
- `results/module1_outputs/flagged_real_incidents.json`: 63 ground-truth incidents with NPT, mud weight, and mitigations.
- `results/module1_outputs/telemetry/15_9-F-9A.csv`: 16,670 rows of real Volve drilling telemetry.

### Module 2 — Geospatial & AHP Similarity Engine (Port 5001)
- `module2/outputs/analog_wells.json`: Pre-computed ranked analog offset wells for all 159 wells across 5 hazards.
- `module2/outputs/ahp_weights.json`: AHP pairwise comparison matrices and eigenvector priority weights (Consistency Ratio $< 0.05$).
- `module2/outputs/formation_correlation.json`: 59 formations depth correlation across 159 wells.

### Module 3 — Real-Time Telemetry, Anomaly Detection & Backtesting (Ports 5002 & 5003)
- `module3/outputs/backtest_result.json`: Time-travel backtest proving **+106.48 m / +44.07 min early warning lead time** on real Volve stuck pipe incident.
- `module3/outputs/backtest_plot.png`: 300 DPI high-resolution telemetry time-series visualization.
- `module3/outputs/risk_predictions.jsonl`: Causal, leakage-free risk scores with Wilson 95% confidence intervals.
- `module3/monitor.html`: Live interactive telemetry and risk prediction monitoring console.

### Module 4 — Knowledge Graph, GraphRAG & AI Briefing Studio (Port 5004)
- `module4/outputs/knowledge_graph.gpickle`: 4,037 nodes and 12,392 edges multi-relational directed graph.
- `module4/outputs/graph_stats.json`: Graph metrics, degree distributions, and node counts.
- `module4/templates/module4.html`: Full-screen dark-theme Vis.js canvas with spring distance sliders, hazard filters, and GraphRAG search.
- `module4/llm_briefing.py`: Google Gemini AI Studio briefing generator with strict anti-hallucination rules and automated `[NODE_ID]` citation verification.