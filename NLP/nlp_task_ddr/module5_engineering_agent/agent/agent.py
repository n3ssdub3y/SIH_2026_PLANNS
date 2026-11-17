import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from config import HF_TOKEN, QWEN_MODEL, GEMINI_API_KEY, GEMINI_MODELS, LLM_TIMEOUT_S, ENV_FILES
from schemas.models import AskRequest, AskResponse, CurrentSituation, EvidenceItem, LLM_PROVIDERS
from retrieval.retriever import Retriever
from .prompts import ENGINEERING_AGENT_SYSTEM_PROMPT, build_context_prompt
from .question import analyse_question, expand_hazards, focus_hazards
from .local_engine import assess_uncertainty, compose_answer, key_facts, out_of_scope_answer

logger = logging.getLogger("module5.agent")

LOCAL_ENGINE = "local-evidence-engine"

# Errors that will not fix themselves on retry: stop calling that provider/model for
# the rest of the process instead of paying the round-trip on every question.
_PERMANENT_AUTH = re.compile(r"\b(401|402|403)\b|payment required|unauthori[sz]ed|permission_denied|leaked|api key not valid", re.I)
_MODEL_GONE = re.compile(r"\b404\b|not_found|no longer available|is not found", re.I)


def _short_err(e: Exception) -> str:
    s = str(e)
    m = re.search(r"\b(4\d\d|5\d\d)\b[^.{]*", s)
    s = m.group(0) if m else s
    return re.sub(r"\s+", " ", s).strip(" .:'\"")[:70]


def _read_env_keys() -> dict:
    """Current HF_TOKEN / GEMINI_API_KEY as on disk (.env files) or in the process env."""
    vals = {"HF_TOKEN": os.environ.get("HF_TOKEN", ""),
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")}
    try:
        from dotenv import dotenv_values
        for f in ENV_FILES:
            if Path(f).exists():
                d = dotenv_values(f)
                if d.get("HF_TOKEN"):
                    vals["HF_TOKEN"] = d["HF_TOKEN"]
                if d.get("GEMINI_API_KEY") or d.get("GOOGLE_API_KEY"):
                    vals["GEMINI_API_KEY"] = d.get("GEMINI_API_KEY") or d.get("GOOGLE_API_KEY")
    except ImportError:
        pass
    return {k: (v or "").strip() for k, v in vals.items()}


class EngineeringAgent:
    def __init__(self):
        self.hf_client = None
        self._hf_token = ""
        self._hf_disabled: Optional[str] = None
        self.gemini_client = None
        self._gemini_key = ""
        self._gemini_disabled: Optional[str] = None
        self._dead_gemini_models: set[str] = set()
        self._set_hf_token(HF_TOKEN)
        self._set_gemini_key(GEMINI_API_KEY)
        self.retriever = Retriever()

    # ── provider clients (rebuilt when a key in .env changes) ────────────────
    def _set_hf_token(self, token: str):
        self._hf_token, self.hf_client, self._hf_disabled = token, None, None
        if not token:
            return
        try:
            from huggingface_hub import InferenceClient
            self.hf_client = InferenceClient(api_key=token, timeout=LLM_TIMEOUT_S)
        except Exception as e:
            logger.warning("Failed to initialize HuggingFace InferenceClient: %s", e)

    def _set_gemini_key(self, key: str):
        self._gemini_key, self.gemini_client, self._gemini_disabled = key, None, None
        if not key:
            return
        try:
            from google import genai
            from google.genai import types
            self.gemini_client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(
                    timeout=int(LLM_TIMEOUT_S * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        except Exception as e:
            logger.warning("Failed to initialize Gemini client: %s", e)

    def refresh_keys(self):
        """Pick up a token/key edited in .env since startup (no gateway restart needed)."""
        keys = _read_env_keys()
        if keys["HF_TOKEN"] != self._hf_token:
            logger.info("HF_TOKEN changed in .env; rebuilding Hugging Face client.")
            self._set_hf_token(keys["HF_TOKEN"])
        if keys["GEMINI_API_KEY"] != self._gemini_key:
            logger.info("GEMINI_API_KEY changed in .env; rebuilding Gemini client.")
            self._set_gemini_key(keys["GEMINI_API_KEY"])
            self._dead_gemini_models.clear()

    def provider_status(self) -> dict:
        def st(client, disabled):
            if disabled:
                return "failing: " + disabled
            return "ready" if client else "no key"
        return {"qwen": st(self.hf_client, self._hf_disabled),
                "gemini": st(self.gemini_client, self._gemini_disabled),
                "local": "ready"}

    # ── formatting for the LLM prompt ────────────────────────────────────────
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
            rec = self.retriever.data_adapter.record_for(e.raw_text)
            part = f"--- {e.citation_id} ---\n"
            part += f"Well: {e.well_id} | Depth: {e.depth} m | Formation: {e.formation or 'Unknown'}\n"
            part += f"Hazard: {e.hazard} | Event: {e.event_type}\n"
            facts = [f"{lbl}: {rec[k]}" for k, lbl in (("npt_hours", "NPT h"), ("volume_lost_bbl", "Lost bbl"),
                                                       ("mud_weight_ppg", "MW ppg")) if rec.get(k)]
            if facts:
                part += " | ".join(facts) + "\n"
            part += f"Evidence:\n{e.raw_text}\n"
            parts.append(part)
        return "\n".join(parts)

    # ── LLM providers ────────────────────────────────────────────────────────
    # Each returns (answer or None, engine label or None, failure notes).
    # force=True: the user picked this provider explicitly, so try it even if an earlier
    # permanent error disabled it (they may have fixed the token since).
    def _try_qwen(self, prompt: str, force: bool = False) -> Tuple[Optional[str], Optional[str], List[str]]:
        if not self.hf_client:
            return None, None, ["Qwen/HF: no HF_TOKEN set"]
        if self._hf_disabled and not force:
            return None, None, [f"Qwen/HF: {self._hf_disabled}"]
        try:
            chat_resp = self.hf_client.chat.completions.create(
                model=QWEN_MODEL,
                messages=[
                    {"role": "system", "content": ENGINEERING_AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1500,
                temperature=0.3,
            )
            text = (chat_resp.choices[0].message.content or "").strip()
            if text:
                self._hf_disabled = None
                return text, f"Qwen ({QWEN_MODEL}) via Hugging Face", []
            return None, None, ["Qwen/HF: empty response"]
        except Exception as e:
            err = _short_err(e)
            if _PERMANENT_AUTH.search(str(e)):
                self._hf_disabled = err
                logger.warning("Disabling Hugging Face provider until its token changes: %s", err)
            return None, None, [f"Qwen/HF: {err}"]

    def _try_gemini(self, prompt: str, force: bool = False) -> Tuple[Optional[str], Optional[str], List[str]]:
        if not self.gemini_client:
            return None, None, ["Gemini: no GEMINI_API_KEY set"]
        if self._gemini_disabled and not force:
            return None, None, [f"Gemini: {self._gemini_disabled}"]
        from google.genai import types
        failures: List[str] = []
        for model in GEMINI_MODELS:
            if model in self._dead_gemini_models:
                continue
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=ENGINEERING_AGENT_SYSTEM_PROMPT,
                        temperature=0.3,
                    ),
                )
                text = (response.text or "").strip()
                if text:
                    self._gemini_disabled = None
                    return text, f"Gemini ({model})", failures
                failures.append(f"Gemini {model}: empty response")
            except Exception as e:
                err = _short_err(e)
                failures.append(f"Gemini {model}: {err}")
                if _PERMANENT_AUTH.search(str(e)):
                    self._gemini_disabled = err
                    logger.warning("Disabling Gemini provider until its key changes: %s", err)
                    break
                if _MODEL_GONE.search(str(e)):
                    self._dead_gemini_models.add(model)
        return None, None, failures or ["Gemini: every configured model is retired (404)"]

    def _call_llm(self, prompt: str, provider: str = "auto") -> Tuple[Optional[str], Optional[str], List[str]]:
        """auto: Qwen -> Gemini. qwen / gemini: only that provider. local: no LLM.
        Returns (None, None, failures) when the caller should use the local engine."""
        if provider == "local":
            return None, None, []
        if provider == "qwen":
            return self._try_qwen(prompt, force=True)
        if provider == "gemini":
            return self._try_gemini(prompt, force=True)
        failures: List[str] = []
        for attempt in (self._try_qwen, self._try_gemini):
            text, engine, fails = attempt(prompt)
            failures += fails
            if text:
                return text, engine, failures
        return None, None, failures

    # ── main entry ───────────────────────────────────────────────────────────
    def ask(self, request: AskRequest) -> AskResponse:
        provider = (request.provider or "auto").lower()
        if provider not in LLM_PROVIDERS:
            provider = "auto"
        self.refresh_keys()
        sit = request.current_situation
        info = analyse_question(request.question)
        focus = focus_hazards(info, sit.hazard if sit else None)

        if not info.in_domain:
            return AskResponse(
                answer=out_of_scope_answer(request.question),
                historical_wells=[], evidence=[], citations=[],
                uncertainty=assess_uncertainty(info, focus, []),
                engine="scope-check",
            )

        analog_wells, evidence = self.retriever.retrieve(
            question=request.question, situation=sit, focus_hazards=focus,
            question_hazards=expand_hazards(info.hazards),
        )

        facts = key_facts(info, focus, sit, analog_wells, evidence, self.retriever.data_adapter)
        focus_str = ", ".join(info.topic_labels) if info.topic_labels else ""
        if focus:
            focus_str = (focus_str + "\n" if focus_str else "") + \
                "Hazards to answer about (store labels): " + ", ".join(focus)
        prompt = build_context_prompt(
            question=request.question,
            situation_str=self._format_situation(sit),
            sequence_str=self._format_sequence(request.event_sequence),
            evidence_str=self._format_evidence(evidence),
            focus_str=focus_str,
            facts_str="\n".join(f"- {f}" for f in facts),
        )
        answer, engine, failures = self._call_llm(prompt, provider)

        if answer is None:
            answer = compose_answer(info, focus, sit, request.event_sequence,
                                    analog_wells, evidence, self.retriever.data_adapter)
            engine = LOCAL_ENGINE
            if failures:
                chosen = {"qwen": "Qwen (Hugging Face) was selected but failed",
                          "gemini": "Gemini was selected but failed"}.get(provider, "LLM unavailable")
                answer += (f"\n\n> *[System Notice]* {chosen} ("
                           + "; ".join(failures[:3])
                           + "). Answer synthesized by the local evidence engine from the retrieved records.")
        elif failures:
            logger.info("Answered by %s after: %s", engine, "; ".join(failures))

        return AskResponse(
            answer=answer,
            historical_wells=analog_wells,
            evidence=evidence,
            uncertainty=assess_uncertainty(info, focus, evidence),
            citations=[e.citation_id for e in evidence],
            engine=engine,
        )
