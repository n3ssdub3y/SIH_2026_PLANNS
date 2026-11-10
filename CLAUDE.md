# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

eRTMAC-NWIS (a.k.a. NWIS-Sentinel) — SIH 2026 prototype (PS SIH26121, Oil India Limited). Offset-well intelligence for drilling: DDR NLP extraction → AHP offset-well ranking → real-time telemetry anomaly detection → knowledge graph / GraphRAG → LLM decision agent. Built on Equinor Volve + FORCE 2020 data plus synthetic wells (`SYNTH-W*`).

Docs are split by concern — read the right one before large changes:
- `ARCHITECTURE.md` — source of truth for ports, runtime topology, API contracts, backtest mechanics.
- `PROJECT.md` — domain research, datasets, algorithm methodology (AHP, CUSUM, GraphRAG).
- `NWIS_PROJECT_SHOWCASE.md` — evaluator/demo narrative.

**Rule (`.agents/rules/architecture-update.md`, always on):** after any change affecting module responsibilities, data flow, APIs, ports, models, dependencies or runtime behavior, update `ARCHITECTURE.md` in place (revise stale sections, update Mermaid diagrams, distinguish implemented vs. simulated/planned). Don't document components that don't exist. Minor architecturally-relevant changes get a 1–2 line note.

## Commands

All real code lives in `NLP/nlp_task_ddr/`; run commands from there unless noted. Dependencies are in the **root** `requirements.txt` (Python 3.10/3.11).

```bash
pip install -r ../../requirements.txt
python check_setup.py                         # verify Module 1 data outputs are present
python gateway.py                             # start everything on :5000
python gateway.py --port 5000 --speed 5.0 --no-browser   # --speed = telemetry replay multiplier
```

Root launchers: `start_all.bat` / `start_all.ps1` (Windows), `start.sh` (devcontainer/Codespaces). All launchers and the devcontainer install from the root `requirements.txt` (there is none inside `NLP/nlp_task_ddr/`).

Tests (no pytest config; `pytest` is in the root `requirements.txt`; run from `NLP/nlp_task_ddr/`):
```bash
python -m pytest module3/ module4/                              # all unit tests
python -m pytest module3/test_leakage.py                        # zero-future-data-leakage regression suite
python -m pytest module3/test_sequence_matcher.py::TestWilsonCI # single class
python -m pytest module4/test_module4.py::test_graph_rag_retrieval
```
Module 3 tests are `unittest` (also runnable as `python module3/test_x.py`); Module 4 uses pytest and imports `module4.*`, so the cwd must be `NLP/nlp_task_ddr`. Root-level `test_api.py`, `test_page_load.py`, `test_slash_wellids.py` are smoke scripts that hit a **running** gateway (`python test_api.py [base_url]`).

Running a single module standalone: each accepts `--port`, e.g. `python module2/app.py --port 15001`, `python module3/simulator_server.py --port 15002 --speed 5`, `python module3/anomaly_server.py --port 15003 --simulator-url ws://localhost:15002/ws/telemetry`. `run_all_modules.py` is an older launcher using direct ports 5000–5005 without the gateway; prefer `gateway.py`.

## Architecture

### Single-port gateway
`gateway.py` (FastAPI) spawns every module as a subprocess (cwd = `NLP/nlp_task_ddr`, logs to `logs/<module>.log`) on internal ports and reverse-proxies HTTP + WebSocket through port 5000:

| Gateway path | Backend |
|---|---|
| `/` | `dashboard/templates/dashboard.html` (served directly) |
| `/module1`, `/module1/upload` | `module1/module1.html` — served directly; OCR is a **client-side simulation** |
| `/module2/*` | Module 2 Flask :15001 |
| `/module3/monitor`, `/module3/anomaly/*`, `/module3/outputs/*`, `WS /ws/anomaly` | Module 3 anomaly server (FastAPI) :15003 |
| `/module3/sim/*`, `WS /ws/telemetry` | Module 3 telemetry simulator (FastAPI) :15002 |
| `/module4/*` | Module 4 Flask :15004 |
| `/module5/*` | Module 5 Flask :15005 |
| `/api/*` | prefix-routed: `anomaly/`→15003, `telemetry/`→15002, `graph/` `rag/` `briefing/` `status` `backtest`→15004, everything else→Module 2 |
| `/gateway/health` | port check of all internals |

When adding a route or module, update `INTERNAL`, `start_all_modules()`, the proxy routes, and the `/api/*` prefix table together. Frontends must use gateway-relative URLs (`/module2/...`, `/ws/...`), not internal ports. Module 3's anomaly server loads a large JSON at startup (gateway waits up to 180 s for it).

### Data pipeline (offline, file-based contracts)
Modules communicate mostly through precomputed files, not APIs. Order of regeneration:

1. `p1_full_pipeline.py` → `results/module1_outputs/` (`wells_metadata.json`, `events.jsonl`, `event_type_vocabulary.json`, `flagged_real_incidents.json`, `telemetry/15_9-F-9A.csv`) from `../../datasets/`.
2. `module2/compute_similarity.py` → `module2/outputs/` (`analog_wells.json`, `ahp_weights.json`, `formation_correlation.json`).
3. `module3/backtest_runner.py` → `module3/outputs/` (`backtest_result.json`, `sequence_matches.json`, `backtest_plot.png`, and the committed `risk_predictions_backtest.jsonl`). `anomaly_server.py` separately writes the git-ignored `risk_predictions_live.jsonl` there (truncated on every start).
4. `module4/knowledge_graph.py` → `module4/outputs/knowledge_graph.gpickle` + `graph_stats.json`. `load_graph()` uses the pickle if present; rebuild after upstream data changes. Briefings are saved as `module4/outputs/BRF_*.json`.
5. Module 5 reads Module 1/2 outputs via `config.py` and a pre-built ChromaDB (collection `nwis_events`). The tracked `module5_engineering_agent/vector_store/chroma_db/` is a **read-only seed**; on first start it is copied to the git-ignored `data/runtime/chroma/`, which is what the app opens (delete that dir to reset).

Gotchas:
- `module3/outputs/` is the single Module 3 output location (the old `results/module3_outputs/` duplicate was removed). Module 4's `get_latest_risk_data()` reads `risk_predictions_live.jsonl` first and falls back to the committed `risk_predictions_backtest.jsonl`; both streams must keep the same record schema (`module3/test_risk_streams.py` enforces it).
- Running the system must not dirty tracked files: live risk data and the Chroma runtime copy are git-ignored. If `git status` shows `chroma.sqlite3` or a risk file modified after a run, something is writing to the wrong path.
- Path resolution is `Path(__file__)`-relative throughout; Module 4 inserts the project root on `sys.path` and imports `module4.*`, Module 3/5 insert their own directory.

### Module 3 causal-safety invariant
The headline result (+106.48 m early warning on 15/9-F-9A) depends on strict causality: detectors (Z-score + recursive CUSUM in `anomaly_detector.py`) and Smith-Waterman sequence matching with Wilson CIs (`sequence_matcher.py`) must only use data at or before the current row/depth, must exclude the target well from its own analog set, and must filter offset events deeper/later than the current point. `test_leakage.py` enforces this — run it after any change to Module 3.

### LLMs
- Module 4 briefings (`llm_briefing.py`): Gemini via `GEMINI_API_KEY` / `GOOGLE_API_KEY` (or key passed in the request); output sentences are verified against cited graph snippet nodes.
- Module 5 agent (`agent/agent.py`): fallback chain Qwen2.5-72B via Hugging Face (`HF_TOKEN`) → Gemini (`GEMINI_API_KEY`) → deterministic local evidence synthesis (works fully offline). All paths return the same schema with citations. Config/env loaded from `module5_engineering_agent/.env` via `config.py`.

### Other directories
- `NLP/nwis-sentinel/backend/` — early standalone FastAPI prototype with demo data; not launched by the gateway.
- `NLP/volve_*.py`, `extract_10_ddrs.py` — one-off data download/extraction scripts.
- `*.html.bak` files are stale template backups; edit the non-`.bak` versions.
