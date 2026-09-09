# Module 5: Engineering RAG + LLM Agent

An evidence-grounded engineering decision-support agent powered by Google Gemini and ChromaDB vector retrieval. It consumes structured analog well data and event histories from Modules 1–3 to assist drilling engineers with factual, cited advice during critical drilling operations.

---

## Architecture

- `schemas/`: Pydantic models for structured data (`CurrentSituation`, `AskRequest`, `AskResponse`, `EvidenceItem`).
- `ingestion/`: Data adapter loading Module 1 outputs (events, flagged incidents) and Module 2 outputs (analog wells).
- `retrieval/`: ChromaDB persistent vector store and hybrid retrieval engine with well-analog filtering.
- `agent/`: Google Gemini LLM integration with strict engineering evidence-grounding system prompts.
- `app.py`: Interactive Streamlit dashboard for real-time parameter entry and chat.
- `api_server.py`: FastAPI backend exposing the `/api/ask` endpoint for external programmatic access.

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
The agent includes a fallback default Gemini API key in `config.py`. To provide your own key:
```bash
# In .env or shell:
export GEMINI_API_KEY="your-gemini-api-key"
```

### 3. Run the Streamlit UI (Port 8501)
```bash
python -m streamlit run app.py
```
Open **[http://localhost:8501](http://localhost:8501)** in your browser.

### 4. Run the REST API Server (Port 8502, Optional)
```bash
python api_server.py
```
Health check:
```bash
curl http://localhost:8502/health
```

---

## Demo Scenarios

Pre-configured scenarios are available in `demo_scenarios.txt`:

1. **Shallow Stuck Pipe Warning**
   - Well: `15/9-F-9A` | Depth: `303.5 m` | Hazard: `stuck_pipe`
   - Timeline: `EVT_ROUTINE_DRILLING, EVT_TIGHT_HOLE, EVT_TIGHT_HOLE, EVT_TIGHT_HOLE`
   - Question: *"We are drilling the top hole section and experiencing repeated tight hole events with erratic torque. Based on historical data for this well and its top analogs, what is the probability this escalates into a stuck pipe event, and what successful interventions were recorded?"*

2. **Mud Loss in Reservoir Section**
   - Well: `15/9-F-9A` | Depth: `2651 m` | Hazard: `mud_loss`
   - Timeline: `NORMAL, FLOW ANOMALY, ROP DECREASE, PUMP PRESSURE DROP`
   - Question: *"Flow out has dropped and pump pressure is decreasing while drilling through the Sandstone formation at 2651m. What historical evidence do we have for partial or total mud losses in this area, and how much volume was typically lost before circulation was regained?"*

3. **Overpressure / Kick Detection**
   - Well: `15/9-F-14` | Depth: `3420 m` | Hazard: `overpressure`
   - Timeline: `EVT_ROUTINE_DRILLING, EVT_DRILLING_BREAK, EVT_FLOW_INCREASE`
   - Question: *"We just hit a sudden drilling break at 3420m and the active pit volume is starting to increase. Do the historical analogs show kick events in this specific formation? If so, what mud weights were required to kill the well?"*

---

## Citations and Verification
Every agent answer includes structured citations referencing specific offset wells, event types, and depths (e.g. `[SYNTH-W12 - EVT_LCM_APPLIED - 2569.8m]`). The UI provides an expandable **"View Evidence Used"** drawer to verify raw historical evidence.
