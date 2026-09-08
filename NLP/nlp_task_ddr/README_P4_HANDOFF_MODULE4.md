# README — Person 4 Handoff: NWIS-Sentinel Complete System (Modules 1–3) → Module 4
## NWIS-Sentinel | SIH 2026 | PS SIH26121 — Oil India Limited

---

> **P4 — READ THIS FIRST BEFORE WRITING A SINGLE LINE OF CODE.**  
> Everything built by Persons 1, 2, and 3 is already on disk. Your only job is to read this file carefully, then begin Module 4 (Knowledge Graph + GraphRAG + LLM Briefing + Final Dashboard). You do NOT need to re-run Modules 1, 2, or 3 to start work.

---

## ✅ Completion Status: What Is Ready For You

| Module | Person | Status | Key Deliverable |
|---|---|---|---|
| **Module 1** — Data Foundation, OCR & NLP | P1 | ✅ COMPLETE | 159 wells, 1959 events, real Volve telemetry |
| **Module 2** — Geospatial & AHP Similarity | P2 | ✅ COMPLETE | Ranked analog wells for all 5 hazards × 159 wells |
| **Module 3** — Telemetry Simulation, Anomaly Detection & Backtest | P3 | ✅ COMPLETE | **+106.48 m / +44.07 min early warning lead time** on real 2014 stuck pipe incident |
| **Module 4** — Knowledge Graph, GraphRAG, LLM Briefing & Dashboard | **P4 (YOU)** | 🔲 YOUR TASK | Final unified dashboard |

---

## 📂 Complete File Tree (All Modules)

```
NLP/nlp_task_ddr/
│
├── README_P4_HANDOFF_MODULE4.md            ← YOU ARE HERE
├── requirements.txt                         ← Python dependencies for whole project
│
├── results/
│   ├── module1_outputs/                     ← ALL MODULE 1 OUTPUTS
│   │   ├── README_module1_data_and_nlp.md
│   │   ├── wells_metadata.json              ← 159 wells, full metadata
│   │   ├── events.jsonl                     ← 1,959 drilling events (NDJSON)
│   │   ├── events_summary.csv               ← Same events in tabular form
│   │   ├── event_type_vocabulary.json       ← 18 canonical event tokens
│   │   ├── flagged_real_incidents.json      ← 63 real verified incidents (incl. backtest seed)
│   │   └── telemetry/
│   │       └── 15_9-F-9A.csv               ← 16,670 rows real Volve MWD telemetry
│   │
│   └── module3_outputs/                     ← MODULE 3 OUTPUTS MIRROR (for easy P4 access)
│       ├── README_module3_prediction_and_backtest.md
│       ├── backtest_result.json             ← FLAGSHIP: +106.48 m lead time result
│       ├── backtest_plot.png                ← 300 DPI time-series comparison plot
│       ├── risk_predictions.jsonl           ← 662 timestamped risk predictions with Wilson CIs
│       └── sequence_matches.json            ← Smith-Waterman analog alignments per hazard
│
├── module2/                                 ← MODULE 2 CODE + OUTPUTS
│   ├── README_module2_geospatial_and_similarity.md
│   ├── compute_similarity.py               ← (Already run, outputs exist — do NOT re-run)
│   ├── app.py                              ← Flask map server (port 5001)
│   ├── templates/map.html                  ← Leaflet.js interactive map
│   └── outputs/
│       ├── analog_wells.json               ← 75 MB — ALL hazard rankings for ALL 159 wells
│       ├── ahp_weights.json                ← AHP pairwise matrices + eigenvector weights
│       └── formation_correlation.json      ← 59 formations × depths across 159 wells
│
└── module3/                                 ← MODULE 3 CODE + OUTPUTS
    ├── README_module3_prediction_and_backtest.md
    ├── simulator_server.py                  ← Live telemetry replay (port 5002)
    ├── anomaly_server.py                    ← Anomaly detection + sequence matching (port 5003)
    ├── anomaly_detector.py                  ← Z-score + CUSUM engine
    ├── sequence_matcher.py                  ← Smith-Waterman + Wilson CI engine
    ├── telemetry_simulator.py               ← Core telemetry replay state machine
    ├── backtest_runner.py                   ← Offline time-travel backtest engine
    ├── monitor.html                         ← Module 3 live monitor UI
    ├── test_leakage.py                      ← Zero-leakage verification suite (5/5 PASS)
    └── outputs/
        ├── backtest_result.json             ← Primary: +106.48 m lead time result
        ├── backtest_plot.png                ← 300 DPI backtest visualization
        ├── risk_predictions.jsonl           ← 662 causal risk predictions
        └── sequence_matches.json            ← Offset analog alignments
```

---

## 📄 Module 1 Outputs — What They Contain & How To Load Them

**Working directory: `NLP/nlp_task_ddr/`** — all relative paths below are from there.

### `results/module1_outputs/wells_metadata.json`
Array of 159 well objects. Each looks like:
```json
{
  "well_id": "15/9-F-9A",
  "source": "real_volve",
  "is_synthetic": false,
  "latitude": 58.3,
  "longitude": 2.1,
  "formation_tops": ["Heimdal", "Ty", "Lista"],
  "bha_type": "rotary",
  "mud_program": "WBM",
  "trajectory": "vertical",
  "total_depth_m": 1206.0
}
```
- **159 total wells**: ~9 real Volve wellbores, 118 real FORCE 2020 wells, 40 synthetic wells
- `is_synthetic: true` is always set on synthetic records — never silently mixed

### `results/module1_outputs/events.jsonl`
NDJSON — one JSON object per line. 1,959 events total:
```json
{"well_id":"15/9-F-9A","event_id":"NO_2014-02-05_EVT_STUCK_PIPE","event_type_id":"EVT_STUCK_PIPE","hazard":"stuck_pipe","depth_m":619.0,"report_date":"2014-02-05","is_synthetic":false,"raw_text":"..."}
```
**Load with:**
```python
import json
events = [json.loads(line) for line in open("results/module1_outputs/events.jsonl")]
```

### `results/module1_outputs/event_type_vocabulary.json`
18 canonical event tokens. This is the shared vocabulary across all modules:
```json
{
  "event_types": {
    "EVT_STUCK_PIPE": {"hazard": "stuck_pipe", "severity_default": "CRITICAL", "description": "..."},
    "EVT_TIGHT_HOLE":  {"hazard": "stuck_pipe", "severity_default": "WARN", "description": "..."},
    ...
  }
}
```

### `results/module1_outputs/flagged_real_incidents.json`
63 verified real historical incidents. The backtest uses:
```json
{"event_id": "NO_2014-02-05_EVT_STUCK_PIPE", "well_id": "15/9-F-9A", "depth_m": 619.0, "hazard": "stuck_pipe", "report_date": "2014-02-05", "raw_text": "Replaced TDS service loop..."}
```

### `results/module1_outputs/telemetry/15_9-F-9A.csv`
16,670 rows of real WITSML-origin MWD telemetry. Column names (15 channels):
```
Measured Depth m | Hole Depth (TVD) m | Average Rotary Speed rpm | 
Corrected Total Hookload kkgf | Total Hookload kkgf | Averaged WOB kkgf | 
Mud Density In g/cm3 | Mud Density Out g/cm3 | Mud Density In g/cm3.1 |
ROPIH s/m | Pump Pressure bar | ...
```

---

## 📄 Module 2 Outputs — What They Contain & How To Load Them

### `module2/outputs/analog_wells.json` (75 MB)
The largest file in the project. Structure:
```json
{
  "15/9-F-9A": {
    "stuck_pipe": [
      {
        "well_id": "FORCE2020_34_10-35",
        "source": "real_force2020",
        "is_synthetic": false,
        "weighted_score": 0.87,
        "feature_breakdown": {"formation_sim": 0.89, "trajectory_sim": 0.92, ...},
        "ahp_weights_used": {"formation": 0.497, "trajectory": 0.245, ...}
      },
      ...  // 158 analogs ranked descending
    ],
    "mud_loss": [...],
    "overpressure": [...],
    "torque_spike": [...],
    "cementing": [...]
  },
  ...  // all 159 wells
}
```
**For P4 Knowledge Graph:** Use this for `ANALOG_FOR_HAZARD` graph edges.  
**For P4 Dashboard:** Show the `feature_breakdown` table — it is the AHP no-black-box proof.

### `module2/outputs/ahp_weights.json`
Fully auditable AHP matrices per hazard. Example:
```json
{
  "stuck_pipe": {
    "weights": {"formation": 0.497, "mud_weight": 0.245, "bha_type": 0.105, "mud_type": 0.105, "trajectory": 0.047},
    "consistency_ratio": 0.028,
    "consistency_acceptable": true,
    "engineering_rationale": "Wellbore trajectory dominates differential sticking risk..."
  }
}
```

### `module2/outputs/formation_correlation.json`
59 unique geological formations indexed. Query by formation name:
```json
{
  "Heimdal": {
    "well_count": 53,
    "depth_range_m": {"min": 755.0, "max": 4374.0},
    "wells": [{"well_id": "...", "depth_md_m": 2806.0, ...}]
  }
}
```

### Module 2 Flask API (when `python module2/app.py` is running on port 5001)
| Endpoint | Returns |
|---|---|
| `GET /api/wells` | All 159 wells with lat/lon |
| `GET /api/analogs?well_id=15/9-F-9A&hazard=stuck_pipe&top=10` | Top-K analog wells with breakdown |
| `GET /api/ahp_weights` | Full AHP matrices |
| `GET /api/formation/<name>` | All wells in a formation |
| `GET /api/well/<well_id>` | Single well full metadata |

---

## 📄 Module 3 Outputs — What They Contain & How To Load Them

### `results/module3_outputs/backtest_result.json`
The flagship deliverable. Key fields for P4:
```json
{
  "summary": {
    "well_id": "15/9-F-9A",
    "incident_event_id": "NO_2014-02-05_EVT_STUCK_PIPE",
    "incident_depth_m": 619.0,
    "lead_time_metrics": {
      "actionable_lead_distance_metres": 106.48,
      "actionable_lead_time_minutes_telemetry": 44.07,
      "actionable_lead_time_hours_at_25m_hr_rop": 4.26
    },
    "system_decision": "PIPE STICKING RISK MITIGATED — 106.48 m prior to pipe lockup."
  },
  "alert_milestones": {...},
  "causality_and_leakage_audit": {"zero_future_leakage_guaranteed": true, "audit_tests_passed": "5/5"}
}
```
**P4 Dashboard:** Feature this as the visual centrepiece. Show the 106.48 m / 44.07 min headline prominently.

### `results/module3_outputs/backtest_plot.png`
300 DPI PNG (3633×2401 px). Shows telemetry curves, the green alert zone, and the red incident line. Embed directly in the Module 4 dashboard panel.

### `results/module3_outputs/risk_predictions.jsonl`
662 records of real-time risk evaluations (one per evaluation interval). Each:
```json
{
  "timestamp": "2026-09-09T...",
  "well_id": "15/9-F-9A",
  "measured_depth_m": 512.52,
  "hazard": "stuck_pipe",
  "risk_level": "CRITICAL",
  "risk_score": 0.8,
  "wilson_ci": {"lower": 0.49, "center": 0.80, "upper": 0.94, "n_trials": 10, "n_successes": 8},
  "feature_weights_and_breakdown": {...},
  "explanation": "Average Rotary Speed collapsed 3.2σ below baseline...",
  "actionable_threshold_crossed": true
}
```
**P4 LLM Briefing:** Feed `explanation` + `feature_weights_and_breakdown` into the LLM system prompt. **NEVER let the LLM restate the numeric risk score** — always pull it from this file directly.

### `results/module3_outputs/sequence_matches.json`
Per-hazard Smith-Waterman alignment results against 41 offset wells:
```json
{
  "target_well_id": "15/9-F-9A",
  "hazard_evaluations": {
    "stuck_pipe": {
      "wilson_ci": {"lower": 0.49, "center": 0.80, "upper": 0.94},
      "top_analog_alignments": [
        {"analog_well_id": "FORCE2020_...", "normalized_score": 0.87, "aligned_query": [...], "aligned_reference": [...]}
      ]
    }
  }
}
```

### Module 3 Live Server APIs (when servers are running)
**Start Telemetry Simulator (Port 5002):**
```powershell
python module3/simulator_server.py --port 5002 --speed 5.0
```
| Endpoint | What it does |
|---|---|
| `WS ws://localhost:5002/ws/telemetry` | Live row-by-row telemetry broadcast |
| `GET /api/telemetry/status` | Current depth, row, speed, connection count |
| `POST /api/telemetry/control` | `{"action": "pause/resume/reset/set_speed", "speed_multiplier": N}` |

**Start Anomaly & Sequence Server (Port 5003):**
```powershell
python module3/anomaly_server.py --port 5003 --simulator-url ws://localhost:5002/ws/telemetry
```
| Endpoint | What it does |
|---|---|
| `WS ws://localhost:5003/ws/anomaly` | Live anomaly alerts + sequence match results |
| `GET /api/anomaly/status` | Detector config, buffer size, alert count |
| `GET /api/anomaly/alerts` | Last N alerts with full Z-score, CUSUM breakdown |
| `GET /api/sequence/match/latest` | Current Wilson CI risk across all hazards |
| `GET /api/backtest/results` | Full backtest_result.json via API |
| `GET /outputs/backtest_plot.png` | Serve the backtest plot image |
| `POST /api/anomaly/reset` | Reset buffer and CUSUM state |

---

## 🏗️ What You Must Build: Module 4

As specified in `PLANNNNN_extracted.txt` Section 7 (lines 198–236):

### Step 1 — Knowledge Graph (`networkx`)
Build an in-memory property graph with these node types:
- `Well`, `Formation`, `Event`, `Hazard`, `Intervention`, `Outcome`, `ReportSnippet`

And these edges:
- `DRILLED_THROUGH` (Well → Formation)
- `HAD_EVENT` (Well → Event)
- `FOLLOWED_BY` (Event → Event, sequence)
- `MITIGATED_BY` (Event → Intervention)
- `LED_TO` (Event → Outcome)
- `ANALOG_FOR_HAZARD` (Well → Well — **use `analog_wells.json` directly, do not recompute**)
- `EXTRACTED_FROM` (Event → ReportSnippet, full citation traceability)

**Load from:**
- `results/module1_outputs/events.jsonl` → `HAD_EVENT`, `FOLLOWED_BY`, `EXTRACTED_FROM` edges
- `module2/outputs/analog_wells.json` → `ANALOG_FOR_HAZARD` edges (pre-computed, use directly)

### Step 2 — GraphRAG Retrieval
**This order is mandatory (core novelty):**
1. Pre-filter: restrict graph to only analog wells flagged by Module 2/3 for the specific hazard
2. Fine-grained retrieval: sentence-transformer embedding similarity WITHIN the filtered subgraph only

**Do NOT do plain vector search over all documents** — that misses the pre-filtering step which is the architectural innovation.

### Step 3 — LLM Briefing Generator (Gemini API)
- Use Gemini API (credentials available in workspace env vars or ask for them)
- Every generated sentence must cite a specific graph node ID or report-snippet ID in brackets
- After generation, run automatic verification: check every cited source actually supports the claim
- Log every verification result — this is the "no hallucination" proof
- **The LLM must NEVER generate the numeric risk score** (use Module 3's `risk_predictions.jsonl` directly)
- **Always show Wilson CI bounds** — never let the LLM paraphrase away the uncertainty

### Step 4 — Final Unified Dashboard
Build one dashboard (React or Streamlit) with these panels:
- **Panel A**: Module 2 geospatial map (embed `module2/app.py` as iframe at `localhost:5001`, or migrate `module2/templates/map.html` directly)
- **Panel B**: Searchable knowledge repository (query `events.jsonl` via graph)
- **Panel C**: Live telemetry stream from Module 3 (`ws://localhost:5003/ws/anomaly`), showing real-time risk alerts with full feature/weight breakdown and LLM briefing as they generate
- **Panel D**: **THE FLAGSHIP** — Historical Backtest Panel. Embed `results/module3_outputs/backtest_plot.png`. Show the **+106.48 m / +44.07 min** lead time headline. This must be the visual centrepiece.
- **Panel E**: Depth-synchronized multi-well playback comparing current well against matched analogs

### Step 5 — Produce
1. The full running dashboard application with exact run command in README
2. `README_module4_integration_and_dashboard.md` with:
   - Total real vs synthetic data used across all 4 modules
   - The backtest lead-time headline result
   - Every API/credential used in the final system

---

## 🚀 To Start All Backend Services At Once

Open **3 PowerShell terminals**, all from `NLP/nlp_task_ddr/`:

**Terminal 1 — Module 2 Map Server:**
```powershell
python module2/app.py
# → http://localhost:5001
```

**Terminal 2 — Module 3 Telemetry Simulator:**
```powershell
python module3/simulator_server.py --port 5002 --speed 5.0
# → ws://localhost:5002/ws/telemetry
```

**Terminal 3 — Module 3 Anomaly & Intelligence Server:**
```powershell
python module3/anomaly_server.py --port 5003 --simulator-url ws://localhost:5002/ws/telemetry
# → ws://localhost:5003/ws/anomaly
# → http://localhost:5003/monitor (Module 3 live dashboard — open to verify it works)
```

---

## 📦 Python Dependencies

Install everything P4 will need:
```powershell
pip install fastapi uvicorn websockets pandas numpy scipy matplotlib statsmodels flask networkx sentence-transformers google-generativeai streamlit
```

Or use the existing `requirements.txt` in the project root and add your additional packages.

---

## ⚠️ Hard Rules (From Global Project Rules — Do NOT Violate)

1. **NO HARDCODING, NO FABRICATED OUTPUTS**: Every number shown in the dashboard must come from real computation on real data.
2. **NO SILENT API STUBS**: If Gemini/Vertex AI credentials are missing, stop and ask. Do not mock LLM responses.
3. **FULL TRANSPARENCY — NO BLACK BOXES**: Every risk score displayed must show its feature weights and Wilson CI. Use `feature_weights_and_breakdown` and `wilson_ci` from `risk_predictions.jsonl`.
4. **FORCED-CITATION LLM**: Every LLM sentence must cite a specific graph node ID. Run verification after generation.
5. **DO NOT REBUILD modules 1, 2, or 3**: All their outputs are already on disk. Never recompute `analog_wells.json` — it takes ~2 minutes and 75 MB of output.

---

## 📊 System-Wide Data Summary (For Your Final README)

| Module | Data Type | Source | Real/Synthetic | Scale |
|---|---|---|---|---|
| M1 | Volve DDR reports | HuggingFace `bengsoon/volve_alpaca` | **REAL** | 1,759 reports, ~9 wellbores |
| M1 | FORCE 2020 well logs | Zenodo #4351156 | **REAL** | 118 NCS wells |
| M1 | Synthetic DDR corpus | Rule-based template + RNG (seed=42) | **SYNTHETIC** | 200 reports, 40 wells |
| M1 | Volve MWD telemetry | Equinor/Kaggle | **REAL** | 16,670 rows, 15 channels |
| M2 | AHP similarity scores | Computed from M1 | **DERIVED** | 159 × 158 × 5 hazard pairs |
| M3 | Z-score / CUSUM detections | Computed from real telemetry | **DERIVED** | 4,306 alerts from 16,670 rows |
| M3 | Wilson CI risk predictions | Smith-Waterman + statsmodels | **DERIVED** | 662 causal evaluations |
| M3 | **Backtest lead time result** | Real 2014 incident, real math | **REAL+DERIVED** | **+106.48 m / +44.07 min** |

---

## 🏆 The Headline You Must Feature in the Dashboard

```
NWIS-Sentinel provided a +106.48 metre / +44.07 minute advance warning
of the confirmed February 2014 stuck pipe incident on Volve Well 15/9-F-9A,
operating with verified zero future data leakage on 16,670 real WITSML sensor readings.
```

This is the project's most powerful result. It must be on the landing screen of the final dashboard.

---

*Generated: 2026-09-09 | P3 → P4 Handoff | Module handoff: Ready for P4*
