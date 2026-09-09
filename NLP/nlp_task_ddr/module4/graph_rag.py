"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 4 — Part B: GraphRAG Retrieval Engine

Two-stage retrieval:
  Stage 1 (Pre-filter): Restrict graph to analog wells for the target hazard
                        (uses analog_wells.json from Module 2 — NOT naive vector search)
  Stage 2 (Semantic):   Embed ReportSnippet raw_text with sentence-transformers
                        and find top-K semantically similar to the engineer's query

This pre-filter-then-retrieve order is the core GraphRAG novelty per the PS spec.
Plain vector similarity over ALL documents is explicitly the weaker approach.

Usage:
    from module4.graph_rag import GraphRAG
    rag = GraphRAG()
    results = rag.query(well_id="15/9-F-9A", hazard="stuck_pipe", query_text="tight hole precursor")
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("graph_rag")

_MODULE4_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE4_DIR.parent
MODULE2_DIR = _PROJECT_ROOT / "module2" / "outputs"
ANALOG_WELLS_PATH = MODULE2_DIR / "analog_wells.json"

TOP_K_ANALOGS    = 10   # number of analog wells to pre-filter to
TOP_K_RESULTS    = 8    # number of snippets to return per query


class GraphRAG:
    """
    GraphRAG: Graph-anchored semantic retrieval.

    Pre-filters to analog-well subgraph first, then does sentence-transformer
    embedding similarity only within that subgraph.
    """

    def __init__(self, graph=None):
        """
        Args:
            graph: An already-loaded networkx graph (nx.DiGraph). If None,
                   will be loaded lazily on first query.
        """
        self._graph = graph
        self._model = None
        self._snippet_embeddings: Optional[Dict[str, np.ndarray]] = None
        self._snippet_texts: Optional[Dict[str, str]] = None
        self._analog_cache: Dict[str, Dict[str, List[Dict]]] = {}
        self._analog_wells_loaded = False

    def _load_graph(self):
        """Lazy-load graph."""
        if self._graph is None:
            from module4.knowledge_graph import load_graph
            self._graph = load_graph()

    def _load_model(self):
        """Lazy-load sentence-transformers model."""
        if self._model is None:
            logger.info("Loading sentence-transformer model (all-MiniLM-L6-v2) ...")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("  Model loaded.")

    def _load_analog_wells(self):
        """Load analog_wells.json once (lazy, cached)."""
        if self._analog_wells_loaded:
            return
        logger.info("Loading analog_wells.json for pre-filter ...")
        with open(ANALOG_WELLS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        # Build: {well_id: {hazard: [top-10 analog dicts]}}
        for wid, hazard_dict in raw.items():
            self._analog_cache[wid] = {}
            for hazard, analog_list in hazard_dict.items():
                if isinstance(analog_list, list):
                    self._analog_cache[wid][hazard] = analog_list[:TOP_K_ANALOGS]
        self._analog_wells_loaded = True
        logger.info("  analog_wells loaded for %d wells.", len(self._analog_cache))

    def _get_analog_well_ids(self, target_well_id: str, hazard: str) -> List[str]:
        """Return the top-K analog well IDs for (target_well_id, hazard)."""
        self._load_analog_wells()
        hazard_map = self._analog_cache.get(target_well_id, {})
        analog_list = hazard_map.get(hazard, [])
        return [a["well_id"] for a in analog_list if "well_id" in a]

    def _get_analog_details(self, target_well_id: str, hazard: str) -> List[Dict]:
        """Return full analog detail dicts for (target_well_id, hazard)."""
        self._load_analog_wells()
        hazard_map = self._analog_cache.get(target_well_id, {})
        return hazard_map.get(hazard, [])

    def _build_snippet_index(self, analog_well_ids: List[str]) -> Tuple[List[str], List[str], List[np.ndarray]]:
        """
        For the given analog well IDs, collect all ReportSnippet nodes
        from the graph and embed them.

        Returns:
            (node_ids, texts, embeddings)
        """
        self._load_graph()
        self._load_model()

        node_ids = []
        texts = []

        # Collect snippet nodes for these analog wells
        for wid in analog_well_ids:
            well_node = f"WELL_{wid}"
            if well_node not in self._graph:
                continue
            # Walk: Well → (HAD_EVENT) → Event → (EXTRACTED_FROM) → ReportSnippet
            for evt_node in self._graph.successors(well_node):
                if self._graph.nodes[evt_node].get("type") != "Event":
                    continue
                for snippet_node in self._graph.successors(evt_node):
                    if self._graph.nodes[snippet_node].get("type") != "ReportSnippet":
                        continue
                    raw_text = self._graph.nodes[snippet_node].get("raw_text", "") or ""
                    if raw_text and raw_text.strip() and raw_text.strip() != "nan":
                        node_ids.append(snippet_node)
                        texts.append(raw_text[:1000])

        if not texts:
            return [], [], []

        logger.info("  Embedding %d snippets from %d analog wells ...", len(texts), len(analog_well_ids))
        embeddings = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return node_ids, texts, list(embeddings)

    def query(
        self,
        well_id: str,
        hazard: str,
        query_text: str,
        top_k: int = TOP_K_RESULTS,
    ) -> Dict[str, Any]:
        """
        Main GraphRAG query.

        Args:
            well_id:    Target well ID (e.g. "15/9-F-9A")
            hazard:     Hazard type (e.g. "stuck_pipe")
            query_text: Engineer's natural language question
            top_k:      Number of results to return

        Returns:
            dict with:
              - analog_wells:   list of pre-filtered analog wells (with AHP scores)
              - results:        top-k semantically similar snippets with node_id + score
              - query_text:     echo of the query
              - retrieval_stats: counts
        """
        self._load_graph()
        self._load_model()

        # Stage 1: Pre-filter to analog subgraph
        analog_well_ids = self._get_analog_well_ids(well_id, hazard)
        analog_details  = self._get_analog_details(well_id, hazard)

        if not analog_well_ids:
            return {
                "error": f"No analog wells found for well='{well_id}', hazard='{hazard}'.",
                "analog_wells": [],
                "results": [],
            }

        # Stage 2: Build embedding index over analog subgraph snippets
        node_ids, texts, embeddings = self._build_snippet_index(analog_well_ids)

        if not embeddings:
            return {
                "analog_wells": analog_details[:5],
                "results": [],
                "query_text": query_text,
                "retrieval_stats": {"analog_wells_used": len(analog_well_ids), "snippets_indexed": 0},
                "message": "No non-empty report snippets found for these analog wells.",
            }

        # Embed query
        query_emb = self._model.encode([query_text], convert_to_numpy=True)[0]

        # Cosine similarity
        emb_matrix = np.array(embeddings)
        norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1e-10, norms)
        normed = emb_matrix / norms

        query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-10)
        scores = normed @ query_norm

        # Top-K
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            snippet_id = node_ids[idx]
            snippet_data = self._graph.nodes[snippet_id]
            event_id = snippet_data.get("event_id", "")
            event_data = self._graph.nodes.get(event_id, {})

            results.append({
                "rank": len(results) + 1,
                "node_id": snippet_id,
                "event_id": event_id,
                "well_id": snippet_data.get("well_id", ""),
                "event_type_id": event_data.get("event_type_id", ""),
                "hazard": event_data.get("hazard", ""),
                "depth_m": event_data.get("depth_m"),
                "severity": event_data.get("severity", ""),
                "similarity_score": float(round(scores[idx], 4)),
                "raw_text": texts[idx][:500],  # truncate for response
            })

        return {
            "well_id": well_id,
            "hazard": hazard,
            "query_text": query_text,
            "analog_wells": analog_details[:5],  # top-5 shown in UI
            "results": results,
            "retrieval_stats": {
                "analog_wells_used": len(analog_well_ids),
                "snippets_indexed": len(node_ids),
                "returned": len(results),
            },
        }

    def get_analog_summary(self, well_id: str, hazard: str) -> List[Dict]:
        """Return the top-10 analog wells with their AHP breakdown."""
        self._load_analog_wells()
        hazard_map = self._analog_cache.get(well_id, {})
        return hazard_map.get(hazard, [])[:10]
