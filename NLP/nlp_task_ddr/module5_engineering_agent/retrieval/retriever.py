from typing import List, Dict, Any, Optional

from .vector_store import VectorStore
from ingestion.data_adapter import DataAdapter
from schemas.models import CurrentSituation, EvidenceItem
from config import TOP_K_ANALOGS, TOP_K_EVIDENCE

# Re-ranking bonuses applied on top of cosine similarity when the three candidate
# pools are merged (see Retriever.retrieve).
_BOOST_FOCUS_HAZARD = 0.15          # hazard named in the question itself
_BOOST_PANEL_HAZARD = 0.05          # hazard only selected in the UI side panel
_BOOST_ANALOG_WELL = 0.10
_PENALTY_ROUTINE = 0.20     # hazard == "none" while the question is about a hazard
_PENALTY_ROUTINE_SOFT = 0.05


def _in_filter(field: str, values: List[str]) -> Dict[str, Any]:
    return {field: values[0]} if len(values) == 1 else {field: {"$in": values}}


class Retriever:
    def __init__(self):
        self.data_adapter = DataAdapter()
        self.vector_store = VectorStore()

        # Populate vector store if it's empty
        self._initialize_vector_store()

    def _initialize_vector_store(self):
        """Populate the vector store if empty."""
        try:
            # check if collection has items
            count = self.vector_store.collection.count()
            if count == 0:
                print("Vector store is empty. Populating from M1/M2 data...")
                all_events = self.data_adapter.events + self.data_adapter.flagged_incidents
                if all_events:
                     self.vector_store.add_events(all_events)
                print(f"Populated vector store with {len(all_events)} events.")
        except Exception as e:
            print(f"Error initializing vector store: {e}")

    def retrieve(
        self,
        question: str,
        situation: Optional[CurrentSituation] = None,
        focus_hazards: Optional[List[str]] = None,
        question_hazards: Optional[List[str]] = None,
    ) -> tuple[List[str], List[EvidenceItem]]:
        """
        Question-driven retrieval:
        1. Top-K analog wells from Module 2 for the situation's well/hazard.
        2. Three semantic searches over the event store, merged and re-ranked:
           - restricted to the analog wells (offset-well evidence),
           - restricted to the hazards the question is about (so a mud-loss question
             finds mud-loss records even when the analogs have none),
           - unrestricted (pure semantic match on the question).
           Records of a focus hazard and from analog wells are boosted, routine
           drilling records are pushed down.
        Previously only the analog-well search ran; with 5 synthetic analogs x 5 events
        that pool was ~25 records, so most questions returned the same evidence.
        """
        focus = [h for h in (focus_hazards or []) if h]
        analog_wells: List[str] = []
        if situation and situation.well_id:
            analog_wells = self.data_adapter.get_top_analog_wells(
                well_id=situation.well_id,
                hazard=situation.hazard,
                top_k=TOP_K_ANALOGS
            )

        # Question first; situation context only for the fields that are actually set.
        search_query = question
        if situation:
            ctx = []
            if focus:
                ctx.append(f"hazard {focus[0].replace('_', ' ')}")
            if situation.formation and situation.formation.lower() != "unknown":
                ctx.append(f"formation {situation.formation}")
            if situation.depth:
                ctx.append(f"depth {situation.depth}m")
            if ctx:
                search_query += ". Context: " + ", ".join(ctx) + "."

        k = TOP_K_EVIDENCE
        pools: List[List[Dict[str, Any]]] = []
        if analog_wells:
            pools.append(self.vector_store.search(search_query, _in_filter("well_id", analog_wells), k))
        if focus:
            pools.append(self.vector_store.search(search_query, _in_filter("hazard", focus), k))
        pools.append(self.vector_store.search(search_query, None, k))

        analog_set, focus_set = set(analog_wells), set(focus)
        # Hazards the question names outrank the panel's; with none named, the panel's count fully.
        strong = set(question_hazards or []) or focus_set
        scored: Dict[tuple, tuple] = {}
        for pool in pools:
            for res in pool:
                meta = res["metadata"]
                key = (meta.get("well_id"), res["document"])
                score = res.get("similarity") or 0.0
                hz = meta.get("hazard", "none")
                if hz in strong:
                    score += _BOOST_FOCUS_HAZARD
                elif hz in focus_set:
                    score += _BOOST_PANEL_HAZARD
                if meta.get("well_id") in analog_set:
                    score += _BOOST_ANALOG_WELL
                if hz in ("none", ""):
                    score -= _PENALTY_ROUTINE if focus_set else _PENALTY_ROUTINE_SOFT
                if key not in scored or score > scored[key][0]:
                    scored[key] = (score, res)

        ranked = sorted(scored.values(), key=lambda t: t[0], reverse=True)[:k]

        evidence_items = []
        for score, res in ranked:
            meta = res['metadata']
            evidence_items.append(EvidenceItem(
                well_id=meta.get("well_id", "Unknown"),
                depth=meta.get("depth_m"),
                formation=meta.get("formation_id"),
                hazard=meta.get("hazard", "none"),
                event_type=meta.get("event_type", "unknown"),
                raw_text=res['document'],
                similarity_score=round(res.get("similarity") or 0.0, 3),
                citation_id=f"[{meta.get('well_id', 'Unknown')} - {meta.get('event_type', 'EVT')} - {meta.get('depth_m', 0)}m]"
            ))

        return analog_wells, evidence_items
