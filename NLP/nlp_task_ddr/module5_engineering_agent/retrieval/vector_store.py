import chromadb
from chromadb.config import Settings
import uuid
from typing import List, Dict, Any

from config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION

class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self.collection = self.client.get_or_create_collection(name=CHROMA_COLLECTION)

    def add_events(self, events: List[Dict[str, Any]]):
        """Add events to the vector store."""
        if not events:
            return

        documents = []
        metadatas = []
        ids = []

        for evt in events:
            # We want to embed the raw text, or a constructed summary if raw_text is missing
            raw_text = evt.get('raw_text', '')
            if not raw_text or raw_text.lower() == 'nan':
                # Construct a descriptive text if raw text is missing
                hazard = evt.get('hazard', 'unknown hazard')
                event_type = evt.get('event_type_id', 'unknown event')
                raw_text = f"Event type: {event_type}. Hazard: {hazard}. Occurred at depth {evt.get('depth_m', 'unknown')}m in formation {evt.get('formation_id', 'unknown')}."
            
            # Clean up metadata values to ensure they are primitives (str, int, float, bool)
            metadata = {
                "well_id": str(evt.get("well_id", "")),
                "depth_m": float(evt.get("depth_m", 0.0) or 0.0),
                "formation_id": str(evt.get("formation_id", "")),
                "event_type": str(evt.get("event_type_id", "")),
                "hazard": str(evt.get("hazard", "")),
                "severity": str(evt.get("severity", "")),
                "source": str(evt.get("source", ""))
            }

            documents.append(raw_text)
            metadatas.append(metadata)
            
            # Ensure unique IDs. Sometimes event_id is duplicated or missing.
            event_id = evt.get("event_id")
            if not event_id:
                event_id = f"{evt.get('well_id')}_{uuid.uuid4()}"
            # Even if event_id is present, make absolutely sure it's unique by appending uuid if needed later, but chromadb handles overwrites if ids match
            ids.append(f"{event_id}_{uuid.uuid4()}")

        # Batch insert to avoid size limits
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            self.collection.upsert(
                documents=documents[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )

    def search(self, query: str, where_filter: Dict[str, Any] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search the vector store."""
        
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter
        )

        output = []
        if not results['documents'] or not results['documents'][0]:
            return output
            
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        ids = results['ids'][0]
        
        for idx in range(len(docs)):
            item = {
                "id": ids[idx],
                "document": docs[idx],
                "metadata": metas[idx]
            }
            output.append(item)
            
        return output
