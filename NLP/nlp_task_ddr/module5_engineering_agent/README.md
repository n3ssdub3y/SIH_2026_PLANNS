# Module 5: Engineering RAG + LLM Decision Support Agent
### NWIS-Sentinel | SIH 2026 | Problem Statement: SIH26121 | Oil India Limited

An evidence-grounded engineering decision-support console powered by Google Gemini and ChromaDB vector retrieval. It consumes structured offset well analog rankings and event histories from Modules 1–3 to assist drilling engineers with factual, cited advice during critical drilling operations.

---

## ⚡ Quick Start

### 1. Working Directory
```bash
# All commands are run from the module5 directory or the root
cd NLP/nlp_task_ddr/module5_engineering_agent
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
*(Dependencies: `flask`, `flask-cors`, `pydantic`, `chromadb`, `google-genai`, `google-generativeai`, `python-dotenv`, `requests`).*

### 3. Launch the Web Application (Port 5005)
```bash
python app.py
```
Open **[http://localhost:5005](http://localhost:5005)** in your browser.

> To run on a custom port:
> ```bash
> python app.py --port 5005
> ```

---

## 🖥️ User Interface Overview

The UI shares the exact dark glassmorphic design system as Modules 2, 3, and 4:
- **Left Console (Drilling Situation)**:
  - **Scenario Selection Panel**: Click `⚡ Select Scenario Panel` to open a full flyout panel with 1-click loading for all 5 pre-configured demo scenarios.
  - **Well & Geology Parameters**: Well ID, Depth (m), Formation name, and color-coded Hazard Focus selector pills.
  - **Telemetry Grid**: Two-column layout with Torque (kNm), WOB (kN), ROP (m/hr), RPM, Flow In (L/min), and Pressure (bar).
  - **Event Timeline**: Interactive chip builder where you can add/remove sequential event codes (e.g., `NORMAL`, `FLOW ANOMALY`).
  - **Analog Offset Wells**: Displays top-ranked analog wells retrieved dynamically from Module 2.
- **Right Console (Agent Chat Studio)**:
  - **Suggested Prompts**: 1-click pill buttons for standard operational queries.
  - **Structured Reasoning Stream**: Real-time response cards displaying uncertainty level (`LOW`, `MEDIUM`, `HIGH`).
  - **Verified Citations**: Structured badges (e.g. `[SYNTH-W12 - EVT_LCM_APPLIED - 2569.8m]`).
  - **Expandable Evidence Drawer**: Click `View Evidence Records` to review the exact raw offset well text retrieved from ChromaDB.

---

## 📋 Pre-Configured Demo Scenarios (from `demo_scenarios.txt`)

You can click any scenario from the `⚡ Select Scenario Panel` to auto-fill the entire dashboard:

1. **Scenario 1: Shallow Stuck Pipe Warning**
   - **Well**: `15/9-F-9A` | **Depth**: `303.5 m` | **Hazard**: `stuck_pipe`
   - **Timeline**: `EVT_ROUTINE_DRILLING, EVT_TIGHT_HOLE, EVT_TIGHT_HOLE, EVT_TIGHT_HOLE`
   - **Sample Question**: *"We are drilling the top hole section and experiencing repeated tight hole events with erratic torque. Based on historical data for this well and its top analogs, what is the probability this escalates into a stuck pipe event, and what successful interventions were recorded?"*

2. **Scenario 2: Mud Loss in Reservoir Section**
   - **Well**: `NO (Offset)` | **Depth**: `2651.0 m` | **Hazard**: `mud_loss`
   - **Timeline**: `NORMAL, FLOW ANOMALY, ROP DECREASE, PUMP PRESSURE DROP`
   - **Sample Question**: *"Flow out has dropped and pump pressure is decreasing while drilling through the Sandstone formation at 2651m. What historical evidence do we have for partial or total mud losses in this area, and how much volume was typically lost before circulation was regained?"*

3. **Scenario 3: Overpressure / Kick Detection**
   - **Well**: `15/9-F-14` | **Depth**: `3420.0 m` | **Hazard**: `overpressure`
   - **Timeline**: `EVT_ROUTINE_DRILLING, EVT_DRILLING_BREAK, EVT_FLOW_INCREASE`
   - **Sample Question**: *"We just hit a sudden drilling break at 3420m and the active pit volume is starting to increase. Do the historical analogs show kick events in this specific formation? If so, what mud weights were required to kill the well?"*

4. **Scenario 4: Severe Torque Spikes in Reactive Shale**
   - **Well**: `15/9-F-11` | **Depth**: `1850.0 m` | **Hazard**: `torque_spike`
   - **Timeline**: `EVT_ROUTINE_DRILLING, EVT_TORQUE_SPIKE, EVT_TORQUE_SPIKE, EVT_PACK_OFF_SYMPTOM`
   - **Sample Question**: *"We are seeing extreme torque spikes and symptoms of pack-off while drilling reactive shale at 1850m. Looking at the retrieved historical evidence, is this typically resolved by pumping a sweep, reaming, or altering the mud properties?"*

5. **Scenario 5: Exploratory Lookahead Planning**
   - **Well**: `15/9-F-9A` | **Depth**: `3150.0 m` | **Hazard**: `none`
   - **Sample Question**: *"We are planning the next 300 meters of this well. Based on the top analog wells, what is the most common hazard encountered in this depth range, and what is the typical Non-Productive Time (NPT) associated with it?"*

---

## 🔌 REST API Endpoints

The Flask server also exposes REST endpoints for programmatic access:

### 1. Health & Vector Store Check
```bash
curl http://localhost:5005/api/health
```
**Response:**
```json
{
  "events_in_store": 2022,
  "model": "gemini-2.5-flash",
  "service": "module5_engineering_agent",
  "status": "healthy"
}
```

### 2. List Demo Scenarios
```bash
curl http://localhost:5005/api/scenarios
```

### 3. Consult Agent
```bash
curl -X POST http://localhost:5005/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What happened during mud loss in offset wells?",
    "current_situation": {
      "well_id": "15/9-F-9A",
      "depth": 2830.0,
      "formation": "Sandstone",
      "hazard": "mud_loss",
      "torque": 18.0,
      "flow": 420.0
    },
    "event_sequence": ["NORMAL", "FLOW ANOMALY"]
  }'
```

---

## 🏗️ Architecture & Grounding

```
module5_engineering_agent/
├── app.py                     # Flask web server (serves UI & /api/ask)
├── templates/
│   └── module5.html           # Dark glassmorphic frontend
├── agent/
│   ├── agent.py               # EngineeringAgent with hybrid LLM/Local synthesis
│   └── prompts.py             # Rig-floor engineering system prompt
├── retrieval/
│   ├── retriever.py           # Top-K analog filtering + vector search
│   └── vector_store.py        # ChromaDB persistent collection wrapper
├── ingestion/
│   └── data_adapter.py        # Adapter loading Module 1 events & Module 2 analogs
├── schemas/
│   └── models.py              # Pydantic schemas (AskRequest, EvidenceItem, etc.)
└── vector_store/
    └── chroma_db/             # Pre-computed ChromaDB vector collection (2,022 events)
```

### Offline & Fallback Synthesis
If an external Gemini API key is missing or expires, the agent automatically falls back to its **Local Evidence Synthesis Engine**, extracting and compiling factual historical mitigation steps directly from the 2,022 indexed records so the application never breaks.

---

## 🛠️ Troubleshooting

- **Port 5005 already in use**:
  ```bash
  python app.py --port 5006
  ```
- **Verify vector database count**:
  Run `curl http://localhost:5005/api/health` and verify `"events_in_store": 2022`.
- **API Key Configuration**:
  To supply a custom Gemini key:
  ```bash
  export GEMINI_API_KEY="your-api-key"
  ```
