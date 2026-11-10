"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 4 Test Suite: Knowledge Graph, GraphRAG, LLM Briefing & REST Endpoints
"""

import json
import pytest
from pathlib import Path

from module4 import llm_briefing
from module4.knowledge_graph import load_graph, get_well_subgraph, get_graph_stats
from module4.graph_rag import GraphRAG
from module4.llm_briefing import (
    LLMBriefing,
    _verify_citation,
    _parse_citations,
    _extract_keywords,
    get_latest_risk_data,
)
from module4.app import app


@pytest.fixture(scope="module")
def graph():
    """Load the pre-built knowledge graph."""
    g = load_graph()
    assert g is not None
    return g


@pytest.fixture(scope="module")
def client():
    """Flask test client for Module 4."""
    from module4.app import startup
    startup()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── 1. Knowledge Graph Tests ──────────────────────────────────────────────────

def test_knowledge_graph_structure(graph):
    """Verify nodes and edges count meet system specifications."""
    stats = get_graph_stats(graph)
    assert stats["total_nodes"] >= 4000, f"Expected >=4000 nodes, got {stats['total_nodes']}"
    assert stats["total_edges"] >= 12000, f"Expected >=12000 edges, got {stats['total_edges']}"
    
    # Check node types
    node_types = stats["node_counts_by_type"]
    assert "Well" in node_types and node_types["Well"] >= 150
    assert "Event" in node_types and node_types["Event"] >= 1800
    assert "Formation" in node_types and node_types["Formation"] >= 50
    assert "Hazard" in node_types and node_types["Hazard"] == 5


def test_well_subgraph_extraction(graph):
    """Verify subgraph extraction for flagship Volve well 15/9-F-9A."""
    sub = get_well_subgraph(graph, "15/9-F-9A", depth=2)
    assert "nodes" in sub and "edges" in sub
    assert len(sub["nodes"]) > 0
    assert len(sub["edges"]) > 0
    
    # Verify well node is present in subgraph
    node_ids = {n["id"] for n in sub["nodes"]}
    assert "WELL_15/9-F-9A" in node_ids or any("15/9-F-9A" in nid for nid in node_ids)


# ── 2. GraphRAG Retrieval Tests ───────────────────────────────────────────────

def test_graph_rag_retrieval(graph):
    """Verify GraphRAG retrieves relevant offset analog incident snippets."""
    rag = GraphRAG(graph=graph)
    res = rag.query(
        well_id="15/9-F-9A",
        hazard="stuck_pipe",
        query_text="differential sticking high overbalance in reservoir",
        top_k=5
    )
    assert "results" in res
    assert "analog_wells" in res
    assert res["hazard"] == "stuck_pipe"
    assert res["well_id"] == "15/9-F-9A"
    assert len(res["results"]) > 0
    
    top = res["results"][0]
    assert "node_id" in top
    assert "raw_text" in top
    assert "similarity_score" in top


# ── 3. Citation Verification & Parsing Tests ─────────────────────────────────

def test_citation_parsing():
    """Verify regex extraction of [NODE_ID] tags from LLM response."""
    sample_text = (
        "High differential sticking risk in Heimdal formation [EVT_2014_01]. "
        "Recommend reducing mud weight to 1.25 SG [SNIP_1234]. "
        "Offset well 15/9-F-12 experienced identical torque spike."
    )
    parsed = _parse_citations(sample_text)
    assert len(parsed) == 3
    assert parsed[0][1] == ["EVT_2014_01"]
    assert parsed[1][1] == ["SNIP_1234"]
    assert parsed[2][1] == []  # Third sentence has no citation


def test_citation_keyword_verification(graph):
    """Verify automated factual citation verification against graph nodes."""
    # Find a ReportSnippet node with valid text (not nan)
    snippet_node = None
    for n, data in graph.nodes(data=True):
        raw = data.get("raw_text", "")
        if data.get("type") == "ReportSnippet" and raw and raw != "nan" and len(raw.strip()) > 30:
            snippet_node = (n, data)
            break
            
    assert snippet_node is not None, "ReportSnippet node not found in graph"
    nid, ndata = snippet_node
    raw_text = ndata["raw_text"]
    kws = list(_extract_keywords(raw_text))
    assert len(kws) > 0
    
    # Test valid citation sentence using overlapping keyword
    valid_sentence = f"The drilling log reports {kws[0]} during the run."
    passed, reason = _verify_citation(valid_sentence, nid, graph)
    assert passed is True
    assert "matching keywords" in reason
    
    # Test invalid citation sentence with completely unrelated content
    invalid_sentence = "Extraterrestrial spacecraft detected near Jupiter orbit."
    passed_inv, reason_inv = _verify_citation(invalid_sentence, nid, graph)
    assert passed_inv is False


# ── 4. Risk Data Integration (PS Rules) ──────────────────────────────────────

def test_latest_risk_data_retrieval():
    """
    Module 3 risk data must load on a fresh clone (no live file) via the committed
    backtest stream, and must carry the Wilson CI whichever source served it.
    """
    risk = get_latest_risk_data("15/9-F-9A", "stuck_pipe")
    assert risk is not None, (
        "No risk data for 15/9-F-9A/stuck_pipe: neither risk_predictions_live.jsonl nor the "
        "committed risk_predictions_backtest.jsonl yielded a complete record"
    )
    assert risk["risk_source"] in ("live", "backtest")
    for key in llm_briefing.RISK_REQUIRED_KEYS:
        assert key in risk
    assert "lower" in risk["wilson_ci"]
    assert "upper" in risk["wilson_ci"]


# Risk-source precedence: live stream first, backtest stream as fallback.

def _risk_rec(**overrides):
    rec = {
        "well_id": "W-TEST", "hazard": "stuck_pipe",
        "risk_score": 0.5, "risk_level": "HIGH",
        "wilson_ci": {"lower": 0.2, "center": 0.5, "upper": 0.8},
    }
    rec.update(overrides)
    return rec


def _write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


@pytest.fixture
def risk_paths(tmp_path, monkeypatch):
    live, backtest = tmp_path / "live.jsonl", tmp_path / "backtest.jsonl"
    monkeypatch.setattr(llm_briefing, "RISK_LIVE_PATH", live)
    monkeypatch.setattr(llm_briefing, "RISK_BACKTEST_PATH", backtest)
    return live, backtest


def test_risk_reader_prefers_live_stream(risk_paths):
    live, backtest = risk_paths
    _write_jsonl(live, [_risk_rec(risk_score=0.9, risk_level="CRITICAL")])
    _write_jsonl(backtest, [_risk_rec(risk_score=0.1, risk_level="LOW")])
    risk = get_latest_risk_data("W-TEST", "stuck_pipe")
    assert risk["risk_source"] == "live"
    assert risk["risk_score"] == 0.9


def test_risk_reader_falls_back_when_live_file_missing(risk_paths):
    _, backtest = risk_paths
    _write_jsonl(backtest, [_risk_rec(risk_score=0.1, risk_level="LOW")])
    risk = get_latest_risk_data("W-TEST", "stuck_pipe")
    assert risk["risk_source"] == "backtest"
    assert risk["risk_score"] == 0.1


def test_risk_reader_falls_back_when_live_lacks_well_or_hazard(risk_paths):
    live, backtest = risk_paths
    _write_jsonl(live, [_risk_rec(hazard="torque_spike"), _risk_rec(well_id="OTHER")])
    _write_jsonl(backtest, [_risk_rec(risk_score=0.3)])
    risk = get_latest_risk_data("W-TEST", "stuck_pipe")
    assert risk["risk_source"] == "backtest"
    # ...while a hazard that only the live stream has is still served live
    assert get_latest_risk_data("W-TEST", "torque_spike")["risk_source"] == "live"


def test_risk_reader_skips_incomplete_live_record(risk_paths):
    live, backtest = risk_paths
    incomplete = _risk_rec()
    del incomplete["wilson_ci"]
    _write_jsonl(live, [incomplete])
    _write_jsonl(backtest, [_risk_rec(risk_score=0.3)])
    assert get_latest_risk_data("W-TEST", "stuck_pipe")["risk_source"] == "backtest"


def test_risk_reader_returns_last_matching_record_and_tolerates_bad_lines(risk_paths):
    live, _ = risk_paths
    live.write_text(
        json.dumps(_risk_rec(risk_score=0.2)) + "\nnot-json\n\n"
        + json.dumps(_risk_rec(risk_score=0.7)) + "\n",
        encoding="utf-8",
    )
    assert get_latest_risk_data("W-TEST", "stuck_pipe")["risk_score"] == 0.7


def test_risk_reader_returns_none_when_no_stream_matches(risk_paths):
    assert get_latest_risk_data("W-TEST", "stuck_pipe") is None


def test_briefing_prompt_generation():
    """Verify prompt forces strict non-hallucination rules and immutable numbers."""
    b = LLMBriefing(api_key="TEST_MOCK_KEY")
    mock_risk = {
        "risk_score": 0.842,
        "risk_level": "CRITICAL",
        "wilson_ci": {"lower": 0.68, "upper": 0.94, "n_successes": 5, "n_trials": 6},
        "measured_depth_m": 619.0,
        "actionable_threshold_crossed": True
    }
    mock_rag = [{
        "node_id": "SNIP_TEST_01",
        "well_id": "15/9-F-12",
        "event_type_id": "STUCK_PIPE",
        "depth_m": 620.0,
        "raw_text": "Severe pipe stuck while reaming bottom hole.",
        "similarity_score": 0.92
    }]
    mock_analogs = [{
        "well_id": "15/9-F-12",
        "weighted_score": 0.95,
        "source": "real_volve",
        "is_synthetic": False
    }]
    
    prompt = b._build_prompt(
        well_id="15/9-F-9A",
        hazard="stuck_pipe",
        risk_data=mock_risk,
        rag_results=mock_rag,
        analog_wells=mock_analogs
    )
    
    assert "DO NOT invent any risk score" in prompt
    assert "0.842" in prompt
    assert "CRITICAL" in prompt
    assert "[SNIP_TEST_01]" in prompt
    assert "15/9-F-12" in prompt


# ── 5. Flask App REST API Endpoints ──────────────────────────────────────────

def test_endpoint_status(client):
    """Test GET /api/status"""
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.get_json()
    assert "service" in data
    assert data["graph_nodes"] >= 4000


def test_endpoint_graph_stats(client):
    """Test GET /api/graph/stats"""
    res = client.get("/api/graph/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total_nodes"] >= 4000
    assert data["total_edges"] >= 12000


def test_endpoint_wells_list(client):
    """Test GET /api/wells"""
    res = client.get("/api/wells")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] >= 150
    assert len(data["wells"]) >= 150


def test_endpoint_well_subgraph(client):
    """Test GET /api/graph/well/<well_id>"""
    res = client.get("/api/graph/well/15/9-F-9A?depth=2")
    assert res.status_code == 200
    data = res.get_json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0


def test_endpoint_rag_query(client):
    """Test GET /api/rag/query"""
    res = client.get("/api/rag/query?well_id=15/9-F-9A&hazard=stuck_pipe&q=differential+sticking&top_k=3")
    assert res.status_code == 200
    data = res.get_json()
    assert "results" in data
    assert "analog_wells" in data


def test_endpoint_backtest(client):
    """Test GET /api/backtest"""
    res = client.get("/api/backtest")
    assert res.status_code == 200
    data = res.get_json()
    assert "summary" in data
    assert data["summary"]["well_id"] == "15/9-F-9A"
    assert data["summary"]["lead_time_metrics"]["actionable_lead_distance_metres"] == 106.48


def test_endpoint_briefing_list(client):
    """Test GET /api/briefing/list"""
    res = client.get("/api/briefing/list")
    assert res.status_code == 200
    data = res.get_json()
    assert "briefing_ids" in data
    assert isinstance(data["briefing_ids"], list)
