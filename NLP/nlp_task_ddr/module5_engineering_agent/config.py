"""
config.py — Module 5: Engineering RAG + LLM Agent
Central configuration. All settings from env vars / .env only.
"""
from __future__ import annotations
import os
from pathlib import Path
_THIS_DIR  = Path(__file__).resolve().parent        # module5_engineering_agent/
_REPO_ROOT = _THIS_DIR.parent                        # nlp_task_ddr/

try:
    from dotenv import load_dotenv
    load_dotenv()
    if (_THIS_DIR / ".env").exists():
        load_dotenv(_THIS_DIR / ".env")
    if (_THIS_DIR / ".config").exists():
        load_dotenv(_THIS_DIR / ".config")
except ImportError:
    pass

# ── Hugging Face / Qwen ───────────────────────────────────────────────────────
HF_TOKEN: str   = os.environ.get("HF_TOKEN", "")
QWEN_MODEL: str = os.environ.get("QWEN_MODEL", "Qwen/Qwen2.5-72B-Instruct")

# ── Gemini (Optional / Fallback) ──────────────────────────────────────────────
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str   = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# ── Paths ─────────────────────────────────────────────────────────────────────

NWIS_DATA_ROOT: Path = Path(os.environ.get("NWIS_DATA_ROOT", str(_REPO_ROOT)))

M1_EVENTS_JSONL       = NWIS_DATA_ROOT / "results" / "module1_outputs" / "events.jsonl"
M1_WELLS_METADATA     = NWIS_DATA_ROOT / "results" / "module1_outputs" / "wells_metadata.json"
M1_FLAGGED_INCIDENTS  = NWIS_DATA_ROOT / "results" / "module1_outputs" / "flagged_real_incidents.json"
M2_ANALOG_WELLS       = NWIS_DATA_ROOT / "module2" / "outputs" / "analog_wells.json"
M2_AHP_WEIGHTS        = NWIS_DATA_ROOT / "module2" / "outputs" / "ahp_weights.json"
M3_RISK_PREDICTIONS   = NWIS_DATA_ROOT / "results" / "module3_outputs" / "risk_predictions.jsonl"
M3_SEQUENCE_MATCHES   = NWIS_DATA_ROOT / "results" / "module3_outputs" / "sequence_matches.json"

# ── Chroma vector store ───────────────────────────────────────────────────────
CHROMA_PERSIST_DIR: str = os.environ.get(
    "CHROMA_PERSIST_DIR", str(_THIS_DIR / "vector_store" / "chroma_db")
)
CHROMA_COLLECTION: str = "nwis_events"

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K_ANALOGS: int  = int(os.environ.get("TOP_K_ANALOGS", "5"))
TOP_K_EVIDENCE: int = int(os.environ.get("TOP_K_EVIDENCE", "10"))

# ── FastAPI ───────────────────────────────────────────────────────────────────
API_HOST: str = os.environ.get("API_HOST", "0.0.0.0")
API_PORT: int = int(os.environ.get("API_PORT", "8502"))

# ── Hazard vocabulary ─────────────────────────────────────────────────────────
HAZARD_LABELS: dict[str, str] = {
    "stuck_pipe":   "Stuck Pipe",
    "mud_loss":     "Mud Loss / Lost Circulation",
    "overpressure": "Overpressure / Kick",
    "torque_spike": "Torque Spike",
    "cementing":    "Cementing Failure",
}
ALL_HAZARDS = list(HAZARD_LABELS.keys())
