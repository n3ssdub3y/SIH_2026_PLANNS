import logging
import os
import shutil
import chromadb
from chromadb.config import Settings
import uuid
from pathlib import Path
from typing import List, Dict, Any

from config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION, CHROMA_SEED_DIR

logger = logging.getLogger("module5.vector_store")


def ensure_runtime_store(
    runtime_dir: str = CHROMA_PERSIST_DIR, seed_dir: str = CHROMA_SEED_DIR
) -> Path:
    """
    Make sure the (git-ignored) runtime Chroma directory exists, seeding it from the
    tracked seed on first use. Opening a Chroma store rewrites chroma.sqlite3 even on
    read-only use, so the app must never open the tracked seed directly.

    The copy goes to a sibling temp dir and is renamed into place, so an interrupted
    copy can never leave a half-populated runtime store that later looks "ready".
    If there is no seed, Chroma creates an empty store and Retriever repopulates it
    from the Module 1 events (existing behaviour).
    """
    runtime, seed = Path(runtime_dir), Path(seed_dir)
    if runtime.resolve() == seed.resolve() or (runtime / "chroma.sqlite3").exists():
        return runtime
    if not (seed / "chroma.sqlite3").exists():
        logger.warning("Chroma seed not found at %s; starting with an empty store.", seed)
        return runtime

    runtime.parent.mkdir(parents=True, exist_ok=True)
    tmp = runtime.with_name(f"{runtime.name}.tmp-{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(seed, tmp)
    try:
        os.replace(tmp, runtime)
    except OSError:
        # Another process won the race (or runtime exists empty); keep whatever is there.
        shutil.rmtree(tmp, ignore_errors=True)
        if not (runtime / "chroma.sqlite3").exists():
            raise
    else:
        logger.info("Seeded runtime Chroma store %s from %s", runtime, seed)
    return runtime


class VectorStore:
    def __init__(self):
        runtime_dir = ensure_runtime_store()
        self.client = chromadb.PersistentClient(path=str(runtime_dir))
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
