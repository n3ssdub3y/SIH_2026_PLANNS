from typing import List, Dict, Any, Optional

from .vector_store import VectorStore
from ingestion.data_adapter import DataAdapter
from schemas.models import CurrentSituation, EvidenceItem
from config import TOP_K_ANALOGS, TOP_K_EVIDENCE

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

    def retrieve(self, question: str, situation: Optional[CurrentSituation] = None) -> tuple[List[str], List[EvidenceItem]]:
        """
        Main retrieval pipeline:
        1. Get Top-K analog wells from M2 based on situation.
        2. Query Vector Store for relevant evidence, constrained by analog wells if available.
        """
        analog_wells = []
        where_filter = None

        if situation and situation.well_id:
            analog_wells = self.data_adapter.get_top_analog_wells(
                well_id=situation.well_id, 
                hazard=situation.hazard, 
                top_k=TOP_K_ANALOGS
            )
            
            # Constrain search to these wells if any are found
            if analog_wells:
                if len(analog_wells) == 1:
                    where_filter = {"well_id": analog_wells[0]}
                else:
                    where_filter = {"well_id": {"$in": analog_wells}}
        
        # Combine question with situation for better semantic search
        search_query = question
        if situation:
            search_query += f". Context: hazard {situation.hazard}, formation {situation.formation}, depth {situation.depth}m."

        # Search the vector store
        raw_results = self.vector_store.search(
            query=search_query,
            where_filter=where_filter,
            top_k=TOP_K_EVIDENCE
        )

        evidence_items = []
        for res in raw_results:
            meta = res['metadata']
            evidence_items.append(EvidenceItem(
                well_id=meta.get("well_id", "Unknown"),
                depth=meta.get("depth_m"),
                formation=meta.get("formation_id"),
                hazard=meta.get("hazard", "none"),
                event_type=meta.get("event_type", "unknown"),
                raw_text=res['document'],
                citation_id=f"[{meta.get('well_id', 'Unknown')} - {meta.get('event_type', 'EVT')} - {meta.get('depth_m', 0)}m]"
            ))

        return analog_wells, evidence_items
