"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 5: ChromaDB seed -> runtime copy tests

The tracked store (vector_store/chroma_db/) is a read-only SEED. Chroma rewrites
chroma.sqlite3 merely by opening it, so the app opens a git-ignored runtime copy
(data/runtime/chroma/) that ensure_runtime_store() creates from the seed on first start.
"""

import hashlib
import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))

from config import CHROMA_COLLECTION, CHROMA_PERSIST_DIR, CHROMA_SEED_DIR  # noqa: E402
from retrieval.vector_store import ensure_runtime_store  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_seed(root: Path) -> Path:
    seed = root / "seed"
    (seed / "segment-uuid").mkdir(parents=True)
    (seed / "chroma.sqlite3").write_bytes(b"SEED-SQLITE")
    (seed / "segment-uuid" / "data_level0.bin").write_bytes(b"SEED-INDEX")
    return seed


def test_runtime_dir_is_separate_from_tracked_seed_by_default():
    assert Path(CHROMA_PERSIST_DIR).resolve() != Path(CHROMA_SEED_DIR).resolve()
    assert Path(CHROMA_PERSIST_DIR).parts[-3:] == ("data", "runtime", "chroma")


def test_first_start_copies_seed_whole_and_leaves_seed_untouched(tmp_path):
    seed = _make_seed(tmp_path)
    before = _sha256(seed / "chroma.sqlite3")
    runtime = tmp_path / "data" / "runtime" / "chroma"

    assert ensure_runtime_store(str(runtime), str(seed)) == runtime
    assert (runtime / "chroma.sqlite3").read_bytes() == b"SEED-SQLITE"
    assert (runtime / "segment-uuid" / "data_level0.bin").read_bytes() == b"SEED-INDEX"
    assert _sha256(seed / "chroma.sqlite3") == before
    # no temp copy dirs left behind
    assert [p.name for p in runtime.parent.iterdir()] == ["chroma"]


def test_existing_runtime_store_is_not_overwritten(tmp_path):
    seed = _make_seed(tmp_path)
    runtime = tmp_path / "runtime"
    ensure_runtime_store(str(runtime), str(seed))
    (runtime / "chroma.sqlite3").write_bytes(b"RUNTIME-MODIFIED")

    ensure_runtime_store(str(runtime), str(seed))
    assert (runtime / "chroma.sqlite3").read_bytes() == b"RUNTIME-MODIFIED"


def test_missing_seed_does_not_crash_or_create_runtime(tmp_path):
    runtime = tmp_path / "runtime"
    assert ensure_runtime_store(str(runtime), str(tmp_path / "no-such-seed")) == runtime
    assert not runtime.exists()  # Chroma itself will create an empty store; Retriever repopulates


def test_runtime_equal_to_seed_is_a_noop(tmp_path):
    seed = _make_seed(tmp_path)
    assert ensure_runtime_store(str(seed), str(seed)) == seed
    assert (seed / "chroma.sqlite3").read_bytes() == b"SEED-SQLITE"


def test_real_seed_opens_via_runtime_copy_without_touching_seed(tmp_path):
    """End to end with the real 2,022-event store: open the COPY, seed bytes must not change."""
    chromadb = pytest.importorskip("chromadb")
    seed_sqlite = Path(CHROMA_SEED_DIR) / "chroma.sqlite3"
    if not seed_sqlite.exists():
        pytest.skip("tracked Chroma seed not present")
    before = _sha256(seed_sqlite)

    runtime = ensure_runtime_store(str(tmp_path / "chroma"), CHROMA_SEED_DIR)
    client = chromadb.PersistentClient(path=str(runtime))
    assert client.get_collection(CHROMA_COLLECTION).count() == 2022
    del client

    assert _sha256(seed_sqlite) == before, "opening the runtime store modified the tracked seed"
