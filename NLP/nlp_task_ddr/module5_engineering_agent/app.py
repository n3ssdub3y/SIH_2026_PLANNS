"""
app.py — Module 5: Engineering RAG + LLM Agent Web Application
NWIS-Sentinel | SIH 2026 | PS SIH26121

Serves:
  GET  /              -> Modern dark glassmorphic engineering console (module5.html)
  POST /api/ask       -> Query EngineeringAgent with structured situation & question
  GET  /api/scenarios -> List pre-configured demo scenarios
  GET  /api/health    -> Health and vector store readiness status

Usage:
  python app.py [--port 5005]
  Open: http://localhost:5005
"""
from __future__ import annotations
import sys
import os
from pathlib import Path
import argparse
import logging
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# Add module5 directory to sys.path
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))

from agent.agent import EngineeringAgent
from schemas.models import AskRequest, CurrentSituation
from config import API_PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("module5_app")

app = Flask(__name__, template_folder="templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True
CORS(app)

# Initialize Agent and Retriever once at startup
logger.info("Initializing EngineeringAgent (ChromaDB + Gemini)...")
agent = EngineeringAgent()
logger.info("EngineeringAgent initialized successfully.")

# ── Demo Scenarios ─────────────────────────────────────────────────────────────
SCENARIOS = {
    "1": {
        "id": "1",
        "title": "Scenario 1: Shallow Stuck Pipe Warning (15/9-F-9A)",
        "well_id": "15/9-F-9A",
        "depth": 303.50,
        "torque": 22.50,
        "wob": 110.00,
        "rop": 5.50,
        "flow": 420.00,
        "pressure": 310.00,
        "rpm": 90.00,
        "formation": "Unknown",
        "hazard": "stuck_pipe",
        "timeline": ["EVT_ROUTINE_DRILLING", "EVT_TIGHT_HOLE", "EVT_TIGHT_HOLE", "EVT_TIGHT_HOLE"],
        "question": "We are drilling the top hole section and experiencing repeated tight hole events with erratic torque. Based on historical data for this well and its top analogs, what is the probability this escalates into a stuck pipe event, and what successful interventions were recorded?"
    },
    "2": {
        "id": "2",
        "title": "Scenario 2: Mud Loss in Reservoir Section (NO)",
        "well_id": "NO",
        "depth": 2651.00,
        "torque": 15.00,
        "wob": 130.00,
        "rop": 25.00,
        "flow": 250.00,
        "pressure": 180.00,
        "rpm": 110.00,
        "formation": "Sandstone",
        "hazard": "mud_loss",
        "timeline": ["NORMAL", "FLOW ANOMALY", "ROP DECREASE", "PUMP PRESSURE DROP"],
        "question": "Flow out has dropped and pump pressure is decreasing while drilling through the Sandstone formation at 2651m. What historical evidence do we have for partial or total mud losses in this area, and how much volume was typically lost before circulation was regained?"
    },
    "3": {
        "id": "3",
        "title": "Scenario 3: Overpressure / Kick Detection (15/9-F-14)",
        "well_id": "15/9-F-14",
        "depth": 3420.00,
        "torque": 20.00,
        "wob": 150.00,
        "rop": 35.00,
        "flow": 460.00,
        "pressure": 350.00,
        "rpm": 120.00,
        "formation": "Hugin Fm.",
        "hazard": "overpressure",
        "timeline": ["EVT_ROUTINE_DRILLING", "EVT_DRILLING_BREAK", "EVT_FLOW_INCREASE"],
        "question": "We just hit a sudden drilling break at 3420m and the active pit volume is starting to increase. Do the historical analogs show kick events in this specific formation? If so, what mud weights were required to kill the well?"
    },
    "4": {
        "id": "4",
        "title": "Scenario 4: Severe Torque Spikes in Reactive Shale (15/9-F-11)",
        "well_id": "15/9-F-11",
        "depth": 1850.00,
        "torque": 35.00,
        "wob": 90.00,
        "rop": 4.00,
        "flow": 400.00,
        "pressure": 280.00,
        "rpm": 80.00,
        "formation": "Lista Fm. (Reactive Shale)",
        "hazard": "torque_spike",
        "timeline": ["EVT_ROUTINE_DRILLING", "EVT_TORQUE_SPIKE", "EVT_TORQUE_SPIKE", "EVT_PACK_OFF_SYMPTOM"],
        "question": "We are seeing extreme torque spikes and symptoms of pack-off while drilling reactive shale at 1850m. Looking at the retrieved historical evidence, is this typically resolved by pumping a sweep, reaming, or altering the mud properties?"
    },
    "5": {
        "id": "5",
        "title": "Scenario 5: Exploratory Planning Question (15/9-F-9A)",
        "well_id": "15/9-F-9A",
        "depth": 3150.00,
        "torque": 18.00,
        "wob": 120.00,
        "rop": 8.00,
        "flow": 420.00,
        "pressure": 310.00,
        "rpm": 90.00,
        "formation": "Limestone",
        "hazard": "none",
        "timeline": [],
        "question": "We are planning the next 300 meters of this well. Based on the top analog wells, what is the most common hazard encountered in this depth range, and what is the typical Non-Productive Time (NPT) associated with it?"
    }
}

# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("module5.html")

@app.route("/api/health", methods=["GET"])
def health():
    try:
        count = agent.retriever.vector_store.collection.count()
    except Exception:
        count = "available"
    return jsonify({
        "status": "healthy",
        "service": "module5_engineering_agent",
        "model": "gemini-2.5-flash",
        "events_in_store": count
    })

@app.route("/api/scenarios", methods=["GET"])
def get_scenarios():
    return jsonify(SCENARIOS)

@app.route("/api/ask", methods=["POST"])
def ask():
    body = request.get_json(force=True) or {}
    question = body.get("question")
    if not question:
        return jsonify({"detail": "Field 'question' is required."}), 400

    sit_data = body.get("current_situation") or {}
    sit = CurrentSituation(
        well_id=sit_data.get("well_id"),
        depth=sit_data.get("depth"),
        torque=sit_data.get("torque"),
        wob=sit_data.get("wob"),
        rop=sit_data.get("rop"),
        flow=sit_data.get("flow"),
        pressure=sit_data.get("pressure"),
        rpm=sit_data.get("rpm"),
        formation=sit_data.get("formation"),
        hazard=sit_data.get("hazard")
    )
    timeline = body.get("event_sequence") or []

    req = AskRequest(
        question=question,
        current_situation=sit,
        event_sequence=timeline
    )

    try:
        resp = agent.ask(req)
        return jsonify({
            "answer": resp.answer,
            "historical_wells": resp.historical_wells,
            "citations": resp.citations,
            "uncertainty": resp.uncertainty,
            "evidence": [e.model_dump() for e in resp.evidence]
        })
    except Exception as e:
        logger.error(f"Error querying agent: {e}", exc_info=True)
        return jsonify({"detail": str(e)}), 500

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Module 5: Engineering RAG + LLM Agent")
    parser.add_argument("--port", type=int, default=5005, help="Port to listen on (default: 5005)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f"  NWIS-Sentinel | Module 5: Engineering Agent")
    print(f"  URL: http://localhost:{args.port}")
    print(f"=======================================================\n")
    app.run(host=args.host, port=args.port, debug=False)
