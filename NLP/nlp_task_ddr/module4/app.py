"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 4: Flask App — Knowledge Graph + GraphRAG + LLM Briefing
Port: 5004

Endpoints:
  GET  /                              → Module 4 web UI
  GET  /api/graph/stats               → Node/edge count summary
  GET  /api/graph/well/<well_id>      → Subgraph for a specific well
  GET  /api/wells                     → List all wells (for dropdown)
  GET  /api/rag/query                 → GraphRAG: ?well_id=&hazard=&q=<text>
  POST /api/briefing/generate         → Generate LLM briefing {well_id, hazard, api_key?}
  GET  /api/briefing/<briefing_id>    → Retrieve saved briefing by ID
  GET  /api/briefing/list             → List all saved briefings
  GET  /api/backtest                  → Module 3 backtest result (for display)

Usage:
    python module4/app.py
    Open: http://localhost:5004
"""

import json
import logging
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Ensure project root is on sys.path so `from module4.xxx import` works
_MODULE4_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE4_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from module4.knowledge_graph import load_graph, get_well_subgraph, get_graph_stats
from module4.graph_rag import GraphRAG
from module4.llm_briefing import LLMBriefing, get_latest_risk_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("module4_app")

# ── Paths ──────────────────────────────────────────────────────────────────────
MODULE1_DIR  = _PROJECT_ROOT / "results" / "module1_outputs"
MODULE3_DIR  = _PROJECT_ROOT / "module3" / "outputs"
TEMPLATES_DIR = _MODULE4_DIR / "templates"
OUTPUTS_DIR   = _MODULE4_DIR / "outputs"

WELLS_META_PATH   = MODULE1_DIR / "wells_metadata.json"
BACKTEST_PATH     = MODULE3_DIR / "backtest_result.json"

# ── Global state (loaded once at startup) ─────────────────────────────────────
_graph   = None
_rag     = None
_wells_list = None  # cached list of well IDs + metadata

# LLM briefing instance — API key set per-request or from env
_briefing_instances: dict = {}

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(TEMPLATES_DIR),  # serve static files from templates dir
)
CORS(app)

# ── Startup ────────────────────────────────────────────────────────────────────
def startup():
    global _graph, _rag, _wells_list
    logger.info("=" * 70)
    logger.info("NWIS-Sentinel Module 4 — Knowledge Graph + GraphRAG + LLM Briefing")
    logger.info("=" * 70)

    logger.info("Loading knowledge graph ...")
    _graph = load_graph()
    logger.info("  Graph ready: %d nodes, %d edges.", _graph.number_of_nodes(), _graph.number_of_edges())

    logger.info("Initialising GraphRAG engine ...")
    _rag = GraphRAG(graph=_graph)
    logger.info("  GraphRAG ready (sentence-transformer loads on first query).")

    logger.info("Loading wells list ...")
    with open(WELLS_META_PATH, encoding="utf-8") as f:
        _wells_list = json.load(f)
    logger.info("  %d wells available.", len(_wells_list))

    logger.info("Module 4 ready -> http://localhost:5004")
    logger.info("=" * 70)


@app.before_request
def ensure_started():
    """Ensure graph and models are loaded even if not launched via __main__."""
    global _graph
    if _graph is None:
        startup()


# ── API endpoints ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the Module 4 HTML UI."""
    return send_from_directory(str(TEMPLATES_DIR), "module4.html")


@app.route("/vis-network.min.js")
def vis_network_js():
    """Serve local vis-network bundle offline."""
    return send_from_directory(str(TEMPLATES_DIR), "vis-network.min.js")


@app.route("/api/status")
def api_status():
    return jsonify({
        "service": "NWIS-Sentinel Module 4 — Knowledge Graph + GraphRAG + LLM Briefing",
        "graph_nodes": _graph.number_of_nodes() if _graph else 0,
        "graph_edges": _graph.number_of_edges() if _graph else 0,
        "wells_loaded": len(_wells_list) if _wells_list else 0,
        "endpoints": {
            "graph_stats":      "GET /api/graph/stats",
            "well_subgraph":    "GET /api/graph/well/<well_id>",
            "wells_list":       "GET /api/wells",
            "rag_query":        "GET /api/rag/query?well_id=&hazard=&q=",
            "generate_briefing":"POST /api/briefing/generate",
            "get_briefing":     "GET /api/briefing/<briefing_id>",
            "list_briefings":   "GET /api/briefing/list",
            "backtest":         "GET /api/backtest",
        },
    })


@app.route("/api/graph/stats")
def api_graph_stats():
    if _graph is None:
        return jsonify({"error": "Graph not loaded."}), 503
    return jsonify(get_graph_stats(_graph))


@app.route("/api/graph/well/<path:well_id>")
def api_well_subgraph(well_id: str):
    if _graph is None:
        return jsonify({"error": "Graph not loaded."}), 503
    depth = int(request.args.get("depth", 2))
    result = get_well_subgraph(_graph, well_id, depth=depth)
    return jsonify(result)


@app.route("/api/wells")
def api_wells():
    if _wells_list is None:
        return jsonify({"error": "Wells not loaded."}), 503
    # Return compact list for dropdown
    out = []
    for w in _wells_list:
        out.append({
            "well_id":      w.get("well_id"),
            "source":       w.get("source"),
            "is_synthetic": w.get("is_synthetic", False),
            "latitude":     w.get("latitude"),
            "longitude":    w.get("longitude"),
            "total_depth_m": w.get("total_depth_m"),
        })
    return jsonify({"count": len(out), "wells": out})


@app.route("/api/rag/query")
def api_rag_query():
    well_id    = request.args.get("well_id", "").strip()
    hazard     = request.args.get("hazard", "").strip()
    query_text = request.args.get("q", "").strip()
    top_k      = int(request.args.get("top_k", 8))

    if not well_id:
        return jsonify({"error": "Missing required param: well_id"}), 400
    if not hazard:
        return jsonify({"error": "Missing required param: hazard"}), 400
    if not query_text:
        return jsonify({"error": "Missing required param: q (query text)"}), 400

    if _rag is None:
        return jsonify({"error": "RAG engine not loaded."}), 503

    try:
        result = _rag.query(well_id=well_id, hazard=hazard, query_text=query_text, top_k=top_k)
        return jsonify(result)
    except Exception as e:
        logger.error("RAG query error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/briefing/generate", methods=["POST"])
def api_generate_briefing():
    data       = request.get_json(force=True)
    well_id    = (data.get("well_id") or "").strip()
    hazard     = (data.get("hazard") or "").strip()
    api_key    = (data.get("api_key") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    query_text = (data.get("query_text") or f"{hazard.replace('_', ' ')} risk indicators").strip()

    if not well_id:
        return jsonify({"error": "Missing required field: well_id"}), 400
    if not hazard:
        return jsonify({"error": "Missing required field: hazard"}), 400
    if not api_key:
        return jsonify({
            "error": "Gemini API key required. Send {'api_key': 'AIza...'} in the request body, or set GOOGLE_API_KEY env var."
        }), 400

    # Step 1: Get latest risk data from Module 3 (immutable source)
    risk_data = get_latest_risk_data(well_id, hazard)
    if not risk_data:
        # Fallback to backtest data if we're on the backtest well
        risk_data = {
            "well_id": well_id,
            "hazard": hazard,
            "risk_score": None,
            "risk_level": "UNKNOWN",
            "wilson_ci": {},
            "measured_depth_m": None,
            "actionable_threshold_crossed": False,
            "note": "No live risk data found in risk_predictions.jsonl for this well/hazard.",
        }

    # Step 2: GraphRAG retrieval
    try:
        rag_result = _rag.query(well_id=well_id, hazard=hazard, query_text=query_text)
        rag_snippets = rag_result.get("results", [])
        analog_wells = rag_result.get("analog_wells", [])
    except Exception as e:
        logger.error("RAG error during briefing generation: %s", e)
        rag_snippets = []
        analog_wells = []

    # Step 3: Generate LLM briefing with citation verification
    try:
        briefing_obj = LLMBriefing(api_key=api_key)
        result = briefing_obj.generate(
            well_id=well_id,
            hazard=hazard,
            rag_results=rag_snippets,
            risk_data=risk_data,
            analog_wells=analog_wells,
        )
        return jsonify(result)
    except Exception as e:
        logger.error("Briefing generation error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/briefing/list")
def api_list_briefings():
    b = LLMBriefing()
    ids = b.list_briefings()
    return jsonify({"count": len(ids), "briefing_ids": ids})


@app.route("/api/briefing/<briefing_id>")
def api_get_briefing(briefing_id: str):
    b = LLMBriefing()
    result = b.get_saved_briefing(briefing_id)
    if result is None:
        return jsonify({"error": f"Briefing '{briefing_id}' not found."}), 404
    return jsonify(result)


@app.route("/api/backtest")
def api_backtest():
    if not BACKTEST_PATH.exists():
        return jsonify({"error": "backtest_result.json not found. Run module3/backtest_runner.py first."}), 404
    with open(BACKTEST_PATH, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/graph/search")
def api_graph_search():
    """Search for a well by well_id or formation name substring."""
    q = request.args.get("q", "").strip().lower()
    if not q or _wells_list is None:
        return jsonify({"results": []})
    matches = [
        {"well_id": w["well_id"], "source": w.get("source"), "is_synthetic": w.get("is_synthetic")}
        for w in _wells_list
        if q in w.get("well_id", "").lower()
    ][:20]
    return jsonify({"query": q, "results": matches})


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    startup()
    print("\nStarting NWIS-Sentinel Module 4 ...")
    print("Open: http://localhost:5004\n")
    app.run(host="0.0.0.0", port=5004, debug=False)
