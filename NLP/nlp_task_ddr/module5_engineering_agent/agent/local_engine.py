"""
Local evidence engine for Module 5: deterministic answers when no LLM is reachable.

Every statement is computed from the retrieved evidence or from Module 1 event
records. Nothing is invented, and each list item carries its citation. The answer is
shaped by the question (see agent/question.py): it reports only the statistics the
engineer asked for, extracts the interventions recorded in the evidence, and says so
plainly when the evidence does not cover the question.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from schemas.models import CurrentSituation, EvidenceItem
from .question import HAZARD_DISPLAY, QuestionInfo, expand_hazards

_INTERVENTION_RE = re.compile(
    r"pump|spot|\bjar|work(ed|ing)? (the )?(pipe|string)|circulat|ream|raise|increas|reduc|cut back"
    r"|shut[\s-]?in|\bkill|\blcm\b|\bpill|freed|wash|sweep|squeeze|driller'?s? method|weight(ed)? up"
    r"|bullhead|plug|cured|static|regain|pooh|pull(ed)? out|backoff|back off|fish",
    re.I,
)
_KILL_MUD_RE = re.compile(r"(\d+(?:\.\d+)?)\s*SG kill mud", re.I)
_MW_RAISED_RE = re.compile(r"MW (?:raised|increased) to (\d+(?:\.\d+)?)\s*SG", re.I)

MAX_EVIDENCE_LINES = 5
MAX_INTERVENTIONS = 6


# ── helpers ───────────────────────────────────────────────────────────────────
def _clean(text: str) -> str:
    return (text or "").replace("�", "-").replace("\n", " ").strip()


def _snippet(text: str, n: int = 220) -> str:
    t = _clean(text)
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z])", _clean(text)) if s.strip()]


def wilson_ci(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def _fmt_range(vals: List[float], unit: str) -> str:
    vals = sorted(vals)
    med = statistics.median(vals)
    if len(vals) == 1:
        return f"{vals[0]:g} {unit}"
    return f"median {med:.1f} {unit} (range {vals[0]:g}–{vals[-1]:g} {unit}, n={len(vals)})"


def relevant_evidence(info: QuestionInfo, focus: List[str], evidence: List[EvidenceItem]) -> List[EvidenceItem]:
    """Evidence that bears on the question: records of the hazards the question names; else of the
    focus hazards (question + panel); else any non-routine record."""
    q_haz = set(expand_hazards(info.hazards))
    if q_haz:
        hits = [e for e in evidence if e.hazard in q_haz]
        if hits:
            return hits
    if focus:
        return [e for e in evidence if e.hazard in set(focus)]
    return [e for e in evidence if e.hazard != "none"]


def hazard_label(h: Optional[str]) -> str:
    if not h:
        return "General Drilling"
    return HAZARD_DISPLAY.get(h, h.replace("_", " ").title())


# ── uncertainty (shared with the LLM path) ────────────────────────────────────
def assess_uncertainty(info: QuestionInfo, focus: List[str], evidence: List[EvidenceItem]) -> str:
    if not info.in_domain:
        return "N/A. Question is outside the drilling-operations scope of this agent."
    if not evidence:
        return "High. No matching historical evidence retrieved."
    relevant = relevant_evidence(info, focus, evidence)
    n = len(relevant)
    synth = sum(1 for e in relevant if e.well_id.upper().startswith("SYNTH"))
    wells = len({e.well_id for e in relevant})
    if focus and n == 0:
        return (f"High. None of the {len(evidence)} retrieved records is a "
                f"{' / '.join(hazard_label(h) for h in focus[:2])} event; evidence is only loosely related.")
    level = "Low to Medium" if n >= 8 and wells >= 3 else "Medium" if n >= 3 else "High"
    msg = f"{level}. {n} directly relevant record{'s' if n != 1 else ''} from {wells} well{'s' if wells != 1 else ''}"
    if n and synth == n:
        msg += "; all are synthetic offset records, so treat figures as indicative"
    elif synth:
        msg += f" ({synth} synthetic)"
    return msg + "."


# ── main entry point ──────────────────────────────────────────────────────────
def out_of_scope_answer(question: str) -> str:
    return "\n".join([
        "### Outside the Engineering Agent's scope",
        f"\"{_snippet(question, 120)}\" doesn't look like a drilling-operations question, "
        "so no offset-well evidence was retrieved.",
        "",
        "I answer from historical DDR events and offset-well analogs. For example:",
        "- *What interventions freed the pipe in analog wells with tight hole and rising torque?*",
        "- *How much mud was typically lost before circulation was regained?*",
        "- *What kill mud weights were used after gas influx in this formation?*",
        "- *What is the most common hazard in the next 300 m, and its typical NPT?*",
    ])


def compose_answer(
    info: QuestionInfo,
    focus: List[str],
    situation: Optional[CurrentSituation],
    sequence: Optional[List[str]],
    analog_wells: List[str],
    evidence: List[EvidenceItem],
    data_adapter,
) -> str:
    focus_set = set(focus)
    primary = focus[0] if focus else None
    if "frequency" in info.intents and not info.hazards:
        title = "Hazard Outlook"
    else:
        title = hazard_label(primary) if primary else "Offset-Well Evidence Review"
    lines: List[str] = [f"### Engineering Assessment — {title}"]

    topics = info.topic_labels
    if topics:
        lines.append(f"**Question focus:** {', '.join(topics)}")

    # Situation — only the fields that were provided
    if situation:
        sit = []
        if situation.well_id:
            sit.append(f"well {situation.well_id}")
        if situation.depth:
            sit.append(f"{situation.depth:g} m")
        if situation.formation and situation.formation.lower() != "unknown":
            sit.append(f"{situation.formation}")
        params = [f"{n} {v:g}{u}" for n, v, u in (
            ("torque", situation.torque, " kNm"), ("WOB", situation.wob, " kN"),
            ("ROP", situation.rop, " m/hr"), ("flow", situation.flow, " L/min"),
            ("pressure", situation.pressure, " bar"), ("RPM", situation.rpm, "")) if v]
        if sit or params:
            s = "**Situation:** " + ", ".join(sit)
            if params:
                s += ("; " if sit else "") + ", ".join(params)
            lines.append(s + ".")
    if sequence:
        lines.append(f"**Recent event sequence:** {' → '.join(sequence)}.")
    lines.append("")

    relevant = relevant_evidence(info, focus, evidence)
    if not focus_set and not relevant:
        relevant = list(evidence)
    shown = relevant[:MAX_EVIDENCE_LINES]

    # Historical evidence
    if not evidence:
        lines.append("**Historical evidence:** No offset-well events were retrieved for this question.")
    elif focus_set and not relevant:
        names = " / ".join(hazard_label(h) for h in focus[:2])
        lines.append(f"**Historical evidence:** None of the {len(evidence)} retrieved records is a "
                     f"{names} event, so the store does not support a direct answer. Closest records:")
        for i, e in enumerate(evidence[:3], 1):
            lines.append(f"{i}. {e.citation_id} {_snippet(e.raw_text, 160)}")
    else:
        wells = sorted({e.well_id for e in relevant})
        lines.append(f"**Historical evidence ({len(relevant)} matching record{'s' if len(relevant) != 1 else ''}"
                     f" from {len(wells)} well{'s' if len(wells) != 1 else ''}):**")
        for i, e in enumerate(shown, 1):
            depth = f" at {e.depth:g} m" if e.depth else ""
            fm = f" in {e.formation}" if e.formation and e.formation.lower() not in ("unknown", "") else ""
            kind = e.event_type.replace('EVT_', '').replace('_', ' ').title()
            if e.event_type == "EVT_ROUTINE_DRILLING" and e.hazard not in ("none", ""):
                kind = hazard_label(e.hazard)   # e.g. cementing records typed as routine drilling
            lines.append(f"{i}. {e.citation_id} {kind}{depth}{fm}: {_snippet(e.raw_text)}")
    if analog_wells:
        lines.append(f"\n**Analog wells (Module 2 AHP ranking):** {', '.join(analog_wells)}.")
    lines.append("")

    records = [(e, data_adapter.record_for(e.raw_text)) for e in relevant]

    # Statistics, only for what was asked
    stats = _statistics(info, focus, situation, analog_wells, records, data_adapter)
    if stats:
        lines.append("**What the records show:**")
        lines.extend(f"- {s}" for s in stats)
        lines.append("")

    # Interventions, extracted verbatim from the evidence
    if relevant and ("interventions" in info.intents or not stats):
        iv = _interventions(relevant, primary)
        if iv:
            lines.append("**Interventions and outcomes recorded in these cases:**")
            lines.extend(f"- {s}" for s in iv)
        elif "interventions" in info.intents:
            lines.append("**Interventions:** The retrieved records don't describe the remedial action taken.")
        lines.append("")

    return "\n".join(lines).rstrip()


def key_facts(info: QuestionInfo, focus: List[str], situation: Optional[CurrentSituation],
              analog_wells: List[str], evidence: List[EvidenceItem], data_adapter) -> List[str]:
    """The computed figures the question asks for (NPT, volume, mud weight, base rate,
    hazard frequency). Also handed to the LLM so it doesn't have to do arithmetic."""
    relevant = relevant_evidence(info, focus, evidence)
    records = [(e, data_adapter.record_for(e.raw_text)) for e in relevant]
    return _statistics(info, focus, situation, analog_wells, records, data_adapter)


def _statistics(info, focus, situation, analog_wells, records, data_adapter) -> List[str]:
    out: List[str] = []
    focus_set = set(focus)
    label = " / ".join(hazard_label(h) for h in focus[:1]) or "these"

    # Population for rate/frequency questions: the analog wells' full event history
    pop = data_adapter.events_for_wells(analog_wells) if analog_wells else []
    pop_name = f"the {len(analog_wells)} analog wells" if pop else ""
    if pop and situation and situation.depth and info.lookahead_m:
        lo, hi = situation.depth, situation.depth + info.lookahead_m
        windowed = [e for e in pop if lo <= float(e.get("depth_m") or 0) <= hi]
        if windowed:
            pop, pop_name = windowed, f"the analog wells between {lo:g} and {hi:g} m"
        else:
            out.append(f"No analog-well events are recorded between {lo:g} and {hi:g} m; "
                       f"figures below use the analog wells' full depth range.")

    if "probability" in info.intents and focus_set:
        if pop:
            nonroutine = [e for e in pop if e.get("hazard", "none") != "none"]
            k = sum(1 for e in nonroutine if e.get("hazard") in focus_set)
            n = len(nonroutine)
            if n:
                lo_ci, hi_ci = wilson_ci(k, n)
                out.append(f"In {pop_name}, {k} of {n} recorded non-routine events ({k / n:.0%}, "
                           f"Wilson 95% CI {lo_ci:.0%}–{hi_ci:.0%}) were {label} events. This is a historical "
                           f"base rate, not a calibrated escalation probability; the live risk score comes from Module 3.")
        else:
            out.append("No analog wells are available for this well, so no base rate can be computed; "
                       "use the Module 3 live risk score.")

    if "frequency" in info.intents and pop:
        cnt = Counter(e.get("hazard") for e in pop if e.get("hazard", "none") != "none")
        if cnt:
            top = ", ".join(f"{hazard_label(h)} ({c})" for h, c in cnt.most_common(3))
            out.append(f"Most frequent hazards in {pop_name}: {top}.")
            if "npt" in info.intents:
                h0 = cnt.most_common(1)[0][0]
                npt = [float(e["npt_hours"]) for e in pop if e.get("hazard") == h0 and e.get("npt_hours")]
                if npt:
                    out.append(f"NPT for {hazard_label(h0)} there: {_fmt_range(npt, 'h')}.")

    recs = [r for _, r in records if r]
    if "npt" in info.intents and not ("frequency" in info.intents and pop):
        npt = [float(r["npt_hours"]) for r in recs if r.get("npt_hours")]
        if npt:
            out.append(f"NPT across the matching records: {_fmt_range(npt, 'h')}.")
        else:
            out.append("The matching records don't report NPT.")

    if "volume" in info.intents:
        vol = [float(r["volume_lost_bbl"]) for r in recs if r.get("volume_lost_bbl")]
        if vol:
            out.append(f"Volume lost per event: {_fmt_range(vol, 'bbl')}.")
        else:
            out.append("The matching records don't report lost volume.")

    if "mud_weight" in info.intents:
        kill = [float(m) for e, _ in records for m in _KILL_MUD_RE.findall(e.raw_text)]
        raised = [float(m) for e, _ in records for m in _MW_RAISED_RE.findall(e.raw_text)]
        mw = [float(r["mud_weight_ppg"]) for r in recs if r.get("mud_weight_ppg")]
        if kill:
            out.append(f"Kill mud weights used: {_fmt_range(kill, 'SG')}.")
        if raised:
            out.append(f"Mud weight raised to: {_fmt_range(raised, 'SG')}.")
        if mw and not kill:
            out.append(f"Mud weight in use at the time: {_fmt_range(mw, 'ppg')}.")
        if not (kill or raised or mw):
            out.append("The matching records don't report mud weights.")
    return out


def _interventions(relevant: List[EvidenceItem], primary: Optional[str] = None) -> List[str]:
    """Remedial-action sentences from the evidence, grouped by wording (numbers ignored).
    Actions from records of the question's primary hazard rank first, then by frequency."""
    groups: Dict[str, Dict[str, Any]] = {}
    for e in relevant:
        for s in _sentences(e.raw_text):
            if not _INTERVENTION_RE.search(s) or len(s) < 8:
                continue
            key = re.sub(r"[\d.,]+", "#", s.lower())
            g = groups.setdefault(key, {"text": s, "cites": [], "n": 0, "primary": False})
            g["n"] += 1
            g["primary"] = g["primary"] or (primary is not None and e.hazard == primary)
            if e.citation_id not in g["cites"]:
                g["cites"].append(e.citation_id)
    ranked = sorted(groups.values(), key=lambda g: (g["primary"], g["n"]), reverse=True)[:MAX_INTERVENTIONS]
    out = []
    for g in ranked:
        seen = f" (seen in {g['n']} records)" if g["n"] > 1 else ""
        out.append(f"{_snippet(g['text'], 160)}{seen} {g['cites'][0]}")
    return out
