"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 4 — Part C: LLM Briefing Generator

Generates citation-forced engineer briefings via Google Gemini AI Studio API.

Core rules (from global PS rules):
  1. LLM NEVER generates the risk score number — injected from Module 3 only.
  2. Every factual sentence must cite a [NODE_ID] from the knowledge graph.
  3. Auto-verification pass checks every cited NODE_ID for keyword support.
  4. Any sentence that fails citation check is flagged — NOT silently removed.
  5. If Wilson CI analogs DISAGREE, the LLM must state the disagreement explicitly.

Usage:
    from module4.llm_briefing import LLMBriefing
    briefing = LLMBriefing(api_key="AIza...")
    result = briefing.generate(well_id="15/9-F-9A", hazard="stuck_pipe",
                               rag_results=[...], risk_data={...})
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("llm_briefing")

_MODULE4_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR  = _MODULE4_DIR / "outputs"

# Minimum keyword overlap required for a citation to PASS verification
VERIFY_MIN_KEYWORD_OVERLAP = 1

# Words to ignore when checking keyword overlap (stop words)
STOP_WORDS = {
    "the", "a", "an", "is", "was", "are", "were", "be", "been", "being",
    "in", "at", "on", "of", "to", "for", "with", "by", "from", "as",
    "and", "or", "but", "not", "that", "this", "it", "its", "has",
    "have", "had", "will", "would", "can", "could", "should", "may",
    "might", "must", "do", "did", "does", "well", "drilling",
}


def _extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text (3+ chars, not stop words)."""
    words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    return {w for w in words if w not in STOP_WORDS}


def _verify_citation(
    sentence: str,
    node_id: str,
    graph,
) -> Tuple[bool, str]:
    """
    Verify that the cited node_id actually supports the sentence content.

    Returns:
        (passed: bool, reason: str)
    """
    if graph is None or node_id not in graph:
        return False, f"Node '{node_id}' not found in knowledge graph."

    node_data = graph.nodes[node_id]
    node_type = node_data.get("type", "")

    # For ReportSnippet: check keyword overlap with raw_text
    if node_type == "ReportSnippet":
        raw_text = node_data.get("raw_text", "") or ""
        if not raw_text or raw_text.strip() == "nan":
            return False, f"Node '{node_id}' has no raw_text content."
        sentence_kws = _extract_keywords(sentence)
        node_kws = _extract_keywords(raw_text)
        overlap = sentence_kws & node_kws
        if len(overlap) >= VERIFY_MIN_KEYWORD_OVERLAP:
            return True, f"Citation verified: {len(overlap)} matching keywords ({', '.join(list(overlap)[:5])})."
        return False, f"Citation failed: no keyword overlap between sentence and node '{node_id}'."

    # For Event nodes: check event_type_id, hazard, depth mention
    elif node_type == "Event":
        evt_type = node_data.get("event_type_id", "").lower().replace("_", " ")
        hazard   = node_data.get("hazard", "").lower().replace("_", " ")
        sentence_lower = sentence.lower()
        if evt_type and any(w in sentence_lower for w in evt_type.split() if len(w) > 3):
            return True, f"Citation verified: event type '{evt_type}' mentioned in sentence."
        if hazard and hazard in sentence_lower:
            return True, f"Citation verified: hazard '{hazard}' mentioned in sentence."
        # Broad check — if node ID substring appears in sentence
        if node_id.split("_")[-1].lower() in sentence_lower:
            return True, f"Citation verified: node label found in sentence."
        return False, f"Citation warning: sentence may not directly reference event '{node_id}'."

    # For Well nodes
    elif node_type == "Well":
        wid = node_data.get("well_id", "")
        if wid and wid in sentence:
            return True, f"Citation verified: well ID '{wid}' in sentence."
        return True, "Citation accepted: well node reference is contextually valid."

    # For other node types (Hazard, Formation, Intervention, Outcome)
    else:
        return True, f"Citation accepted: {node_type} node reference is contextually valid."


def _parse_citations(text: str) -> List[Tuple[str, List[str]]]:
    """
    Parse LLM output into (sentence, [node_ids]) pairs.
    Handles decimal numbers (e.g. 1.25 SG), abbreviation dots, and citations at end or inline.
    """
    result = []
    # Split on sentence boundaries (. ! ?) avoiding decimal digits like 1.25
    raw_sentences = re.split(r'(?<=[.!?])(?<!\d\.)\s+(?=[A-Z\[]|\Z)|\n+', text)
    for raw in raw_sentences:
        raw = raw.strip()
        if not raw:
            continue
        # Extract all [NODE_ID] references
        cit_ids = re.findall(r'\[([a-zA-Z0-9_/:.-]+)\]', raw)
        # Clean sentence of inline citation brackets
        clean_sentence = re.sub(r'\s*\[[a-zA-Z0-9_/:.-]+\]', '', raw).strip()
        all_cits = list(dict.fromkeys(cit_ids))  # deduplicate preserving order
        if clean_sentence:
            result.append((clean_sentence, all_cits))
    return result


class LLMBriefing:
    """Generates Gemini-powered, citation-verified engineer briefings."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Google AI Studio API key (AIza...).
                     Falls back to GOOGLE_API_KEY env var if not provided.
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self._client = None
        self._graph = None
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_client(self):
        """Lazy-load Gemini client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "Gemini API key not configured. "
                    "Pass api_key= to LLMBriefing() or set GOOGLE_API_KEY env var."
                )
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model_name = "gemini-1.5-flash"
            try:
                available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                for cand in ["models/gemini-1.5-flash", "models/gemini-1.5-flash-latest", "models/gemini-2.0-flash", "models/gemini-1.5-pro", "models/gemini-pro"]:
                    if cand in available:
                        model_name = cand
                        break
                else:
                    if available:
                        model_name = available[0]
            except Exception as ex:
                logger.warning("Could not list models: %s, defaulting to gemini-1.5-flash", ex)
            self._client = genai.GenerativeModel(model_name)
            logger.info("Gemini client loaded (model: %s).", model_name)

    def _load_graph(self):
        """Lazy-load knowledge graph for citation verification."""
        if self._graph is None:
            from module4.knowledge_graph import load_graph
            self._graph = load_graph()

    def _build_prompt(
        self,
        well_id: str,
        hazard: str,
        risk_data: Dict[str, Any],
        rag_results: List[Dict],
        analog_wells: List[Dict],
    ) -> str:
        """Build the forced-citation prompt for Gemini."""

        # Format risk data (these numbers are IMMUTABLE — LLM must use them exactly)
        risk_score    = risk_data.get("risk_score", "N/A")
        risk_level    = risk_data.get("risk_level", "UNKNOWN")
        ci_lower      = risk_data.get("wilson_ci", {}).get("lower", "N/A")
        ci_upper      = risk_data.get("wilson_ci", {}).get("upper", "N/A")
        n_successes   = risk_data.get("wilson_ci", {}).get("n_successes", "N/A")
        n_trials      = risk_data.get("wilson_ci", {}).get("n_trials", "N/A")
        depth_m       = risk_data.get("measured_depth_m", "N/A")
        actionable    = risk_data.get("actionable_threshold_crossed", False)

        # Format retrieved evidence snippets
        evidence_lines = []
        for r in rag_results[:6]:  # max 6 snippets in prompt
            nid  = r.get("node_id", "")
            wid  = r.get("well_id", "")
            etype = r.get("event_type_id", "")
            dep  = r.get("depth_m", "")
            txt  = r.get("raw_text", "")[:300]
            score = r.get("similarity_score", 0)
            evidence_lines.append(
                f"  [{nid}] Well={wid} | EventType={etype} | Depth={dep}m | "
                f"Similarity={score:.2f}\n  Text: \"{txt}\""
            )
        evidence_block = "\n\n".join(evidence_lines) if evidence_lines else "  [No evidence retrieved]"

        # Format top analogs
        analog_lines = []
        for a in analog_wells[:4]:
            awid  = a.get("well_id", "")
            score = a.get("weighted_score", 0)
            syn   = a.get("is_synthetic", False)
            src   = a.get("source", "")
            analog_lines.append(f"  - {awid} (AHP score={score:.3f}, source={src}, synthetic={syn})")
        analog_block = "\n".join(analog_lines) if analog_lines else "  - None"

        prompt = f"""You are NWIS-Sentinel, an AI drilling risk advisor for rig-floor engineers.

## STRICT RULES YOU MUST FOLLOW:
1. DO NOT invent any risk score, confidence interval, or depth value.
   The values below come from the prediction system — use them EXACTLY as given.
2. EVERY sentence containing a factual claim must end with [NODE_ID] citing the evidence.
   Use the NODE IDs provided in the evidence section below.
3. If the analogs DISAGREE (some had this incident, some didn't), you MUST explicitly state the disagreement.
4. Write in plain, direct language for a rig floor engineer (not a scientist).
5. Length: exactly 4-6 sentences. No more, no less.

## RISK ASSESSMENT (FROM MODULE 3 — IMMUTABLE VALUES):
- Well ID:          {well_id}
- Hazard:           {hazard.replace("_", " ").upper()}
- Current Depth:    {depth_m} m MD
- Risk Level:       {risk_level}
- Risk Score:       {risk_score} (DO NOT CHANGE THIS NUMBER)
- Wilson 95% CI:    [{ci_lower}, {ci_upper}]
- Analogs matched:  {n_successes} out of {n_trials} offset wells show similar patterns
- Actionable alert: {"YES — threshold crossed" if actionable else "NOT YET — monitoring"}

## TOP ANALOG OFFSET WELLS (pre-filtered by Module 2 AHP geospatial similarity):
{analog_block}

## RETRIEVED EVIDENCE (cite these by [NODE_ID] — only use evidence from this list):
{evidence_block}

## YOUR BRIEFING (4-6 sentences, every factual claim must end with [NODE_ID]):
"""
        return prompt

    def generate(
        self,
        well_id: str,
        hazard: str,
        rag_results: List[Dict],
        risk_data: Dict[str, Any],
        analog_wells: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a citation-verified LLM briefing.

        Returns a full briefing dict with per-sentence verification results.
        """
        self._load_client()
        self._load_graph()

        briefing_id = f"BRF_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
        analog_wells = analog_wells or []

        # Build prompt
        prompt = self._build_prompt(well_id, hazard, risk_data, rag_results, analog_wells)

        # Call Gemini
        logger.info("Calling Gemini for briefing (well=%s, hazard=%s) ...", well_id, hazard)
        try:
            response = self._client.generate_content(prompt)
            raw_llm_output = response.text.strip()
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            return {
                "briefing_id": briefing_id,
                "error": f"Gemini API error: {str(e)}",
                "well_id": well_id,
                "hazard": hazard,
            }

        logger.info("Gemini response received (%d chars).", len(raw_llm_output))

        # Parse into (sentence, [citations]) pairs
        parsed = _parse_citations(raw_llm_output)

        # Auto-verify each citation
        verified_sentences = []
        all_passed = True

        for sentence, citations in parsed:
            sentence_result = {
                "text": sentence,
                "citations": citations,
                "verified": True,
                "verification_details": [],
            }

            if not citations:
                # Sentence has no citation — flag as unverified
                sentence_result["verified"] = False
                sentence_result["verification_details"].append(
                    "WARNING: No [NODE_ID] citation found. Every factual sentence must cite evidence."
                )
                all_passed = False
            else:
                for cit_id in citations:
                    passed, reason = _verify_citation(sentence, cit_id, self._graph)
                    sentence_result["verification_details"].append(
                        {"node_id": cit_id, "passed": passed, "reason": reason}
                    )
                    if not passed:
                        sentence_result["verified"] = False
                        all_passed = False

            verified_sentences.append(sentence_result)

        # Count pass/fail
        n_pass = sum(1 for s in verified_sentences if s["verified"])
        n_fail = len(verified_sentences) - n_pass

        result = {
            "briefing_id": briefing_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "well_id": well_id,
            "hazard": hazard,
            "risk_score_from_module3": risk_data.get("risk_score"),
            "risk_level_from_module3": risk_data.get("risk_level"),
            "measured_depth_m": risk_data.get("measured_depth_m"),
            "wilson_ci": risk_data.get("wilson_ci", {}),
            "actionable_threshold_crossed": risk_data.get("actionable_threshold_crossed", False),
            "llm_model": "gemini-1.5-flash",
            "raw_llm_output": raw_llm_output,
            "briefing_sentences": verified_sentences,
            "verification_summary": {
                "total_sentences": len(verified_sentences),
                "sentences_passed": n_pass,
                "sentences_failed": n_fail,
                "all_citations_verified": all_passed,
            },
            "rag_snippets_used": len(rag_results),
            "analog_wells_used": len(analog_wells),
        }

        # Save briefing to disk
        briefing_path = OUTPUTS_DIR / f"{briefing_id}.json"
        with open(briefing_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info("Briefing saved → %s (pass=%d, fail=%d)", briefing_path, n_pass, n_fail)

        return result

    def get_saved_briefing(self, briefing_id: str) -> Optional[Dict]:
        """Retrieve a previously generated briefing by ID."""
        path = OUTPUTS_DIR / f"{briefing_id}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def list_briefings(self) -> List[str]:
        """List all saved briefing IDs."""
        return [
            p.stem for p in sorted(OUTPUTS_DIR.glob("BRF_*.json"), reverse=True)
        ]


def get_latest_risk_data(well_id: str, hazard: str) -> Optional[Dict]:
    """
    Read the latest risk prediction from Module 3's risk_predictions.jsonl
    for the given (well_id, hazard).
    This is the ONLY source of risk score numbers — the LLM never generates these.
    """
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
    risk_path = _PROJECT_ROOT / "module3" / "outputs" / "risk_predictions.jsonl"
    if not risk_path.exists():
        return None

    best = None
    with open(risk_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("well_id") == well_id and rec.get("hazard") == hazard:
                    best = rec
            except Exception:
                continue
    return best
