# README — Module 1: Data Foundation, OCR & NLP
## NWIS-Sentinel | SIH 2026 | PS SIH26121 — Oil India Limited

---

## What This Module Does
Module 1 is the data foundation layer for NWIS-Sentinel. It:
1. Acquires real public drilling data (Volve Field + FORCE 2020 — 118 NCS wells)
2. Generates a 200-report synthetic DDR corpus across 40 synthetic wells
3. Runs NLP entity extraction on all 1759 real DDRs
4. Normalises extracted events to a canonical versioned event vocabulary
5. Produces 6 structured output files consumed by Modules 2–4

---

## Tech Stack
| Component | Tool | Why |
|---|---|---|
| Data loading | pandas | Industry-standard tabular processing |
| NLP extraction | Python `re` (regex) | Fast, fully transparent, no black box |
| Event classification | Keyword → EVT lookup table | Every match is inspectable and auditable |
| Synthetic corpus | Template + controlled RNG (seed=42) | Reproducible, honest, explicitly tagged |
| Telemetry export | Raw Volve WITSML-origin CSV | Real drilling physics, not invented numbers |

---

## Dataset Scale & Transparency (Rule 3 Compliance)

| Dataset | Source | Type | Wells | Records |
|---|---|---|---|---|
| Volve DDRs | HuggingFace `bengsoon/volve_alpaca` | **REAL** | ~9 Volve wellbores | 1759 |
| FORCE 2020 Lithology | Zenodo #4351156 | **REAL** | 118 NCS wells | Formation tops |
| Synthetic DDR Corpus | Rule-based template + RNG | **SYNTHETIC** | 40 synthetic wells | 200 |
| Volve F-9A Telemetry | Equinor/Kaggle | **REAL** | 1 (F-9A) | 50,000 rows |

**Total: 159 wells | 1959 events | `is_synthetic` field is always set explicitly.**

---

## Step 1c — Real Historical Incident (Module 3 Backtest Seed)

**FOUND:**
- Well: `NO`
- Date: `1997-07-26`
- Event: `EVT_STUCK_PIPE`
- Hazard: `stuck_pipe`
- Snippet: _TIH with drilling BHA to 9 5/8" window. Corrected problem w/yellow pod tested bops. Attempted to drill-got stuck freed string. Unable to pass back through window. POOH PU milling BHA._

---

## Output Files (Module 2 consumes these directly)

| File | Description | Count |
|---|---|---|
| `wells_metadata.json` | Per-well: id, source, coords, formations, casing, is_synthetic flag | 159 wells |
| `events.jsonl` | Per-event: well_id, event_type_id, depth, formation, source, confidence, raw_text | 1959 events |
| `events_summary.csv` | Tabular view of all events (no raw_text) | 1959 rows |
| `event_type_vocabulary.json` | Canonical event vocab v1.0 — shared by all modules | 18 types |
| `telemetry/15_9-F-9A.csv` | Real Volve real-time drilling parameters | 50,000 rows |
| `flagged_real_incidents.json` | Real documented incidents flagged for Module 3 | 63 events |

---

## Known Limitations (Rule 4 Compliance)
- Volve DDR text is LLM-summarised alpaca format — depth/MW regex hits ~70% of records
- Synthetic wells carry no real GPS coordinates (always flagged `is_synthetic: true`)
- FORCE 2020 provides formation tops but no real-time telemetry for those 98 wells
- With more time + OIL India proprietary data: fine-tuned NER (spaCy / BERT) would replace regex

---

*Generated: 2026-09-07 18:17 | P1 Owner: Ness Dubey | Module handoff: Ready for P2*
