import google.genai as genai
from typing import List, Dict, Any, Optional

from config import GEMINI_API_KEY, GEMINI_MODEL
from schemas.models import AskRequest, AskResponse, CurrentSituation, EvidenceItem
from retrieval.retriever import Retriever
from .prompts import ENGINEERING_AGENT_SYSTEM_PROMPT, build_context_prompt

class EngineeringAgent:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.retriever = Retriever()

    def _format_situation(self, sit: Optional[CurrentSituation]) -> str:
        if not sit:
            return "No structured parameters provided."
        
        parts = []
        if sit.well_id: parts.append(f"Well ID: {sit.well_id}")
        if sit.depth: parts.append(f"Depth: {sit.depth} m")
        if sit.formation: parts.append(f"Formation: {sit.formation}")
        if sit.hazard: parts.append(f"Hazard: {sit.hazard}")
        if sit.torque: parts.append(f"Torque: {sit.torque} kNm")
        if sit.wob: parts.append(f"WOB: {sit.wob} kN")
        if sit.rop: parts.append(f"ROP: {sit.rop} m/hr")
        if sit.flow: parts.append(f"Flow: {sit.flow} L/min")
        if sit.pressure: parts.append(f"Pressure: {sit.pressure} bar")
        if sit.rpm: parts.append(f"RPM: {sit.rpm}")
        
        for k, v in sit.additional_params.items():
            parts.append(f"{k.capitalize()}: {v}")
            
        return "\n".join(parts) if parts else "No structured parameters provided."

    def _format_sequence(self, seq: Optional[List[str]]) -> str:
        if not seq:
            return "No sequence provided."
        return " → ".join(seq)

    def _format_evidence(self, evidence: List[EvidenceItem]) -> str:
        if not evidence:
            return "No relevant historical evidence found."
        
        parts = []
        for e in evidence:
            part = f"--- {e.citation_id} ---\n"
            part += f"Hazard: {e.hazard}\n"
            part += f"Formation: {e.formation or 'Unknown'}\n"
            part += f"Evidence:\n{e.raw_text}\n"
            parts.append(part)
        return "\n".join(parts)

    def ask(self, request: AskRequest) -> AskResponse:
        # Retrieve evidence
        analog_wells, evidence = self.retriever.retrieve(
            question=request.question,
            situation=request.current_situation
        )
        
        # Prepare prompt
        situation_str = self._format_situation(request.current_situation)
        sequence_str = self._format_sequence(request.event_sequence)
        evidence_str = self._format_evidence(evidence)
        
        prompt = build_context_prompt(
            question=request.question,
            situation_str=situation_str,
            sequence_str=sequence_str,
            evidence_str=evidence_str
        )
        
        # Call LLM
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=ENGINEERING_AGENT_SYSTEM_PROMPT
                )
            )
            answer = response.text
            
            # Simple heuristic for uncertainty if no evidence
            if not evidence:
                uncertainty = "High. No matching historical evidence retrieved."
            else:
                uncertainty = "Low to Medium. Based on historical data, though sample size varies."

        except Exception as e:
            # Fallback: synthesize evidence-grounded engineering brief directly from retrieved events
            err_msg = str(e)
            hazard_name = (request.current_situation.hazard or "drilling hazard").replace("_", " ").title() if request.current_situation else "Drilling Hazard"
            well_id = request.current_situation.well_id if request.current_situation else "Current Well"
            depth = f"at {request.current_situation.depth} m" if request.current_situation and request.current_situation.depth else ""
            
            lines = [
                f"### Operational Engineering Assessment — {hazard_name}",
                f"**Well Evaluation:** {well_id} {depth}.",
                ""
            ]
            
            if evidence:
                lines.append(f"**Retrieved Historical Analog Evidence ({len(evidence)} records):**")
                for idx, ev in enumerate(evidence[:5], 1):
                    lines.append(f"{idx}. **{ev.citation_id}**: {ev.raw_text}")
                lines.append("")
                lines.append(f"**Analog Wells Analyzed:** {', '.join(analog_wells) if analog_wells else 'Regional offset dataset'}.")
                lines.append("")
                lines.append("**Operational Guidance & Historical Interventions:**")
                lines.append("- Review parameters against offset wells above showing similar depth and formation signatures.")
                lines.append("- Implement standard mitigating procedures recorded in analog records before escalating.")
                uncertainty = "Low to Medium. Synthesized directly from verified historical offset records."
            else:
                lines.append("No matching offset well events retrieved for the current filter criteria.")
                uncertainty = "High. Insufficient historical analog data."

            if "leaked" in err_msg.lower() or "permission_denied" in err_msg.lower():
                lines.append(f"\n> *[System Notice]* Gemini API key requires renewal (`{err_msg[:65]}...`). Synthesized via local evidence engine.")
            elif err_msg:
                lines.append(f"\n> *[System Notice]* LLM offline: {err_msg[:65]}... Synthesized via local evidence engine.")

            answer = "\n".join(lines)

        return AskResponse(
            answer=answer,
            historical_wells=analog_wells,
            evidence=evidence,
            uncertainty=uncertainty,
            citations=[e.citation_id for e in evidence]
        )
