# README — Module 3: Real-Time Telemetry Simulation, Anomaly Detection, Sequence Matching & Flagship Historical Backtest
## NWIS-Sentinel | SIH 2026 | PS SIH26121 — Oil India Limited

---

### **FLAGSHIP RESULT: HISTORICAL TIME-TRAVEL BACKTEST**
> **In strict chronological/depth time-travel replay across 16,670 rows of real Volve MWD telemetry (`15_9-F-9A.csv`), NWIS-Sentinel Module 3 achieved an actionable early warning lead time of +106.48 metres (+44.07 minutes of direct telemetry stream lead time / +4.26 hours at standard drilling ROP) prior to the confirmed historical stuck pipe incident on Well 15/9-F-9A (`NO_2014-02-05_EVT_STUCK_PIPE` at 619.00 m MD), operating with verified zero future data leakage.** Initial critical precursor alerts began as early as 471.83 m MD (+147.17 m / +53.62 min lead time), successfully demonstrating that real-time sensor anomalies combined with analog sequence matching can preempt catastrophic drillstring sticking before irreversible mechanical lockup.

---

## 1. Executive Summary & What This Module Does
Module 3 is the predictive intelligence engine of NWIS-Sentinel. It bridges the gap between historical offset well knowledge (from Module 1 NLP and Module 2 Geospatial AHP) and live rig-floor sensor streams.

It executes five integrated operational steps:
1. **Live Telemetry Replay Engine (Step 1)**: Streams 15 high-frequency drilling telemetry channels (Hookload, WOB, RPM, Mud Density, ROP, TVD, Hole Depth) over WebSockets and REST APIs, preserving WITSML data integrity and engineering units.
2. **Precursor / Anomaly Detection Engine (Step 2)**: Analyzes the causal rolling buffer using dual transparent physical detectors: Rolling Z-Score ($|z| \ge 2.5\sigma$) and self-resetting CUSUM control charts ($h = 5.0\sigma, k = 0.5\sigma$). Monitors 5 key drilling hazards: `stuck_pipe`, `torque_spike`, `mud_loss`, `kick`, and `overpressure`.
3. **Event Tokenization & Sequence Alignment (Step 3)**: Discretizes live anomaly bursts into canonical event tokens (from `event_type_vocabulary.json`) and runs Smith-Waterman local alignment against the top-K offset analog wells identified by Module 2. Quantifies hazard probability with 95% Wilson Score Confidence Intervals via `statsmodels` (never bare numbers).
4. **Flagship Historical Time-Travel Backtest (Step 4)**: Causal replay of the real Volve Well 15/9-F-9A telemetry stream up to the confirmed operational stuck tool incident at 619.0 m MD. Formulates and plots the actionable lead-time delta (+106.48 m / +44.07 min).
5. **Exact Standardized Deliverables (Step 5)**: Produces the 4 core deliverables for Module 4 (Unified Dashboard): `backtest_result.json`, `backtest_plot.png`, `risk_predictions.jsonl`, and `sequence_matches.json`.

---

## 2. Tech Stack & Justification

| Component | Library / Technology | Version / Tool | Engineering Rationale |
|---|---|---|---|
| **Real-Time Streaming** | FastAPI & WebSockets | FastAPI 0.115+, websockets | High-throughput asynchronous broadcasting (sub-millisecond latency for rig-floor feeds). |
| **Statistical Detection** | NumPy & SciPy | NumPy 1.26+ | Fast, vectorized rolling window means, sample standard deviations, and CUSUM accumulators. |
| **Sequence Alignment** | Smith-Waterman Dynamic Programming | Pure Python (matrix-backed) | Transparent local alignment (no external black-box genomic libraries); custom scoring matrix (+4 match, +2 same-hazard, -1 mismatch, -1 gap). |
| **Proportion CI** | statsmodels | `statsmodels.stats.proportion.proportion_confint` | Wilson Score confidence interval formulation (Wilson 1927) providing rigorous binomial parameter bounds even on small sample sizes ($N=10$ offset wells). |
| **Data Handling** | pandas | pandas 2.2+ | Tabular ingestion, monotonic depth validation, and cleaning. |
| **Visualization** | Matplotlib | Matplotlib 3.8+ (Agg backend) | Publication-grade dual-tier dark-slate backtest chart (`backtest_plot.png`) at 300 DPI. |
| **Verification Suite** | unittest | Python standard library | Causal invariance and zero-leakage regression test suite (`test_leakage.py`). |

---

## 3. Strict Causality & Zero Future Data Leakage Audit

A core requirement of PS SIH26121 is that the backtest must be **provably leakage-free**:
- **Causal Invariance**: At any replay index $t$ (depth $D_t$), the system is physically isolated from all data at $t+1 \dots N$. Rolling means $\mu_t$ and sample standard deviations $\sigma_t$ use only the causal window $[t-W+1, t]$.
- **Recursive State Causality**: The CUSUM accumulators $S_t^+ = \max(0, S_{t-1}^+ + (x_t - \mu_t) - k_t)$ depend only on historical state $S_{t-1}^+$ and current observation $x_t$.
- **No Target Well Self-Matching**: When evaluating Well `15/9-F-9A`, the well itself (and its aliases `15_9-F-9A`, `NO`) is strictly excluded from the offset analog candidate set (`exclude_target=True`). An incident can never be matched against itself or its own future.
- **Historical Event Depth Filtering**: Offset well historical events are restricted strictly to completed historical records prior to the current drilling operation.
- **Automated Verification**: Passed all 5 tests in `test_leakage.py` (`Ran 5 tests in 7.28s, OK`).

---

## 4. Input Files & Schema Consumed

| Input File | Source | Description | Schema / Key Fields |
|---|---|---|---|
| `results/module1_outputs/telemetry/15_9-F-9A.csv` | Module 1 (Real Volve) | 16,670 rows of 15-channel MWD drilling telemetry. | `Measured Depth m`, `Average Rotary Speed rpm`, `Corrected Total Hookload kkgf`, `Averaged WOB kkgf`, `Mud Density In g/cm3`, etc. |
| `results/module1_outputs/flagged_real_incidents.json` | Module 1 (Real Volve) | 63 verified historical drilling incidents. | `event_id`, `well_id`, `report_date`, `depth_m`, `hazard`, `raw_text`. |
| `results/module1_outputs/event_type_vocabulary.json` | Module 1 | Canonical vocabulary of 18 drilling event states. | `event_types` -> `{token: {hazard, severity_default, description}}`. |
| `results/module1_outputs/events.jsonl` | Module 1 | 1,959 extracted event tokens across 41 wells. | `well_id`, `event_id`, `depth_m`, `event_type_id`, `hazard`, `report_date`. |
| `module2/outputs/analog_wells.json` | Module 2 | AHP geospatial & formation similarity rankings. | `{target_well_id: {hazard: [{well_id, weighted_score, ...}]}}`. |

---

## 5. Output Files & Standardized Schemas Produced

All four primary deliverables are written to `module3/outputs/` and mirrored to `results/module3_outputs/`:

### 1. `backtest_result.json`
Comprehensive metadata summarizing the historical time-travel backtest:
```json
{
  "summary": {
    "flagship_deliverable": "Historical Time-Travel Backtest (Module 3 Step 4)",
    "well_id": "15/9-F-9A",
    "field": "Volve Field (North Sea)",
    "incident_event_id": "NO_2014-02-05_EVT_STUCK_PIPE",
    "incident_hazard": "stuck_pipe",
    "incident_depth_m": 619.0,
    "lead_time_metrics": {
      "actionable_lead_distance_metres": 106.48,
      "actionable_lead_time_minutes_telemetry": 44.07,
      "actionable_lead_time_hours_at_25m_hr_rop": 4.26,
      "precursor_initial_lead_distance_metres": 147.17,
      "precursor_initial_lead_time_minutes": 53.62
    },
    "system_decision": "PIPE STICKING RISK MITIGATED — Actionable alert provided 106.27 m (44.0 min) prior to pipe lockup."
  }
}
```

### 2. `backtest_plot.png`
High-resolution (300 DPI, $3633 \times 2401$ px) publication-ready presentation graphic:
- **Top Panel**: Real Hookload curve (cyan) vs. Rotary Speed RPM (amber) across the key operational depth window ($350\text{ m} - 750\text{ m}$), showing clear rotary stalling and hookload overpull preceding the incident.
- **Actionable Warning Zone**: Shaded green region spanning from the first actionable alert ($512.52\text{ m}$) to the real incident ($619.00\text{ m}$).
- **Annotated Callout**: Highlighted box displaying Lead Distance ($+106.5\text{ m}$), Telemetry Lead ($+44.1\text{ min}$), and Operational Lead ($+4.26\text{ hrs}$ at $25\text{ m/h}$ ROP).
- **Bottom Panel**: Dynamic Wilson 95% Confidence Interval band ($[0.49, 0.94]$) and predicted risk score ($0.80$ CRITICAL) aligned with advisory and actionable threshold lines.

### 3. `risk_predictions.jsonl`
Line-delimited JSON log of live risk predictions evaluated at each depth interval. Every line contains full feature breakdowns and Wilson confidence intervals (no bare numbers):
```json
{
  "timestamp": "2026-09-08T18:03:22.254101+00:00",
  "well_id": "15/9-F-9A",
  "measured_depth_m": 512.521,
  "row_index": 2019,
  "hazard": "stuck_pipe",
  "risk_level": "CRITICAL",
  "risk_score": 0.8,
  "wilson_ci": {
    "lower": 0.4902,
    "center": 0.8,
    "upper": 0.9433,
    "n_trials": 10,
    "n_successes": 8,
    "method": "wilson",
    "alpha": 0.05
  },
  "feature_weights_and_breakdown": {
    "n_trials": 10,
    "n_successes": 8,
    "alignment_threshold": 0.2,
    "top_analog_feature_weights": [
      {"analog_well_id": "SYNTH-W09", "ahp_similarity_weight": 0.9438, "smith_waterman_normalized": 0.5},
      {"analog_well_id": "SYNTH-W10", "ahp_similarity_weight": 0.9438, "smith_waterman_normalized": 0.25}
    ]
  },
  "actionable_threshold_crossed": true,
  "explanation": "Query sequence for hazard 'stuck_pipe': ['EVT_TIGHT_HOLE', ...]. Evaluated against 10 top analog offset wells from Module 2 (excluding target well). 8/10 analogs produced an alignment score above threshold. Wilson 95% CI: [0.49, 0.94], point estimate: 0.80. Risk level: CRITICAL."
}
```

### 4. `sequence_matches.json`
Static export of all historical offset analog matches, local alignment segments, and normalized scores per hazard.

---

## 6. Real vs. Synthetic Data Breakdown (Rule 3 Compliance)

| Component | Dataset / Item | Real vs. Synthetic | Details / Transparency |
|---|---|---|---|
| **Telemetry Stream** | `15_9-F-9A.csv` | **100% REAL** | Public Equinor Volve Field high-frequency WITSML drilling telemetry (Well 15/9-F-9A). 16,670 rows, real sensor physics. |
| **Historical Incident** | `NO_2014-02-05_EVT_STUCK_PIPE` | **100% REAL** | Verified real operational stuck tool incident documented in Norwegian Volve field Daily Drilling Reports at 619.0 m MD. |
| **Analog Well Weights** | `analog_wells.json` | **HYBRID** | Real Volve wells + systematically parameterized synthetic offset wells from Module 2. |
| **Historical Event Tokens**| `events.jsonl` | **HYBRID** | Real NLP extractions from Volve reports + controlled synthetic report corpus (all synthetic records tagged `is_synthetic: true`). |
| **Anomaly Detection Math** | Z-score & CUSUM | **100% REAL MATH** | Exact deterministic statistical formulas derived from causal telemetry buffer. |
| **Wilson Confidence CI** | statsmodels | **100% REAL MATH** | Standard Wilson score binomial interval computation. Zero hardcoding. |

---

## 7. How to Run the Live System

### A. Run the Flagship Backtest (Offline Batch Mode)
Executes the full time-travel simulation, generates all plots, and updates all JSON/JSONL deliverables:
```powershell
python module3/backtest_runner.py
```

### B. Run the Zero-Leakage Test Suite
Executes the causal verification and regression test suite:
```powershell
python -m unittest module3/test_leakage.py -v
```

### C. Run the Live Telemetry Simulator & Anomaly Server (Real-Time Mode)
1. **Start Step 1 Simulator Server (Port 5002)**:
   ```powershell
   python module3/simulator_server.py --port 5002 --speed 5.0
   ```
   - WebSocket Feed: `ws://localhost:5002/ws/telemetry`
   - REST Status: `http://localhost:5002/api/telemetry/status`

2. **Start Step 2+3 Anomaly & Prediction Server (Port 5003)**:
   ```powershell
   python module3/anomaly_server.py --port 5003 --simulator-url ws://localhost:5002/ws/telemetry
   ```
   - Live Anomaly Feed: `ws://localhost:5003/ws/anomaly`
   - Real-Time Monitor Web UI: Open `module3/monitor.html` directly in any web browser.

---

## 8. Known Limitations & Future Enhancements for Oil India Limited (OIL)
1. **Direct WITSML / OPC-UA Ingestion**: In production at OIL's eRTMAC (Real-Time Monitoring and Advisory Centre), the simulator layer would be replaced with a live WITSML 1.4 / 2.0 SOAP/XML or OPC-UA connector.
2. **Channel Sparsity Handling**: In the public Volve dataset, certain channels (such as ROP and Mud Density Out) are sampled intermittently. While the CUSUM and Z-score engines gracefully handle `None` entries by filtering valid observations, higher-frequency mud flow out sensors on modern rigs would enable even earlier kick/loss detection.
3. **Multi-Well Parallel Replay**: The architecture currently backtests one wellbore at a time. For full enterprise field-scale deployment, the engine can be orchestrated via Celery or Ray to monitor 10+ active drilling rigs simultaneously.
