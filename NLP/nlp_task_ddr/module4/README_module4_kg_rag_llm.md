# README — Module 4: Knowledge Graph, GraphRAG & LLM Briefing
### NWIS-Sentinel | SIH 2026 | PS SIH26121

---

## What This Module Does (Plain Language)

Module 4 is the **intelligence layer** of NWIS-Sentinel. It connects all the data from Modules 1, 2, and 3 into a single searchable knowledge graph, then lets an engineer ask questions in plain English and get a Gemini AI-generated briefing that is **provably grounded** — every sentence links back to a specific historical report snippet that actually supports the claim.

Three things this module builds:

**Part A — Knowledge Graph**: Loads all 159 wells, 1,959 events, formations, interventions, and analog relationships into a NetworkX property graph with 7 node types and 7 edge types. Engineers can visually explore the graph to see how wells, events, and formations connect.

**Part B — GraphRAG**: When an engineer asks "what happened to similar wells before stuck pipe?", the system first narrows the search to only the wells Module 2 already identified as geophysically similar (using AHP scores), then does semantic similarity search *within that smaller set*. This pre-filter-then-retrieve design is the core novelty — it avoids the weaker approach of doing raw vector search over all 1,959 events blindly.

**Part C — LLM Briefing**: Takes the RAG evidence + Module 3's risk score and asks Gemini to write a 4-6 sentence briefing for the rig floor engineer. The risk score number is injected from Module 3 as an **immutable value** — the LLM cannot change it. Every sentence must cite a `[NODE_ID]` from the knowledge graph. An automatic verification pass then checks every cited node to confirm it actually supports the claim, and flags sentences that fail.

---

## Tech Stack

| Component | Library/Model | Why Chosen |
|---|---|---|
| Knowledge Graph | `networkx==3.6.1` | Standard, fast, in-memory property graph; pickle serialization for fast reload |
| Semantic Embeddings | `sentence-transformers==6.0.1` + `all-MiniLM-L6-v2` | 82MB, runs fully offline after first download, fastest model for semantic similarity |
| LLM Briefing | `google-generativeai` + `gemini-1.5-flash` | Gemini AI Studio API, fast + affordable, supports long context for evidence injection |
| Web Server | `Flask` + `flask-cors`, port 5004 | Consistent with Module 2 (5001/5002) and Module 3 (5003) architecture |
| UI | Vanilla HTML/CSS/JS + `vis-network` (CDN) | No build step, dark glassmorphism, interactive graph drag-and-drop |

---

## Input Files (All From Modules 1-3)

| File | Source | What We Use It For |
|---|---|---|
| `results/module1_outputs/wells_metadata.json` | Module 1 | 159 wells: lat/lon, formation tops, casing, BHA → Well + Formation nodes |
| `results/module1_outputs/events.jsonl` | Module 1 | 1,959 events with raw_text → Event + ReportSnippet nodes |
| `results/module1_outputs/event_type_vocabulary.json` | Module 1 | 18 canonical event type IDs |
| `results/module1_outputs/telemetry/15_9-F-9A.csv` | Module 1 | Real Volve MWD telemetry (used by Module 3 backtest, referenced here) |
| `module2/outputs/analog_wells.json` | Module 2 | 75MB AHP similarity rankings → ANALOG_FOR_HAZARD edges + GraphRAG pre-filter |
| `module2/outputs/ahp_weights.json` | Module 2 | AHP pairwise matrices (for auditability display) |
| `module3/outputs/risk_predictions.jsonl` | Module 3 | Live risk scores + Wilson CI → injected immutably into LLM prompt |
| `module3/outputs/backtest_result.json` | Module 3 | 106.48m lead time result displayed in UI sidebar |

---

## Output Files

| File | Path | Contents |
|---|---|---|
| `knowledge_graph.gpickle` | `module4/outputs/` | Serialized NetworkX DiGraph (fast reload on server start) |
| `graph_stats.json` | `module4/outputs/` | Node/edge counts by type |
| `BRF_<timestamp>_<id>.json` | `module4/outputs/` | Each generated LLM briefing with full citation verification log |

---

## Knowledge Graph Statistics (as built)

| Node Type | Count |
|---|---|
| Well | 159 |
| Formation | 59 |
| Event | 1,898 |
| Hazard | 5 |
| Intervention | 12 |
| Outcome | 5 |
| ReportSnippet | 1,898 |
| **TOTAL** | **4,037** |

| Edge Type | Count |
|---|---|
| DRILLED_THROUGH | 1,105 |
| HAD_EVENT | 1,898 |
| FOLLOWED_BY | 1,918 |
| MITIGATED_BY | 2,160 |
| LED_TO | 1,899 |
| ANALOG_FOR_HAZARD | 1,225 |
| EXTRACTED_FROM | 1,898 |
| CLASSIFIED_AS | 289 |
| **TOTAL** | **12,392** |

---

## How to Run

### Step 1 — Install dependencies (one time)
```bash
pip install networkx sentence-transformers google-generativeai flask flask-cors
```

### Step 2 — Start the server
```bash
cd NLP/nlp_task_ddr
python module4/app.py
```

### Step 3 — Open the UI
```
http://localhost:5004
```

> **Note**: The knowledge graph is built automatically on first run from the existing module outputs. The `sentence-transformers` model (`all-MiniLM-L6-v2`, ~82MB) is downloaded from Hugging Face on first RAG query and cached locally.

### Using the UI

1. **Select a well** from the left sidebar dropdown
2. **Select a hazard** (Mud Loss / Stuck Pipe / Overpressure / Torque Spike / Cementing)
3. **Click "Load Graph"** to see the well's knowledge graph subgraph in the centre panel
4. **Type a question** in the RAG Query panel (e.g. "tight hole precursor signs") and click **Search** — retrieves top evidence from offset wells
5. **Enter your Gemini API key** and click **Generate Briefing** — produces a citation-verified LLM briefing alongside Module 3's live risk score

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Module 4 web UI |
| GET | `/api/status` | Service health + endpoint list |
| GET | `/api/graph/stats` | Node/edge counts |
| GET | `/api/graph/well/<well_id>` | Well subgraph (2-hop neighbourhood) |
| GET | `/api/wells` | All 159 wells list |
| GET | `/api/rag/query?well_id=&hazard=&q=` | GraphRAG query |
| POST | `/api/briefing/generate` | Generate LLM briefing `{well_id, hazard, api_key}` |
| GET | `/api/briefing/<id>` | Retrieve saved briefing |
| GET | `/api/briefing/list` | List all saved briefings |
| GET | `/api/backtest` | Module 3 backtest result |

---

## Real vs Synthetic Data

| Category | Count | Type |
|---|---|---|
| FORCE 2020 wells | 118 | **REAL** — Norwegian Continental Shelf public dataset |
| Volve wells | 1 | **REAL** — Equinor public North Sea field data |
| Synthetic DDR wells | 40 | **SYNTHETIC** — LLM-generated, clearly labelled |
| **Total** | **159** | **75% real data** |

All `ReportSnippet` nodes carry `is_synthetic` flag inherited from the originating event — the UI can always distinguish real vs synthetic citations.

---

## Global Rule Compliance

| Rule | How This Module Complies |
|---|---|
| No hardcoding | All graph nodes/edges built from real data files at runtime |
| No silent API stubs | If Gemini key not provided, API returns explicit error asking for it |
| Full transparency | Every LLM sentence must cite `[NODE_ID]`; auto-verifier logs PASS/FAIL per sentence |
| LLM never generates risk scores | Risk score injected from Module 3 as immutable string in prompt; verified in code |
| Document your work | This README |

---

## Known Limitations

1. **Gemini API key required for Part C**: No key = no LLM briefing. RAG and graph still work without it.
2. **Graph is built from Module 1's text-extracted events** — the NLP entity extraction quality directly limits graph richness.
3. **82MB model download on first RAG query**: Requires internet on first run; cached after that.
4. **Citation verifier uses keyword overlap** — a sentence with zero keyword overlap to its cited node will fail. More sophisticated entailment checking would improve accuracy.
5. **Production would connect directly to eRTMAC WITSML feed** for live telemetry instead of replaying Module 3's static risk_predictions.jsonl.
