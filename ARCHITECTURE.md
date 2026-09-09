# eRTMAC-NWIS — Nearby Wells Intelligence System
## Architecture Document

> **Smart India Hackathon 2026 | Problem Statement: SIH26121 | Organization: Oil India Limited**
> **System:** Real-Time Measurement Across Channels — Nearby Wells Intelligence System
> **Purpose:** AI-powered Offset Well Knowledge, Real-Time Telemetry & Decision Support for drilling engineers

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Module 1 — Data Foundation & NLP Pipeline](#3-module-1--data-foundation--nlp-pipeline)
4. [Module 2 — Geospatial Map & AHP Offset-Well Similarity Engine](#4-module-2--geospatial-map--ahp-offset-well-similarity-engine)
5. [Module 3 — Real-Time Telemetry Streaming & Anomaly Detection](#5-module-3--real-time-telemetry-streaming--anomaly-detection)
6. [Module 4 — Knowledge Graph, GraphRAG & AI Briefing Studio](#6-module-4--knowledge-graph-graphrag--ai-briefing-studio)
7. [Module 5 — Engineering Decision Support Agent](#7-module-5--engineering-decision-support-agent)
8. [Cross-Module Data Flow](#8-cross-module-data-flow)
9. [System Orchestration & Deployment](#9-system-orchestration--deployment)
10. [Technology Stack Summary](#10-technology-stack-summary)
11. [Data Schema Contracts](#11-data-schema-contracts)

---

## 1. System Overview

eRTMAC-NWIS is a **multi-module AI platform** for real-time drilling hazard prediction, offset-well intelligence, and decision support. It integrates real-world datasets (Volve Field WITSML + FORCE 2020 NCS wells) with NLP extraction, live telemetry anomaly detection, knowledge graph reasoning, and LLM-powered decision support into a unified five-module system.

### Core Design Principles

- **No hardcoding** — all numbers derive from real computation
- **Full transparency** — every event, score, and alert shows its source, method, and confidence
- **No silent stubs** — every pipeline step is real working code
- **Dataset scale** — 100+ real wells + synthetic augmentation + 16,670 real WITSML rows

### Service Map

| Module | Port | Protocol | Role |
|--------|------|----------|------|
| Module 1 | _(offline)_ | — | Data foundation, NLP extraction |
| Module 2 | 5001 | HTTP (Flask) | Geospatial map + AHP analog ranking |
| Module 3 Simulator | 5002 | HTTP + WebSocket (FastAPI) | Live telemetry replay stream |
| Module 3 Anomaly | 5003 | HTTP + WebSocket (FastAPI) | Real-time risk detection + monitor UI |
| Module 4 | 5004 | HTTP (Flask) | Knowledge graph + GraphRAG + AI briefings |
| Module 5 | 5005 | HTTP (Flask) | Engineering decision support agent |

---

## 2. High-Level Architecture

```mermaid
graph TD
    subgraph "External Data Sources"
        V["Volve WITSML Field Data\n15/9-F-9A — 16,670 rows"]
        F["FORCE 2020 / NPD\n100+ NCS Wells"]
        H["HuggingFace Volve DDRs\n1,759 Alpaca Reports"]
    end

    subgraph "MODULE 1 — Data Foundation (Offline)"
        M1_NLP["NLP Extraction Engine\nRegex + Keyword Vocab"]
        M1_SYNTH["Synthetic DDR Generator\nTemplate + RNG seed=42"]
        M1_OUT["Module 1 Outputs\nwells_metadata.json\nevents.jsonl\ntelemetry/15_9-F-9A.csv\nflagged_real_incidents.json\nevent_type_vocabulary.json"]
    end

    subgraph "MODULE 2 — Geospatial & AHP :5001"
        M2_SIM["Similarity Engine\ncompute_similarity.py"]
        M2_APP["Flask Web Server\napp.py"]
        M2_OUT["Module 2 Outputs\nanalog_wells.json\nahp_weights.json\nformation_correlation.json"]
        M2_UI["Leaflet Map UI\nmap.html"]
    end

    subgraph "MODULE 3 — Real-Time Telemetry :5002/:5003"
        M3_SIM["Telemetry Simulator\nsimulator_server.py :5002"]
        M3_DET["Anomaly Detector\nanomaly_detector.py\nZ-Score + CUSUM"]
        M3_SEQ["Sequence Matcher\nsequence_matcher.py\nSmith-Waterman + Wilson CI"]
        M3_ANO["Anomaly Server\nanomaly_server.py :5003"]
        M3_BT["Backtest Runner\nbacktest_runner.py"]
        M3_UI["Live Monitor UI\nmonitor.html"]
        M3_OUT["Module 3 Outputs\nrisk_predictions.jsonl\nbacktest_result.json\nsequence_matches.json"]
    end

    subgraph "MODULE 4 — Knowledge Graph & AI :5004"
        M4_KG["Knowledge Graph Builder\nknowledge_graph.py\nNetworkX DiGraph"]
        M4_RAG["GraphRAG Engine\ngraph_rag.py\nsentence-transformers"]
        M4_LLM["LLM Briefing Engine\nllm_briefing.py\nGemini AI"]
        M4_APP["Flask App\napp.py :5004"]
        M4_UI["Vis.js Graph UI\nmodule4.html"]
        M4_OUT["Module 4 Outputs\nknowledge_graph.gpickle\nBRF_*.json briefings"]
    end

    subgraph "MODULE 5 — Engineering Agent :5005"
        M5_DA["Data Adapter\ndata_adapter.py"]
        M5_VS["ChromaDB Vector Store\nvector_store.py"]
        M5_RET["Retriever\nretriever.py"]
        M5_AGT["Engineering Agent\nagent.py\nGemini 2.5 Flash"]
        M5_APP["Flask App\napp.py :5005"]
        M5_UI["Dark Console UI\nmodule5.html"]
    end

    V --> M1_NLP
    F --> M1_NLP
    H --> M1_NLP
    M1_NLP --> M1_OUT
    M1_SYNTH --> M1_OUT

    M1_OUT --> M2_SIM
    M2_SIM --> M2_OUT
    M2_OUT --> M2_APP
    M2_APP --> M2_UI

    M1_OUT --> M3_SIM
    M3_SIM -->|"ws://localhost:5002/ws/telemetry"| M3_ANO
    M3_ANO --> M3_DET
    M3_ANO --> M3_SEQ
    M2_OUT --> M3_SEQ
    M3_ANO --> M3_OUT
    M3_ANO --> M3_UI

    M1_OUT --> M4_KG
    M2_OUT --> M4_KG
    M3_OUT --> M4_LLM
    M4_KG --> M4_RAG
    M4_RAG --> M4_LLM
    M4_KG --> M4_APP
    M4_RAG --> M4_APP
    M4_LLM --> M4_APP
    M4_APP --> M4_UI

    M1_OUT --> M5_DA
    M2_OUT --> M5_DA
    M5_DA --> M5_VS
    M5_VS --> M5_RET
    M2_OUT --> M5_RET
    M5_RET --> M5_AGT
    M5_AGT --> M5_APP
    M5_APP --> M5_UI
```

---

## 3. Module 1 — Data Foundation & NLP Pipeline

### 3.1 Responsibility

Module 1 is the **offline data acquisition and NLP extraction layer**. It ingests real public drilling datasets, runs regex-based Named Entity Recognition (NER) on 1,759 real DDR (Daily Drilling Reports), generates a reproducible synthetic corpus, and emits six structured output files that all downstream modules consume. It does **not** expose an HTTP server.

### 3.2 Source Datasets

| Dataset | Source | Type | Wells | Records |
|---------|--------|------|-------|---------|
| Volve DDRs (alpaca format) | HuggingFace `bengsoon/volve_alpaca` | REAL | ~9 Volve wellbores | 1,759 |
| FORCE 2020 Lithology | Zenodo #4351156 — `NPD_Lithostratigraphy_*` | REAL | 118 NCS wells | Formation tops |
| FORCE 2020 Casing depths | Zenodo — `NPD_Casing_depth_*` | REAL | 118 NCS wells | Casing records |
| Volve F-9A Telemetry | Equinor Volve WITSML depth CSV | REAL | 1 (F-9A) | 16,670 rows |
| Synthetic DDR Corpus | Rule-based templates + `random.seed(42)` | SYNTHETIC | 40 synthetic wells | 200 reports |

### 3.3 Internal Pipeline (7 Steps)

```mermaid
flowchart LR
    A["Step 1\nFORCE 2020 Excel\nwells_metadata.json"] --> B["Step 2\nEvent vocabulary\nevent_type_vocabulary.json"]
    B --> C["Step 3\nNLP on 1759 Volve DDRs\nRegex entity extraction"]
    C --> D["Step 4\nGenerate 200 synthetic DDRs\n40 wells seed=42"]
    D --> E["Step 5\nMerge → events.jsonl\n1959 total events"]
    E --> F["Step 6\nExport Volve telemetry\n16670 rows CSV"]
    F --> G["Step 7\nWrite README\nflagged_real_incidents.json"]
```

### 3.4 NLP Extraction Methodology

**Entry point:** `p1_full_pipeline.py::extract_entities()`

The NLP pipeline uses **deterministic keyword matching** against a canonical 18-class event vocabulary (`EVENT_VOCAB`):

```mermaid
flowchart TD
    RAW["Raw DDR text"] --> TOK["Lowercase text"]
    TOK --> KW{"Keyword scan\nKEYWORD_EVT list"}
    KW -->|Match| EVT_ID["event_type_id\ne.g. EVT_STUCK_PIPE"]
    KW -->|"No match"| ROUT["EVT_ROUTINE_DRILLING"]
    EVT_ID --> FIELDS["Extract fields\nvia regex"]
    FIELDS --> DEPTH["depth_m\n\\d+ m / mTVD"]
    FIELDS --> MW["mud_weight_ppg\nppg/SG/pcf"]
    FIELDS --> NPT["npt_hours\nnpt: \\d+h"]
    FIELDS --> VOL["volume_lost_bbl\n\\d+ bbl"]
    FIELDS --> FM["formation_id\nHordaland Draupne ..."]
    DEPTH & MW & NPT & VOL & FM & EVT_ID --> REC["Event record\nwith confidence score"]
```

**Canonical Event Vocabulary (18 types across 7 hazard categories):**

| Hazard | Event Types |
|--------|-------------|
| `mud_loss` | EVT_MUD_LOSS_PARTIAL, EVT_MUD_LOSS_TOTAL, EVT_LCM_APPLIED, EVT_CIRC_RESTORED |
| `stuck_pipe` | EVT_STUCK_PIPE, EVT_DIFF_STICKING, EVT_TIGHT_HOLE, EVT_JARRING, EVT_FISHING |
| `kick` | EVT_KICK, EVT_GAS_INFLUX, EVT_BOP_SHUTIN |
| `overpressure` | EVT_OVERPRESSURE_DETECTED |
| `torque_spike` | EVT_TORQUE_UP, EVT_TORQUE_SPIKE |
| `cementing` | EVT_CEMENTING_FAILURE, EVT_WOC |
| `none` | EVT_ROUTINE_DRILLING |

### 3.5 Synthetic DDR Generation

`mk_synth()` generates realistic DDR text by filling parameterized templates with controlled random values (`random.seed(42)` ensures full reproducibility). Each synthetic event is explicitly tagged `is_synthetic: True`.

**Distribution:** 50 mud_loss + 50 stuck_pipe + 30 kick + 35 torque_spike + 20 cementing + 15 routine = 200 events across 40 SYNTH-W{01..40} wells.

### 3.6 Output Files

```
results/module1_outputs/
├── wells_metadata.json        ← 159 wells (118 FORCE + 1 Volve + 40 synthetic)
├── events.jsonl               ← 1,959 events (NDJSON, one per line)
├── events_summary.csv         ← Tabular view (no raw_text)
├── event_type_vocabulary.json ← 18 canonical event types v1.0
├── flagged_real_incidents.json← Real documented hazard events
└── telemetry/15_9-F-9A.csv   ← 16,670 rows, 15 sensor channels
```

**Per-event record schema:**
```json
{
  "well_id": "NO_15/9-F-9A",
  "event_id": "NO_15/9-F-9A_2014-02-05_EVT_STUCK_PIPE",
  "report_date": "2014-02-05",
  "depth_m": 619.0,
  "formation_id": "Hordaland",
  "mud_weight_ppg": 9.5,
  "npt_hours": 4.5,
  "volume_lost_bbl": 0.0,
  "event_type_id": "EVT_STUCK_PIPE",
  "hazard": "stuck_pipe",
  "severity": "critical",
  "source": "real_volve",
  "is_synthetic": false,
  "confidence": 0.85,
  "raw_text": "..."
}
```

---

## 4. Module 2 — Geospatial Map & AHP Offset-Well Similarity Engine

### 4.1 Responsibility

Module 2 is the **geospatial intelligence and analog well ranking layer**. It applies Analytic Hierarchy Process (AHP) multi-criteria decision analysis to rank all 159 wells against each other across 5 drilling hazards, produces a Leaflet.js interactive map UI, and exports the analog rankings that all downstream modules consume for context-aware retrieval.

### 4.2 Architecture

```mermaid
graph TD
    M1_DATA["Module 1 Outputs\nwells_metadata.json\nevents.jsonl"] --> CS["compute_similarity.py"]

    subgraph "Compute Similarity Engine"
        CS --> AHP["AHP Weight Calculator\nahp_weights\nahp_consistency_ratio"]
        CS --> FS["Feature Extractors\nformation_set\nbha_tokens\nmud_tokens\nmud_weight_sim\ntrajectory_sim"]
        AHP --> PAIR["Pairwise Similarity\nfor each well × hazard"]
        FS --> PAIR
        PAIR --> SCORE["Weighted Similarity Score\nScore = Σ w_k × sim_k"]
        SCORE --> RANK["Ranked Analog List\nper target well × hazard"]
    end

    CS --> AW["analog_wells.json\n159 wells × 5 hazards"]
    CS --> AHW["ahp_weights.json"]
    CS --> FC["formation_correlation.json"]

    AW & AHW & FC --> APP["Flask app.py :5001"]

    APP --> R1["GET / → map.html"]
    APP --> R2["GET /api/wells"]
    APP --> R3["GET /api/analogs?well_id=&hazard="]
    APP --> R4["GET /api/ahp_weights"]
    APP --> R5["GET /api/formation/:name"]
    APP --> R6["GET /api/well/:well_id"]

    R1 --> UI["Leaflet.js Map\n159 well markers\nAHP scores on click"]
```

### 4.3 AHP Methodology (5 Features × 5 Hazards)

The Analytic Hierarchy Process (Saaty 1980) is applied per hazard. Five features are compared pairwise, producing eigenvector weights that sum to 1.0.

**Features compared:**
- `formation` — Jaccard similarity of formation names shared between wells
- `mud_weight` — Gaussian similarity of average mud weights (from events.jsonl)
- `bha_type` — Jaccard similarity of BHA type tokens
- `mud_type` — Jaccard similarity of mud program tokens
- `trajectory` — Fast Dynamic Time Warping (fastdtw) on inclination profiles

```mermaid
graph LR
    subgraph "AHP Pairwise Matrix per hazard"
        PM["5×5 Pairwise Matrix\nScale 1..9 Saaty"]
        PM --> CS2["Column-normalize\n÷ column sums"]
        CS2 --> EV["Row-average\neigenvector weights"]
        EV --> CR["Consistency Ratio\nCR = CI / RI₅"]
        CR -->|"CR < 0.10"| OK["Weights Acceptable"]
    end
```

**Per-hazard weight rationale:**
- `mud_loss` — Formation dominant + mud weight secondary
- `stuck_pipe` — Trajectory dominant + BHA contact area
- `overpressure` — Mud weight dominant + formation lithology
- `torque_spike` — Trajectory + BHA + mud lubricity
- `cementing` — Mud type dominant + formation bond

**Similarity formula:**
`Similarity(well_i, hazard_h) = Σ_k [ w_(h,k) × sim_k(well_i, target_well) ]`

### 4.4 Feature Similarity Functions

| Feature | Function | Algorithm |
|---------|----------|-----------|
| Formation | `jaccard(formation_set_A, formation_set_B)` | `|A∩B| / |A∪B|` |
| Mud weight | `mud_weight_sim(id_A, id_B)` | Gaussian: `exp(-Δ² / 2·0.3²)`, normalized to MW range |
| BHA type | `jaccard(bha_tokens_A, bha_tokens_B)` | Token Jaccard on lowercased, split BHA string |
| Mud type | `jaccard(mud_tokens_A, mud_tokens_B)` | Token Jaccard on mud_program base_fluid string |
| Trajectory | `trajectory_sim(well_A, well_B)` | fastdtw on 50-point subsampled inclination profiles |

### 4.5 REST API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Serves Leaflet map UI |
| `GET /api/wells` | All 159 wells with lat/lon + hazard event counts |
| `GET /api/analogs?well_id=X&hazard=Y&top=N` | Top-N ranked analogs for well+hazard with full AHP breakdown |
| `GET /api/ahp_weights` | AHP pairwise matrices + eigenvector weights per hazard |
| `GET /api/formation/<name>` | All wells that drilled through a named formation |
| `GET /api/search/formation?q=X` | Formation name substring search |
| `GET /api/well/<well_id>` | Full well metadata record |

### 4.6 Outputs Consumed by Other Modules

| File | Consumed By |
|------|-------------|
| `analog_wells.json` | Module 3 (sequence matching), Module 4 (GraphRAG pre-filter + KG edges), Module 5 (analog retrieval) |
| `ahp_weights.json` | Module 4 (UI display), Module 2 REST API |
| `formation_correlation.json` | Module 2 REST API formation search |

---

## 5. Module 3 — Real-Time Telemetry Streaming & Anomaly Detection

### 5.1 Responsibility

Module 3 is the **real-time predictive intelligence layer**. It is split into two independently running servers:
- **Port 5002 (Simulator Server):** Replays the 16,670-row Volve WITSML telemetry CSV row-by-row over WebSocket, simulating a live eRTMAC/WITSML feed.
- **Port 5003 (Anomaly Server):** Subscribes to the simulator, runs dual-algorithm anomaly detection (Z-score + CUSUM), performs Smith-Waterman sequence alignment against historical analog patterns, computes Wilson Score Confidence Intervals for hazard probabilities, and serves a live browser dashboard.

**Key result:** **+106.48 m early warning** lead time before the confirmed `EVT_STUCK_PIPE` incident at 619 m on well 15/9-F-9A (2014-02-05).

### 5.2 Full Architecture

```mermaid
graph TD
    CSV["15_9-F-9A.csv\n16,670 rows real WITSML"] --> TS["TelemetrySimulator\ntelemetry_simulator.py"]

    subgraph "Port 5002 — Simulator Server"
        TS --> BL["Broadcast Loop\nasyncio background task"]
        BL -->|"ws://5002/ws/telemetry\nJSON row envelope"| WS_SIM["WebSocket Endpoint\n/ws/telemetry"]
        BL --> LATEST["_latest_emitted\ncache"]
        CM["ConnectionManager\nactive client set"] --> BL
        REST_SIM["REST API\n/api/telemetry/status\n/api/telemetry/current\nPOST /config /reset /pause"] --> TS
    end

    WS_SIM -->|"WebSocket subscribe"| CONSUMER["consume_simulator_websocket\nasyncio background task"]

    subgraph "Port 5003 — Anomaly Server"
        CONSUMER --> BUFF["Rolling Buffer\ndeque maxlen=300 rows"]
        BUFF --> AD["AnomalyDetector\nanomaly_detector.py"]

        subgraph "Dual Detector"
            AD --> ZS["Rolling Z-Score\nwindow=30\nthreshold=2.5σ"]
            AD --> CU["CUSUM\nk=0.5σ allowance\nh=5.0σ threshold"]
        end

        ZS & CU --> ALERTS["AnomalyAlert objects\nalert_id, channel, hazard\nseverity, z_score, cusum\nexplanation"]
        ALERTS --> AH["Alert History\nmaxlen=500"]
        AH -->|"every 25 rows"| SM["SequenceMatcher\nsequence_matcher.py"]

        subgraph "Smith-Waterman Engine"
            SM --> TOK["Event Tokenizer\nalert → EVT_* token"]
            TOK --> SW["Smith-Waterman\nLocal Alignment\nmatch=4, mismatch=-1, gap=-1"]
            SW --> WCI["Wilson Score CI\n95% confidence\nstatsmodels"]
            WCI --> RISK["Risk Level\nLOW/MEDIUM/HIGH/CRITICAL"]
        end

        RISK --> OUT["risk_predictions.jsonl"]
        RISK --> WS_ANO["/ws/anomaly\nbroadcast to UI clients"]
        WS_ANO --> UI["monitor.html\nLive Dashboard"]
        REST_ANO["REST API\n/api/anomaly/status\n/api/anomaly/alerts\n/api/anomaly/buffer/stats\n/api/sequence/match/latest"] --> AH & BUFF
    end
```

### 5.3 Anomaly Detection Engine (`anomaly_detector.py`)

#### 5.3.1 Monitored Channels

Seven telemetry channels are monitored, each mapped to 1–2 drilling hazards:

| Channel (exact Volve column) | Direction | Hazards | Engineering Basis |
|------------------------------|-----------|---------|-------------------|
| `Corrected Total Hookload kkgf` | high | stuck_pipe | Elevated hookload = overpull (Maidla & Wojtanowicz 1990) |
| `Averaged WOB kkgf` | both | stuck_pipe, torque_spike | WOB spike = formation engagement; WOB drop = string not advancing |
| `Average Rotary Speed rpm` | low | torque_spike, stuck_pipe | RPM drop = friction/rotational stalling precursor |
| `Mud Density In g/cm3` | low | mud_loss, kick, overpressure | MW-in drop = influx / underbalance |
| `Mud Density Out g/cm3` | low | mud_loss, kick | MW-out < MW-in = gas-cut returns |
| `Mud Density In g/cm3.1` | low | mud_loss, overpressure | Secondary MW sensor cross-check |
| `ROPIH s/m` | high | stuck_pipe, overpressure | High seconds/metre = string not advancing normally |

#### 5.3.2 Z-Score Detector

```
μ_rolling = mean(buffer[-30:])
σ_rolling = std(buffer[-30:], ddof=1)
z = (current_value - μ_rolling) / σ_rolling

Alarm when:
  direction='high'  → z > +2.5σ
  direction='low'   → z < -2.5σ
  direction='both'  → |z| > 2.5σ

Severity: WARN(|z|≥2.5), ALERT(|z|≥3.0), CRITICAL(|z|≥4.0)
```

#### 5.3.3 CUSUM Detector

Detects **persistent slow drift** that individual Z-score checks miss:

```
k = 0.5σ  (allowance)
h = 5.0σ  (decision threshold)

S+_n = max(0, S+_{n-1} + (x_n - μ) - k)   [upward CUSUM]
S-_n = max(0, S-_{n-1} - (x_n - μ) - k)   [downward CUSUM]

Alarm when S+ > h (direction='high'/'both') or S- > h (direction='low'/'both')
State resets after alarm (self-resetting CUSUM)

Severity: WARN(ratio≥1.0), ALERT(ratio≥1.5), CRITICAL(ratio≥2.5)
  where ratio = cusum_accumulator / h
```

#### 5.3.4 AnomalyAlert Data Structure

```python
@dataclass
class AnomalyAlert:
    alert_id: str          # UUID4
    row_index: int         # position in replay
    measured_depth_m: float
    detector: str          # 'zscore' | 'cusum'
    channel: str           # exact Volve column name
    hazard: str            # one of 5 canonical hazards
    z_score: Optional[float]
    cusum_s_plus: Optional[float]
    cusum_s_minus: Optional[float]
    threshold_used: float
    direction: str         # 'high' | 'low'
    severity_label: str    # 'WARN' | 'ALERT' | 'CRITICAL'
    explanation: str       # human-readable with SPE citation
    rolling_mean: float
    rolling_std: float
    current_value: float
```

### 5.4 Sequence Matching Engine (`sequence_matcher.py`)

#### 5.4.1 Event Tokenization

Deterministic mapping from `(hazard, direction, severity_label)` to `event_type_id` from the canonical vocabulary. Examples:
- `stuck_pipe + high + CRITICAL` → `EVT_STUCK_PIPE`
- `stuck_pipe + high + ALERT` → `EVT_DIFF_STICKING`
- `stuck_pipe + high + WARN` → `EVT_TIGHT_HOLE`

#### 5.4.2 Smith-Waterman Local Alignment

Pure Python implementation (no Biopython). For each hazard:

```
Scoring:
  match (same token):       +4
  match (same hazard cat):  +2
  mismatch:                 -1
  gap penalty:              -1

Normalized score = raw_alignment_score / (SW_MATCH_SAME_TOKEN × min(len_query, len_hist))
Threshold: normalized_score > 2.0 → counts as "success" for Wilson CI
```

#### 5.4.3 Wilson Score Confidence Interval

```
n_trials    = number of top-K analog wells aligned
n_successes = count where normalized_alignment > threshold

Wilson CI (95%, statsmodels.stats.proportion.proportion_confint):
  center ∈ [ci_lower, ci_upper]

Risk level mapping:
  center ≥ 0.65 → CRITICAL
  center ≥ 0.45 → HIGH
  center ≥ 0.25 → MEDIUM
  else          → LOW
```

### 5.5 Time-Travel Backtest (`backtest_runner.py`)

The backtest replays the entire 16,670-row Volve telemetry in strict causal order (zero future-data leakage), running the full anomaly + sequence matching pipeline at every row:

- **Confirmed incident:** `NO_2014-02-05_EVT_STUCK_PIPE` at **619.0 m MD**
- **First actionable alarm:** at **512.52 m MD** (Wilson CI center ≥ 0.65)
- **Early warning lead:** **+106.48 m** (≈ 44 minutes at observed ROP)

**Deliverables produced:**
- `backtest_result.json` — Full numeric summary
- `backtest_plot.png` — Matplotlib risk timeline chart
- `risk_predictions.jsonl` — Per-row prediction log (read by Module 4 LLM)
- `sequence_matches.json` — Historical alignment records

### 5.6 Live WebSocket Protocol

**Simulator → Anomaly Server (`ws://5002 → 5003`):**
```json
{
  "well_id": "15/9-F-9A",
  "row_index": 5123,
  "total_rows": 16670,
  "delay_seconds": 0.2,
  "is_last_row": false,
  "telemetry": {
    "Measured Depth m": 512.52,
    "Corrected Total Hookload kkgf": 187.3,
    "Averaged WOB kkgf": 12.1
  }
}
```

**Anomaly Server → Browser (`/ws/anomaly`):**
```json
// Type 1: Alert event (on every anomaly)
{
  "type": "anomaly_alerts",
  "timestamp": "2026-09-10T03:00:00Z",
  "alerts": [{ "alert_id": "...", "detector": "cusum", "hazard": "stuck_pipe" }]
}

// Type 2: Sequence match result (every 25 rows)
{
  "type": "sequence_match",
  "results": [{ "hazard": "stuck_pipe", "risk_level": "HIGH", "wilson_ci": {} }]
}
```

---

## 6. Module 4 — Knowledge Graph, GraphRAG & AI Briefing Studio

### 6.1 Responsibility

Module 4 is the **knowledge synthesis and AI briefing layer**. It constructs a rich property graph from all Module 1, 2, and 3 outputs, provides an interactive Vis.js canvas, supports two-stage GraphRAG retrieval with AHP pre-filtering, and generates citation-enforced AI briefings via Google Gemini where every factual claim is auto-verified against a knowledge graph node.

### 6.2 Architecture

```mermaid
graph TD
    subgraph "Inputs from upstream modules"
        M1["wells_metadata.json\nevents.jsonl\nevent_type_vocabulary.json"]
        M2["analog_wells.json"]
        M3["risk_predictions.jsonl"]
    end

    subgraph "knowledge_graph.py — Part A"
        M1 & M2 --> KGB["build_graph\nNetworkX DiGraph"]
        KGB --> N_WELL["Well nodes × 159"]
        KGB --> N_FORM["Formation nodes × ~59"]
        KGB --> N_EVT["Event nodes × 1,959"]
        KGB --> N_SNIP["ReportSnippet nodes × 1,959"]
        KGB --> N_HAZ["Hazard nodes × 5"]
        KGB --> N_INT["Intervention nodes × 12"]
        KGB --> N_OUT["Outcome nodes × 5"]
        KGB --> EDGES["~12,392 edges\n8 relationship types"]
        KGB --> GPK["knowledge_graph.gpickle\n~1.6 MB pre-built"]
    end

    subgraph "graph_rag.py — Part B"
        GPK --> LOAD["load_graph\ncached in-memory"]
        LOAD --> STAGE1["Stage 1: AHP Pre-filter\nget top-K analog wells\nfrom analog_wells.json"]
        STAGE1 --> STAGE2["Stage 2: Semantic Index\ncollect ReportSnippets\nfrom analog subgraph"]
        STAGE2 --> EMBED["sentence-transformers\nall-MiniLM-L6-v2\ncosine similarity"]
        EMBED --> TOPK["Top-K results\nsorted by similarity"]
    end

    subgraph "llm_briefing.py — Part C"
        M3 --> RD["get_latest_risk_data\nread risk_predictions.jsonl"]
        TOPK --> PROMPT["_build_prompt\nforced-citation prompt\nIMMUTABLE risk values"]
        RD --> PROMPT
        PROMPT --> GEM["Google Gemini API\ngemini-1.5-flash"]
        GEM --> RAW["Raw LLM output\n4-6 citation sentences"]
        RAW --> PARSE["_parse_citations\nsentence → node_id pairs"]
        PARSE --> VERIFY["_verify_citation\nkeyword overlap check"]
        VERIFY --> BRF["Briefing JSON\nBRF_*.json\nper-sentence pass/fail"]
    end

    subgraph "app.py — Flask :5004"
        GPK --> APP["Flask Server"]
        TOPK --> APP
        BRF --> APP
        APP --> UI["module4.html\nVis.js canvas\nGraphRAG panel\nBriefing studio"]
    end
```

### 6.3 Knowledge Graph Structure

**Graph size:** ~4,037 nodes, ~12,392 edges (NetworkX DiGraph, serialized as `.gpickle`)

#### 6.3.1 Node Types

| Node Type | Count | Key Attributes |
|-----------|-------|----------------|
| `Well` | 159 | well_id, source, latitude, longitude, is_synthetic, total_depth_m, bha_type |
| `Event` | 1,959 | event_id, event_type_id, hazard, severity, depth_m, report_date, formation_id, confidence, is_synthetic |
| `ReportSnippet` | 1,959 | event_id, well_id, raw_text (≤2000 chars) |
| `Formation` | ~59 unique | formation_name |
| `Hazard` | 5 | hazard_id (mud_loss, stuck_pipe, overpressure, torque_spike, cementing) |
| `Intervention` | 12 | intervention_id, keywords (LCM_PILL, WEIGHTED_MUD, POOH, ...) |
| `Outcome` | 5 | OUT_RESOLVED, OUT_PARTIAL, OUT_UNRESOLVED, OUT_NPT, OUT_NONE |

#### 6.3.2 Edge Types and Ontology

```mermaid
graph LR
    WELL(("Well")) -->|"DRILLED_THROUGH"| FORM(("Formation"))
    WELL -->|"HAD_EVENT"| EVT(("Event"))
    EVT -->|"FOLLOWED_BY"| EVT2(("Next Event"))
    EVT -->|"MITIGATED_BY"| INT(("Intervention"))
    EVT -->|"LED_TO"| OUT(("Outcome"))
    EVT -->|"CLASSIFIED_AS"| HAZ(("Hazard"))
    EVT -->|"EXTRACTED_FROM"| SNIP(("ReportSnippet"))
    WELL -->|"ANALOG_FOR_HAZARD"| WELL2(("Analog Well"))
```

| Relation | Source → Target | Edge Attributes |
|----------|-----------------|-----------------|
| `DRILLED_THROUGH` | Well → Formation | depth_md_m |
| `HAD_EVENT` | Well → Event | depth_m |
| `FOLLOWED_BY` | Event → Event | depth_gap_m (depth-ordered within same well) |
| `MITIGATED_BY` | Event → Intervention | keyword-extracted from raw_text |
| `LED_TO` | Event → Outcome | text + severity driven |
| `CLASSIFIED_AS` | Event → Hazard | for the 5 canonical hazards |
| `ANALOG_FOR_HAZARD` | Well → Well | rank, weighted_score, feature_breakdown |
| `EXTRACTED_FROM` | Event → ReportSnippet | citation anchor |

### 6.4 GraphRAG Two-Stage Retrieval

The core novelty over plain vector similarity is **pre-filtering to an analog subgraph first**:

```mermaid
sequenceDiagram
    participant ENG as "Engineer (browser)"
    participant APP as "Module 4 API"
    participant RAG as "GraphRAG Engine"
    participant KG as "Knowledge Graph"
    participant M2 as "analog_wells.json"
    participant ST as "SentenceTransformer"

    ENG->>APP: GET /api/rag/query?well_id=X&hazard=Y&q=text
    APP->>RAG: rag.query(well_id, hazard, query_text)
    RAG->>M2: Stage 1: get_analog_well_ids(well_id, hazard)
    M2-->>RAG: top-10 AHP-ranked analog well IDs
    RAG->>KG: Stage 2: walk Well→Events→ReportSnippets for each analog
    KG-->>RAG: text snippets from analog subgraph only
    RAG->>ST: encode(snippets) + encode(query_text)
    ST-->>RAG: embeddings (all-MiniLM-L6-v2)
    RAG->>RAG: cosine similarity → top-K snippets
    RAG-->>APP: {analog_wells, results, retrieval_stats}
    APP-->>ENG: JSON response
```

> **Why this beats naive RAG:** Plain vector search over all 1,959 snippets ignores geological context. Stage 1 restricts the search corpus to only AHP-confirmed geospatially similar wells for that hazard, dramatically improving retrieval precision.

### 6.5 LLM Briefing Engine — Citation Enforcement

The Gemini briefing is governed by five hard rules:

1. **LLM never generates the risk score** — injected from `risk_predictions.jsonl` (Module 3) as immutable values
2. **Every factual sentence must cite a [NODE_ID]** from the knowledge graph
3. **Auto-verification pass** — every cited node_id is checked for keyword overlap with the sentence
4. **Failed citations are flagged** (not silently removed)
5. **Analog disagreement must be explicitly stated** if some analogs had the incident and others did not

```mermaid
flowchart LR
    M3_RISK["risk_predictions.jsonl\nIMMUTABLE risk values"] --> PROMPT
    RAG_RESULTS["GraphRAG top-K snippets\n+ analog well AHP scores"] --> PROMPT
    PROMPT["Build Prompt\n_build_prompt"] --> GEMINI["Gemini API\ngemini-1.5-flash"]
    GEMINI --> RAW_TEXT["Raw LLM output\n4-6 citation sentences"]
    RAW_TEXT --> PARSE["_parse_citations\nsentence → node_ids"]
    PARSE --> VERIFY{"_verify_citation\nkeyword overlap"}
    VERIFY -->|"pass"| PASS["✓ Verified sentence"]
    VERIFY -->|"fail"| FAIL["✗ Flagged sentence"]
    PASS & FAIL --> BRF["Briefing JSON\nBRF_YYYYMMDD_XXXXXX.json\nwith per-sentence audit trail"]
```

### 6.6 REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /` | GET | Serves Vis.js graph UI |
| `GET /api/graph/stats` | GET | Node/edge counts by type |
| `GET /api/graph/well/<well_id>` | GET | Balanced subgraph for a well (≤18 events) |
| `GET /api/wells` | GET | All wells for dropdown |
| `GET /api/rag/query` | GET | GraphRAG: `?well_id=&hazard=&q=` |
| `POST /api/briefing/generate` | POST | Generate Gemini briefing `{well_id, hazard, api_key}` |
| `GET /api/briefing/<id>` | GET | Retrieve saved briefing by ID |
| `GET /api/briefing/list` | GET | List all saved briefing IDs |
| `GET /api/backtest` | GET | Module 3 backtest result |
| `GET /api/graph/search` | GET | Search wells by substring |
| `GET /api/status` | GET | Service health check |

---

## 7. Module 5 — Engineering Decision Support Agent

### 7.1 Responsibility

Module 5 is the **evidence-grounded engineering decision support layer**. It provides a dark glassmorphic console where drilling engineers can pose natural language questions about ongoing drilling scenarios. It retrieves relevant historical evidence from a ChromaDB vector store (populated from Module 1 events), constrains retrieval to AHP-ranked analog wells from Module 2, and sends a structured prompt to Gemini 2.5 Flash. A complete offline fallback (Local Evidence Synthesis Engine) is built in for when no API key is available.

### 7.2 Internal Architecture

```mermaid
graph TD
    subgraph "Data Sources"
        M1E["events.jsonl\n1,959 events"]
        M1F["flagged_real_incidents.json"]
        M2A["analog_wells.json"]
    end

    subgraph "ingestion/data_adapter.py"
        M1E --> DA["DataAdapter\nload events + flagged incidents\n+ analog_wells at startup"]
        M1F --> DA
        M2A --> DA
        DA --> GET_ANALOGS["get_top_analog_wells\nwell_id × hazard → top-K IDs"]
    end

    subgraph "retrieval/ — VectorStore + Retriever"
        DA --> VS["VectorStore\nchromadb.PersistentClient\nnwis_events collection"]
        VS -->|"upsert at first launch"| CHROMA[("ChromaDB\nvector_store/chroma_db/\n~2,022 records")]
        GET_ANALOGS --> FILT["where_filter\nwell_id: $in analog_ids"]
        CHROMA --> SEARCH["collection.query\nquery_texts + where_filter\ntop_k=10"]
        FILT --> SEARCH
        SEARCH --> EV["EvidenceItem list\ncitation_id, raw_text, metadata"]
    end

    subgraph "agent/ — EngineeringAgent"
        EV --> AGT["agent.ask\nformat situation + sequence + evidence"]
        AGT --> PROMPT["build_context_prompt\nSituation / EventSequence / Evidence / Question"]
        PROMPT --> GEMINI["Gemini 2.5 Flash\ngoogle.genai.Client"]
        GEMINI -->|"success"| ANS["AskResponse\nanswer + citations + uncertainty"]
        GEMINI -->|"API error"| FALLBACK["Local Evidence Synthesis\nstructured markdown from EvidenceItems"]
        ANS & FALLBACK --> RESP["Final AskResponse"]
    end

    subgraph "app.py — Flask :5005"
        RESP --> API["POST /api/ask"]
        API --> UI["module5.html\nDark console\n5 preset scenarios"]
        SCEN["GET /api/scenarios"] --> UI
        HEALTH["GET /api/health"] --> COUNT["collection.count"]
    end
```

### 7.3 Request/Response Data Flow

```mermaid
sequenceDiagram
    participant ENG as "Engineer (browser)"
    participant APP as "Flask :5005"
    participant AGT as "EngineeringAgent"
    participant RET as "Retriever"
    participant DA as "DataAdapter"
    participant VS as "ChromaDB"
    participant GEM as "Gemini 2.5 Flash"

    ENG->>APP: POST /api/ask {question, current_situation, event_sequence}
    APP->>AGT: agent.ask(AskRequest)
    AGT->>RET: retrieve(question, situation)
    RET->>DA: get_top_analog_wells(well_id, hazard, top_k=5)
    DA-->>RET: [analog_well_ids]
    RET->>VS: search(query, where_filter={well_id: $in analog_ids}, top_k=10)
    VS-->>RET: [raw_results with docs + metadata]
    RET-->>AGT: (analog_wells, [EvidenceItem list])
    AGT->>GEM: generate_content(prompt + system_instruction)
    GEM-->>AGT: answer text
    AGT-->>APP: AskResponse
    APP-->>ENG: JSON {answer, historical_wells, citations, uncertainty, evidence[]}
```

### 7.4 Vector Store Population Strategy

At first launch, if the `nwis_events` ChromaDB collection is empty, the Retriever auto-populates it:

```
all_events = data_adapter.events + data_adapter.flagged_incidents
→ upsert into ChromaDB in batches of 100
→ each document = raw_text (or constructed summary if raw_text is missing/nan)
→ metadata = {well_id, depth_m, formation_id, event_type, hazard, severity, source}
→ ChromaDB uses its built-in embedding model for vector generation
→ IDs are unique per record: event_id + UUID suffix (ensures no collision on re-run)
```

### 7.5 System Prompt & Response Format

**System prompt enforces:**
- Only make claims supported by retrieved evidence
- Explicitly state uncertainty when evidence is insufficient
- Include citations using `[well_id - event_type - depth]` format
- Output structured format: **Situation / Historical Evidence / What happened next / Why / Relevant Interventions / Uncertainty / Evidence**

### 7.6 Five Pre-configured Demo Scenarios

| # | Title | Well | Hazard | Key Question |
|---|-------|------|--------|--------------|
| 1 | Shallow Stuck Pipe Warning | 15/9-F-9A | stuck_pipe | Probability of escalation + interventions? |
| 2 | Mud Loss in Reservoir | NO | mud_loss | Historical volume losses + regain methods? |
| 3 | Overpressure / Kick Detection | 15/9-F-14 | overpressure | Formation kick history + kill mud weights? |
| 4 | Severe Torque Spikes in Reactive Shale | 15/9-F-11 | torque_spike | Sweep/ream/mud change — what worked? |
| 5 | Exploratory Planning | 15/9-F-9A | none | Most common hazard + NPT in next 300 m? |

### 7.7 REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /` | GET | Serves dark console UI |
| `POST /api/ask` | POST | Main agent query endpoint |
| `GET /api/scenarios` | GET | All 5 preset demo scenarios |
| `GET /api/health` | GET | Health check + vector store record count |

---

## 8. Cross-Module Data Flow

### 8.1 Complete Data Dependency Graph

```mermaid
graph TD
    EXT_VOLVE["Volve WITSML\n15_9-F-9A.csv"] --> M1
    EXT_FORCE["FORCE 2020\nNPD Excel files"] --> M1
    EXT_DDR["Volve DDRs\nHuggingFace"] --> M1

    M1["Module 1\nData Foundation"] -->|"wells_metadata.json"| M2
    M1 -->|"events.jsonl"| M2
    M1 -->|"15_9-F-9A.csv telemetry"| M3_SIM
    M1 -->|"events.jsonl + vocabulary"| M4
    M1 -->|"wells_metadata.json"| M4
    M1 -->|"events.jsonl"| M5
    M1 -->|"flagged_real_incidents.json"| M5

    M2["Module 2\nAHP Engine"] -->|"analog_wells.json"| M3_SEQ["M3 Sequence Matcher"]
    M2 -->|"analog_wells.json"| M4["Module 4\nKnowledge Graph"]
    M2 -->|"analog_wells.json"| M5["Module 5\nAgent"]

    M3_SIM["M3 Simulator\n:5002"] -->|"WebSocket telemetry rows"| M3_ANO["M3 Anomaly Server\n:5003"]
    M3_ANO -->|"risk_predictions.jsonl"| M4
    M3_ANO -->|"backtest_result.json"| M4

    M4 -->|"GraphRAG results"| M4_LLM["M4 LLM Briefing"]
    M4_LLM -->|"BRF_*.json briefings"| M4_UI["M4 Browser UI"]
    M5 -->|"AskResponse"| M5_UI["M5 Browser UI"]
```

### 8.2 Module Startup Order

Module 3's Anomaly Server **must** start after the Simulator Server since it actively connects to port 5002's WebSocket:

```mermaid
sequenceDiagram
    participant ORC as "run_all_modules.py"
    participant M2 as "Module 2 :5001"
    participant SIM as "M3 Simulator :5002"
    participant ANO as "M3 Anomaly :5003"
    participant M4 as "Module 4 :5004"
    participant M5 as "Module 5 :5005"

    ORC->>M2: subprocess.Popen + 1.2s wait
    ORC->>SIM: subprocess.Popen + 1.2s wait
    Note over SIM: Loads 16,670 CSV rows into memory
    ORC->>ANO: subprocess.Popen + 1.2s wait
    Note over ANO: Connects to ws://5002/ws/telemetry
    SIM-->>ANO: WebSocket accepted
    ORC->>M4: subprocess.Popen + 1.2s wait
    Note over M4: Loads .gpickle graph into memory
    ORC->>M5: subprocess.Popen + 1.2s wait
    Note over M5: Populates ChromaDB if empty
    ORC->>ORC: supervisor loop (1s poll)
    ORC->>ORC: webbrowser.open (4 browser tabs)
```

### 8.3 Key Shared Data Contract — `analog_wells.json`

The `analog_wells.json` file is the **single most shared artifact**, consumed by Modules 3, 4, and 5:

```json
{
  "<target_well_id>": {
    "<hazard>": [
      {
        "well_id": "<analog_well_id>",
        "source": "real_force2020",
        "is_synthetic": false,
        "latitude": 56.12,
        "longitude": 2.45,
        "weighted_score": 0.7234,
        "feature_breakdown": {
          "formation_sim": 0.85,
          "mud_weight_sim": 0.72,
          "bha_sim": 0.60,
          "mud_type_sim": 0.55,
          "trajectory_sim": 0.78
        },
        "ahp_weights_used": {
          "formation": 0.4721,
          "mud_weight": 0.2634
        }
      }
    ]
  }
}
```

---

## 9. System Orchestration & Deployment

### 9.1 Master Orchestrator (`run_all_modules.py`)

The orchestrator is a **Python supervisor process** that:
1. Checks for port conflicts before launching
2. Starts each module as an independent `subprocess.Popen` with its own log file
3. Staggers starts by 1.2 seconds to allow socket binding
4. Monitors for unexpected exits with a 1-second poll loop
5. On `Ctrl+C`: gracefully terminates all child processes (`CTRL_BREAK_EVENT` on Windows)

```
Logs:
  logs/module2.log
  logs/module3_sim.log
  logs/module3_anomaly.log
  logs/module4.log
  logs/module5.log
```

### 9.2 Module Framework Choices

| Module | Framework | Why |
|--------|-----------|-----|
| Module 2 | Flask | Simple WSGI; data loaded at startup, all serving is fast in-memory |
| Module 3 Simulator | FastAPI + uvicorn | asyncio required for WebSocket broadcast loop |
| Module 3 Anomaly | FastAPI + uvicorn | asyncio required for simultaneous WebSocket consumer + broadcaster |
| Module 4 | Flask | Synchronous serving; graph is pre-loaded, RAG queries are fast |
| Module 5 | Flask | Simple WSGI; ChromaDB and Gemini calls are synchronous |

### 9.3 Offline Fallbacks

| Module | Scenario | Behavior |
|--------|----------|----------|
| Module 4 | No Gemini API key | Graph, search, and RAG features fully work; only "Generate Briefing" is blocked |
| Module 5 | API key missing or expired | Local Evidence Synthesis Engine activates: structured markdown synthesized directly from ChromaDB EvidenceItems |

### 9.4 Production Context

> In production (eRTMAC deployment at Oil India Limited), the Telemetry Simulator (port 5002) would be **replaced** by a direct WITSML/eRTMAC API subscriber. All downstream modules (Anomaly Server, Knowledge Graph, Agent) are designed to connect to any WebSocket that emits the same row envelope format.

---

## 10. Technology Stack Summary

| Category | Library/Tool | Used In |
|----------|-------------|---------|
| Web framework | `flask`, `flask-cors` | Modules 2, 4, 5 |
| Async web framework | `fastapi`, `uvicorn` | Module 3 (both servers) |
| WebSocket client | `websockets` | Module 3 Anomaly Server |
| Knowledge graph | `networkx` | Module 4 |
| Semantic embeddings | `sentence-transformers` (all-MiniLM-L6-v2) | Module 4 GraphRAG |
| Vector store | `chromadb` (PersistentClient) | Module 5 |
| Gemini AI | `google-generativeai` (Module 4), `google-genai` (Module 5) | Modules 4, 5 |
| Statistics | `scikit-learn`, `scipy`, `numpy`, `pandas` | Anomaly detection, AHP |
| Wilson CI | `statsmodels.stats.proportion` | Module 3 sequence matcher |
| Dynamic Time Warping | `fastdtw` | Module 2 trajectory similarity |
| Plotting | `matplotlib` | Module 3 backtest plot |
| Data validation | `pydantic` | Module 3 (FastAPI models), Module 5 (schemas) |
| Graph visualization | `vis-network.min.js` (bundled offline) | Module 4 UI |
| Map visualization | Leaflet.js (CDN) | Module 2 UI |

---

## 11. Data Schema Contracts

### 11.1 Telemetry Row Envelope (Module 3 WebSocket)

```json
{
  "well_id": "15/9-F-9A",
  "row_index": 5123,
  "total_rows": 16670,
  "delay_seconds": 0.2,
  "is_last_row": false,
  "telemetry": {
    "Measured Depth m": 512.52,
    "Corrected Total Hookload kkgf": 187.3,
    "Averaged WOB kkgf": 12.1,
    "Average Rotary Speed rpm": 95.4,
    "Mud Density In g/cm3": 1.24,
    "Mud Density Out g/cm3": 1.22,
    "Mud Density In g/cm3.1": 1.24,
    "ROPIH s/m": 8.4
  }
}
```

### 11.2 Risk Prediction Record (Module 3 → Module 4)

```json
{
  "timestamp": "2026-09-10T03:00:00Z",
  "well_id": "15/9-F-9A",
  "hazard": "stuck_pipe",
  "query_sequence": ["EVT_TIGHT_HOLE", "EVT_DIFF_STICKING"],
  "n_query_tokens": 2,
  "wilson_ci": {
    "lower": 0.35, "center": 0.52, "upper": 0.68,
    "n_trials": 10, "n_successes": 5,
    "method": "wilson", "alpha": 0.05
  },
  "risk_level": "HIGH",
  "actionable_threshold_crossed": false,
  "measured_depth_m": 512.52
}
```

### 11.3 Module 5 Ask Request/Response

```json
// POST /api/ask Request
{
  "question": "What is the probability this escalates to stuck pipe?",
  "current_situation": {
    "well_id": "15/9-F-9A",
    "depth": 303.5,
    "torque": 22.5, "wob": 110.0, "rop": 5.5,
    "flow": 420.0, "pressure": 310.0, "rpm": 90.0,
    "formation": "Unknown", "hazard": "stuck_pipe"
  },
  "event_sequence": ["EVT_ROUTINE_DRILLING", "EVT_TIGHT_HOLE", "EVT_TIGHT_HOLE"]
}

// Response
{
  "answer": "### Operational Assessment...\n...",
  "historical_wells": ["16/11-1 ST3", "7/3-1"],
  "citations": ["[16/11-1 ST3 - EVT_STUCK_PIPE - 619.0m]"],
  "uncertainty": "Low to Medium. Based on historical data...",
  "evidence": [
    {
      "well_id": "16/11-1 ST3",
      "depth": 619.0,
      "formation": "Hordaland",
      "hazard": "stuck_pipe",
      "event_type": "EVT_STUCK_PIPE",
      "raw_text": "Pipe stuck at 619m in Hordaland shale...",
      "citation_id": "[16/11-1 ST3 - EVT_STUCK_PIPE - 619.0m]"
    }
  ]
}
```

---

## Appendix: File Structure Reference

```
SIH_2026_PLANNS/
├── README.md
├── start_all.bat / start_all.ps1          ← Windows 1-click launchers
│
└── NLP/nlp_task_ddr/                       ← ALL code lives here
    ├── requirements.txt
    ├── run_all_modules.py                  ← Master orchestrator (5 processes)
    ├── p1_full_pipeline.py                 ← Module 1 offline pipeline
    ├── check_setup.py                      ← Data integrity verifier
    │
    ├── results/module1_outputs/            ← Module 1 artifacts (shared by all)
    │   ├── wells_metadata.json             ← 159 wells
    │   ├── events.jsonl                    ← 1,959 events (NDJSON)
    │   ├── event_type_vocabulary.json      ← 18 canonical event types
    │   ├── flagged_real_incidents.json     ← Real hazard events
    │   └── telemetry/15_9-F-9A.csv        ← 16,670 WITSML rows
    │
    ├── module2/                            ← Port 5001 (Flask)
    │   ├── app.py                          ← REST API + map server
    │   ├── compute_similarity.py           ← AHP + similarity engine (offline)
    │   ├── templates/map.html              ← Leaflet.js map UI
    │   └── outputs/
    │       ├── analog_wells.json           ← 159 × 5 hazards × ranked analogs
    │       ├── ahp_weights.json            ← AHP matrices + eigenvectors
    │       └── formation_correlation.json  ← 59 formations cross-referenced
    │
    ├── module3/                            ← Ports 5002 + 5003 (FastAPI)
    │   ├── telemetry_simulator.py          ← TelemetrySimulator class
    │   ├── simulator_server.py             ← FastAPI app :5002
    │   ├── anomaly_detector.py             ← AnomalyDetector (Z-score + CUSUM)
    │   ├── sequence_matcher.py             ← Smith-Waterman + Wilson CI
    │   ├── anomaly_server.py               ← FastAPI app :5003
    │   ├── backtest_runner.py              ← Time-travel backtest engine
    │   ├── monitor.html                    ← Live dashboard UI
    │   └── outputs/
    │       ├── backtest_result.json        ← +106.48 m early warning result
    │       ├── backtest_plot.png           ← Matplotlib risk timeline
    │       ├── risk_predictions.jsonl      ← Live per-row risk scores
    │       └── sequence_matches.json       ← Historical alignment records
    │
    ├── module4/                            ← Port 5004 (Flask)
    │   ├── knowledge_graph.py              ← NetworkX graph builder
    │   ├── graph_rag.py                    ← GraphRAG two-stage retrieval
    │   ├── llm_briefing.py                 ← Gemini citation-forced briefing
    │   ├── app.py                          ← Flask REST + UI server
    │   ├── templates/
    │   │   ├── module4.html                ← Vis.js graph UI
    │   │   └── vis-network.min.js          ← Bundled offline (no CDN)
    │   └── outputs/
    │       ├── knowledge_graph.gpickle     ← Pre-built ~1.6 MB graph
    │       ├── graph_stats.json            ← Node/edge counts
    │       └── BRF_*.json                  ← Generated AI briefings
    │
    └── module5_engineering_agent/          ← Port 5005 (Flask)
        ├── app.py                          ← Flask app + 5 demo scenarios
        ├── config.py                       ← Paths + Gemini + ChromaDB config
        ├── agent/
        │   ├── agent.py                    ← EngineeringAgent class
        │   └── prompts.py                  ← System prompt + context builder
        ├── retrieval/
        │   ├── retriever.py                ← Analog lookup + vector search
        │   └── vector_store.py             ← ChromaDB VectorStore wrapper
        ├── ingestion/
        │   └── data_adapter.py             ← M1/M2 data loader
        ├── schemas/
        │   └── models.py                   ← Pydantic data models
        ├── templates/module5.html          ← Dark console UI
        └── vector_store/chroma_db/         ← ChromaDB persistent storage
```

---

*Architecture document for eRTMAC-NWIS | SIH 2026 | PS SIH26121 | Oil India Limited*
*Based on actual implementation in `NLP/nlp_task_ddr/` — September 2026*
