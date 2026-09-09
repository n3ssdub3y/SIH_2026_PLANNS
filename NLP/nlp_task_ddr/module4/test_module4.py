"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 4 Test Suite: Knowledge Graph, GraphRAG, LLM Briefing & REST Endpoints
"""

import json
import pytest
from pathlib import Path

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
    """Verify Module 3 risk data is accurately loaded and contains Wilson CI."""
    risk = get_latest_risk_data("15/9-F-9A", "stuck_pipe")
    if risk is not None:
        assert "risk_score" in risk
        assert "risk_level" in risk
        assert "wilson_ci" in risk
        assert "lower" in risk["wilson_ci"]
        assert "upper" in risk["wilson_ci"]


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
