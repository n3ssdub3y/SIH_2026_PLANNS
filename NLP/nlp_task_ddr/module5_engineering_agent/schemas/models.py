from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class CurrentSituation(BaseModel):
    well_id: Optional[str] = None
    depth: Optional[float] = None
    torque: Optional[float] = None
    wob: Optional[float] = None
    rop: Optional[float] = None
    flow: Optional[float] = None
    pressure: Optional[float] = None
    rpm: Optional[float] = None
    formation: Optional[str] = None
    hazard: Optional[str] = None
    additional_params: Dict[str, Any] = Field(default_factory=dict)

LLM_PROVIDERS = ("auto", "qwen", "gemini", "local")


class AskRequest(BaseModel):
    question: str
    current_situation: Optional[CurrentSituation] = None
    event_sequence: Optional[List[str]] = None
    # "auto" = Qwen -> Gemini -> local; "qwen" / "gemini" = only that LLM (local engine if it fails);
    # "local" = offline evidence engine only, no LLM call.
    provider: str = "auto"

class EvidenceItem(BaseModel):
    well_id: str
    depth: Optional[float] = None
    formation: Optional[str] = None
    hazard: str
    event_type: str
    raw_text: str
    similarity_score: Optional[float] = None
    citation_id: str

class AskResponse(BaseModel):
    answer: str
    historical_wells: List[str]
    evidence: List[EvidenceItem]
    uncertainty: str
    citations: List[str]
    # Which engine wrote `answer`: "Qwen (...) via Hugging Face", "Gemini (<model>)",
    # "local-evidence-engine", or "scope-check" (question rejected as off-topic).
    engine: str = "local-evidence-engine"
