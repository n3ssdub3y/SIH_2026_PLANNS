"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 4 — Part A: Knowledge Graph Builder

Builds an in-memory NetworkX property graph from all Module 1, 2, 3 outputs.

Node types:
  Well           — one per well from wells_metadata.json
  Formation      — one per unique formation name
  Event          — one per event from events.jsonl
  Hazard         — one per hazard type (5 canonical)
  Intervention   — keyword-extracted from event raw_text
  Outcome        — severity/resolution per event
  ReportSnippet  — citation anchor storing raw_text (one per event)

Edge types:
  DRILLED_THROUGH     Well   → Formation
  HAD_EVENT           Well   → Event
  FOLLOWED_BY         Event  → Event  (same well, depth order)
  MITIGATED_BY        Event  → Intervention
  LED_TO              Event  → Outcome
  ANALOG_FOR_HAZARD   Well   → Well   (from analog_wells.json top-5)
  EXTRACTED_FROM      Event  → ReportSnippet

Usage:
    python module4/knowledge_graph.py   # builds + saves graph
    from module4.knowledge_graph import load_graph, get_well_subgraph
"""

import json
import logging
import os
import pickle
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("knowledge_graph")

# ── Paths ─────────────────────────────────────────────────────────────────────
_MODULE4_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE4_DIR.parent

MODULE1_DIR  = _PROJECT_ROOT / "results" / "module1_outputs"
MODULE2_DIR  = _PROJECT_ROOT / "module2" / "outputs"
MODULE3_DIR  = _PROJECT_ROOT / "module3" / "outputs"
OUTPUTS_DIR  = _MODULE4_DIR / "outputs"

WELLS_META_PATH   = MODULE1_DIR / "wells_metadata.json"
EVENTS_JSONL_PATH = MODULE1_DIR / "events.jsonl"
VOCAB_PATH        = MODULE1_DIR / "event_type_vocabulary.json"
ANALOG_WELLS_PATH = MODULE2_DIR / "analog_wells.json"
GRAPH_PICKLE_PATH = OUTPUTS_DIR / "knowledge_graph.gpickle"
GRAPH_STATS_PATH  = OUTPUTS_DIR / "graph_stats.json"

# ── Canonical Hazards ──────────────────────────────────────────────────────────
CANONICAL_HAZARDS = [
    "mud_loss", "stuck_pipe", "overpressure", "torque_spike", "cementing"
]

# ── Intervention keyword patterns (case-insensitive) ──────────────────────────
INTERVENTION_PATTERNS: Dict[str, List[str]] = {
    "INT_LCM_PILL":          ["lcm", "lost circulation material", "lost-circulation material"],
    "INT_WEIGHTED_MUD":      ["weighted mud", "barite", "mud weight increas"],
    "INT_POOH":              ["pooh", "pull out of hole", "pulled out"],
    "INT_CIRC_DRILL":        ["circulated", "circulation restored", "circ restor"],
    "INT_WORKED_STRING":     ["worked string", "rotate string", "reciproc"],
    "INT_SIDETRACK":         ["sidetrack", "kick off", "new trajectory"],
    "INT_CEMENT_REMEDIAL":   ["remedial cement", "squeeze cement", "cbm"],
    "INT_BOP_TEST":          ["bop test", "pressure test", "well control"],
    "INT_INCREASE_ROP":      ["increase rop", "drill ahead", "resume drill"],
    "INT_REDUCE_WOB":        ["reduce wob", "reduce weight", "slack off"],
    "INT_SPOTTING_FLUID":    ["spotting fluid", "spot oil", "spot diesel"],
    "INT_NONE":              ["no intervention", "monitor", "continue"],
}

# ── Outcome types ──────────────────────────────────────────────────────────────
OUTCOME_TYPES = {
    "OUT_RESOLVED":   ["resolved", "restored", "resumed", "successful"],
    "OUT_PARTIAL":    ["partial", "reduced", "improved"],
    "OUT_UNRESOLVED": ["unresolved", "ongoing", "failed", "abandoned"],
    "OUT_NPT":        ["npt", "non-productive", "downtime"],
    "OUT_NONE":       [],
}


def _extract_interventions(raw_text: str) -> List[str]:
    """Return list of intervention node IDs found in a raw_text string."""
    if not raw_text or raw_text == "nan":
        return []
    text_lower = raw_text.lower()
    found = []
    for int_id, patterns in INTERVENTION_PATTERNS.items():
        if any(p in text_lower for p in patterns):
            found.append(int_id)
    return found if found else ["INT_NONE"]


def _extract_outcome(raw_text: str, severity: str) -> str:
    """Return the best outcome node ID based on raw_text + severity."""
    if not raw_text or raw_text == "nan":
        sev = (severity or "none").lower()
        if sev in ("critical", "high"):
            return "OUT_UNRESOLVED"
        return "OUT_NONE"
    text_lower = raw_text.lower()
    for out_id, patterns in OUTCOME_TYPES.items():
        if patterns and any(p in text_lower for p in patterns):
            return out_id
    sev = (severity or "none").lower()
    if sev in ("critical", "high"):
        return "OUT_NPT"
    return "OUT_NONE"


def build_graph() -> nx.DiGraph:
    """Build and return the full NWIS-Sentinel knowledge graph."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    G = nx.DiGraph()

    # ── 1. Load data ───────────────────────────────────────────────────────────
    logger.info("Loading wells_metadata.json ...")
    with open(WELLS_META_PATH, encoding="utf-8") as f:
        wells: List[Dict] = json.load(f)
    logger.info("  %d wells loaded.", len(wells))

    logger.info("Loading events.jsonl ...")
    events: List[Dict] = []
    with open(EVENTS_JSONL_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    logger.info("  %d events loaded.", len(events))

    logger.info("Loading event_type_vocabulary.json ...")
    with open(VOCAB_PATH, encoding="utf-8") as f:
        vocab_raw = json.load(f)
    vocab = vocab_raw.get("event_types", {})

    logger.info("Loading analog_wells.json (75MB — may take a moment) ...")
    with open(ANALOG_WELLS_PATH, encoding="utf-8") as f:
        analog_wells: Dict = json.load(f)
    logger.info("  analog_wells loaded for %d wells.", len(analog_wells))

    # ── 2. Add Hazard nodes ────────────────────────────────────────────────────
    logger.info("Adding Hazard nodes ...")
    for h in CANONICAL_HAZARDS:
        G.add_node(f"HAZARD_{h.upper()}", type="Hazard", hazard_id=h, label=h.replace("_", " ").title())

    # ── 3. Add Intervention nodes ──────────────────────────────────────────────
    logger.info("Adding Intervention nodes ...")
    for int_id, patterns in INTERVENTION_PATTERNS.items():
        G.add_node(int_id, type="Intervention", intervention_id=int_id,
                   label=int_id.replace("INT_", "").replace("_", " ").title(),
                   keywords=patterns)

    # ── 4. Add Outcome nodes ───────────────────────────────────────────────────
    logger.info("Adding Outcome nodes ...")
    for out_id in OUTCOME_TYPES:
        G.add_node(out_id, type="Outcome", outcome_id=out_id,
                   label=out_id.replace("OUT_", "").replace("_", " ").title())

    # ── 5. Add Well nodes + Formation nodes + DRILLED_THROUGH edges ───────────
    logger.info("Adding Well + Formation nodes ...")
    formations_seen: Set[str] = set()
    for well in wells:
        wid = well["well_id"]
        G.add_node(
            f"WELL_{wid}",
            type="Well",
            well_id=wid,
            source=well.get("source", "unknown"),
            latitude=well.get("latitude"),
            longitude=well.get("longitude"),
            is_synthetic=well.get("is_synthetic", False),
            total_depth_m=well.get("total_depth_m"),
            bha_type=well.get("bha_type"),
            label=wid,
        )
        # Formation tops
        for ft in well.get("formation_tops", []):
            fname = ft.get("formation", "").strip()
            if not fname or fname.lower() in ("unknown", "n/a", ""):
                continue
            fnode = f"FORM_{fname[:60].replace(' ', '_').upper()}"
            if fnode not in formations_seen:
                G.add_node(fnode, type="Formation", formation_name=fname, label=fname)
                formations_seen.add(fnode)
            G.add_edge(
                f"WELL_{wid}", fnode,
                relation="DRILLED_THROUGH",
                depth_md_m=ft.get("depth_md_m"),
            )

    logger.info("  %d Well nodes, %d Formation nodes added.", len(wells), len(formations_seen))

    # ── 6. Add Event + ReportSnippet nodes + edges ────────────────────────────
    logger.info("Adding Event + ReportSnippet nodes ...")
    # Group events by well for FOLLOWED_BY edges
    events_by_well: Dict[str, List[Dict]] = defaultdict(list)

    for evt in events:
        eid  = evt.get("event_id", "")
        wid  = evt.get("well_id", "")
        raw  = evt.get("raw_text", "") or ""
        haz  = evt.get("hazard", "none")
        sev  = evt.get("severity", "none") or "none"
        etype = evt.get("event_type_id", "EVT_UNKNOWN")
        depth = evt.get("depth_m", 0.0) or 0.0

        snippet_id = f"SNIPPET_{eid}"

        # ReportSnippet node
        G.add_node(
            snippet_id,
            type="ReportSnippet",
            event_id=eid,
            well_id=wid,
            raw_text=raw[:2000],      # cap at 2000 chars for memory
            label=f"Snippet:{eid[:30]}",
        )

        # Event node
        G.add_node(
            eid,
            type="Event",
            event_id=eid,
            well_id=wid,
            event_type_id=etype,
            hazard=haz,
            severity=sev,
            depth_m=depth,
            report_date=evt.get("report_date"),
            formation_id=evt.get("formation_id"),
            confidence=evt.get("confidence", 1.0),
            is_synthetic=evt.get("is_synthetic", False),
            label=f"{etype}@{wid}",
        )

        # EXTRACTED_FROM: Event → ReportSnippet
        G.add_edge(eid, snippet_id, relation="EXTRACTED_FROM")

        # HAD_EVENT: Well → Event
        if wid:
            G.add_edge(f"WELL_{wid}", eid, relation="HAD_EVENT", depth_m=depth)

        # MITIGATED_BY: Event → Intervention
        for int_id in _extract_interventions(raw):
            G.add_edge(eid, int_id, relation="MITIGATED_BY")

        # LED_TO: Event → Outcome
        out_id = _extract_outcome(raw, sev)
        G.add_edge(eid, out_id, relation="LED_TO")

        # Hazard linkage: Event → Hazard node (if hazard is one of 5 canonical)
        if haz in CANONICAL_HAZARDS:
            G.add_edge(eid, f"HAZARD_{haz.upper()}", relation="CLASSIFIED_AS")

        events_by_well[wid].append(evt)

    # ── 7. FOLLOWED_BY edges (depth-ordered per well) ─────────────────────────
    logger.info("Adding FOLLOWED_BY edges ...")
    followed_count = 0
    for wid, wevts in events_by_well.items():
        sorted_evts = sorted(wevts, key=lambda e: e.get("depth_m", 0.0) or 0.0)
        for i in range(len(sorted_evts) - 1):
            e_curr = sorted_evts[i]["event_id"]
            e_next = sorted_evts[i + 1]["event_id"]
            depth_gap = (sorted_evts[i+1].get("depth_m", 0) or 0) - (sorted_evts[i].get("depth_m", 0) or 0)
            G.add_edge(e_curr, e_next, relation="FOLLOWED_BY", depth_gap_m=round(depth_gap, 2))
            followed_count += 1

    logger.info("  %d FOLLOWED_BY edges added.", followed_count)

    # ── 8. ANALOG_FOR_HAZARD edges (top 5 per hazard per well) ────────────────
    logger.info("Adding ANALOG_FOR_HAZARD edges (top-5 per hazard) ...")
    analog_edge_count = 0
    for target_wid, hazard_dict in analog_wells.items():
        src_node = f"WELL_{target_wid}"
        if src_node not in G:
            continue
        for hazard, analog_list in hazard_dict.items():
            if not isinstance(analog_list, list):
                continue
            top5 = analog_list[:5]
            for rank, analog in enumerate(top5):
                analog_wid = analog.get("well_id", "")
                dst_node = f"WELL_{analog_wid}"
                if dst_node not in G:
                    continue
                G.add_edge(
                    src_node, dst_node,
                    relation="ANALOG_FOR_HAZARD",
                    hazard=hazard,
                    rank=rank + 1,
                    weighted_score=analog.get("weighted_score", 0.0),
                    feature_breakdown=json.dumps(analog.get("feature_breakdown", {})),
                )
                analog_edge_count += 1

    logger.info("  %d ANALOG_FOR_HAZARD edges added.", analog_edge_count)

    # ── 9. Summary ─────────────────────────────────────────────────────────────
    node_types: Dict[str, int] = defaultdict(int)
    for _, data in G.nodes(data=True):
        node_types[data.get("type", "Unknown")] += 1

    edge_types: Dict[str, int] = defaultdict(int)
    for _, _, data in G.edges(data=True):
        edge_types[data.get("relation", "Unknown")] += 1

    stats = {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_counts_by_type": dict(node_types),
        "edge_counts_by_type": dict(edge_types),
    }

    logger.info("=== Graph Built ===")
    logger.info("  Total nodes: %d", stats["total_nodes"])
    logger.info("  Total edges: %d", stats["total_edges"])
    for t, c in sorted(stats["node_counts_by_type"].items()):
        logger.info("    [Node] %s: %d", t, c)
    for t, c in sorted(stats["edge_counts_by_type"].items()):
        logger.info("    [Edge] %s: %d", t, c)

    # ── 10. Serialize ──────────────────────────────────────────────────────────
    logger.info("Saving knowledge_graph.gpickle ...")
    with open(GRAPH_PICKLE_PATH, "wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

    with open(GRAPH_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    logger.info("Graph saved → %s", GRAPH_PICKLE_PATH)
    logger.info("Stats saved → %s", GRAPH_STATS_PATH)
    return G


# ── Public API ─────────────────────────────────────────────────────────────────

_GRAPH: Optional[nx.DiGraph] = None

def load_graph(rebuild: bool = False) -> nx.DiGraph:
    """Load graph from disk (or build if not cached)."""
    global _GRAPH
    if _GRAPH is not None and not rebuild:
        return _GRAPH
    if GRAPH_PICKLE_PATH.exists() and not rebuild:
        logger.info("Loading cached graph from %s ...", GRAPH_PICKLE_PATH)
        with open(GRAPH_PICKLE_PATH, "rb") as f:
            _GRAPH = pickle.load(f)
        logger.info("  Graph loaded: %d nodes, %d edges.", _GRAPH.number_of_nodes(), _GRAPH.number_of_edges())
    else:
        logger.info("Building knowledge graph from scratch ...")
        _GRAPH = build_graph()
    return _GRAPH


def get_well_subgraph(G: nx.DiGraph, well_id: str, depth: int = 2) -> Dict[str, Any]:
    """
    Return a balanced, readable subgraph for the given well_id.
    Includes:
      1. Target Well (hero node)
      2. Formations drilled through
      3. Direct Events on this well
      4. Top direct Analog Wells (up to 6, avoiding transitive cliques of 100+ wells)
      5. Associated Hazards, Interventions, Outcomes, and ReportSnippets
    """
    well_node = f"WELL_{well_id}"
    if well_node not in G:
        return {"error": f"Well '{well_id}' not found in graph."}

    subgraph_nodes: Set[str] = {well_node}

    # 1. Direct Formations
    formations = [
        v for u, v, d in G.out_edges(well_node, data=True)
        if d.get("relation") == "DRILLED_THROUGH"
    ][:12]
    subgraph_nodes.update(formations)

    # 2. Direct Events
    direct_events = [
        v for u, v, d in G.out_edges(well_node, data=True)
        if d.get("relation") == "HAD_EVENT"
    ][:10]
    subgraph_nodes.update(direct_events)

    # 3. Top direct Analog Wells only (prevents transitive explosion of 100+ offset wells)
    analog_wells = [
        v for u, v, d in G.out_edges(well_node, data=True)
        if d.get("relation") == "ANALOG_FOR_HAZARD"
    ][:6]
    subgraph_nodes.update(analog_wells)

    # 4. Key events from analog wells (up to 2 each)
    events_to_expand = list(direct_events)
    for aw in analog_wells:
        aw_events = [
            v for u, v, d in G.out_edges(aw, data=True)
            if d.get("relation") == "HAD_EVENT"
        ][:2]
        subgraph_nodes.update(aw_events)
        events_to_expand.extend(aw_events)

    # 5. Connect events to their Hazards, Interventions, Outcomes, Snippets, and Next Events
    for ev in events_to_expand[:18]:
        for u, v, d in G.out_edges(ev, data=True):
            rel = d.get("relation")
            if rel in ("CLASSIFIED_AS", "MITIGATED_BY", "LED_TO", "EXTRACTED_FROM"):
                subgraph_nodes.add(v)
        for u, v, d in G.in_edges(ev, data=True):
            rel = d.get("relation")
            if rel in ("FOLLOWED_BY",):
                subgraph_nodes.add(u)

    sub = G.subgraph(subgraph_nodes)

    nodes_out = []
    for n, data in sub.nodes(data=True):
        node_data = {
            "id": n,
            "type": data.get("type", "Unknown"),
            "label": data.get("label", n[:40]),
        }
        if data.get("type") == "Well":
            node_data.update({
                "well_id": data.get("well_id"),
                "source": data.get("source"),
                "is_synthetic": data.get("is_synthetic"),
            })
        elif data.get("type") == "Event":
            node_data.update({
                "hazard": data.get("hazard"),
                "severity": data.get("severity"),
                "depth_m": data.get("depth_m"),
                "event_type_id": data.get("event_type_id"),
            })
        elif data.get("type") == "Formation":
            node_data["formation_name"] = data.get("formation_name")
        elif data.get("type") == "ReportSnippet":
            node_data["raw_text"] = data.get("raw_text", "")
        nodes_out.append(node_data)

    edges_out = []
    for u, v, data in sub.edges(data=True):
        if u in subgraph_nodes and v in subgraph_nodes:
            edges_out.append({"from": u, "to": v, "relation": data.get("relation", "")})

    return {
        "well_id": well_id,
        "node_count": len(nodes_out),
        "edge_count": len(edges_out),
        "nodes": nodes_out,
        "edges": edges_out,
    }


def get_graph_stats(G: nx.DiGraph) -> Dict[str, Any]:
    """Return graph statistics dict."""
    if GRAPH_STATS_PATH.exists():
        with open(GRAPH_STATS_PATH, encoding="utf-8") as f:
            return json.load(f)
    node_types: Dict[str, int] = defaultdict(int)
    for _, data in G.nodes(data=True):
        node_types[data.get("type", "Unknown")] += 1
    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_counts_by_type": dict(node_types),
    }


if __name__ == "__main__":
    g = build_graph()
    print(f"\n[OK] Knowledge Graph built: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
