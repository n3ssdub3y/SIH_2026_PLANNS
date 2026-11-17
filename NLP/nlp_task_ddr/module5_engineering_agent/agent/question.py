"""
Question understanding for the Module 5 agent (deterministic, no model needed).

Works out what the engineer is asking about (hazards), what they want to know
(interventions, NPT, lost volume, mud weight, likelihood, frequency) and whether
the question is about drilling at all. Both the retriever (to steer the search)
and the local evidence engine (to shape the answer) use the result.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

# Hazard labels as they appear in the event store (Module 1 `hazard` field).
# Module 1 labels well-control events "kick"; the UI/Module 2 call the same family
# "overpressure", so the two are always searched together.
HAZARD_DISPLAY = {
    "stuck_pipe":   "Stuck Pipe",
    "mud_loss":     "Mud Loss / Lost Circulation",
    "kick":         "Kick / Well Control",
    "overpressure": "Overpressure / Kick",
    "torque_spike": "Torque Spike",
    "cementing":    "Cementing",
}
_HAZARD_FAMILY = {
    "kick": ["kick", "overpressure"],
    "overpressure": ["overpressure", "kick"],
}

HAZARD_PATTERNS = {
    "stuck_pipe": r"\bstuck\b|tight (hole|spot)|pack[\s-]?off|overpull|differential(ly)?[\s-]stick"
                  r"|\bjar(s|red|ring)?\b|fishing|free (the )?(pipe|string)|sticking",
    "mud_loss":   r"(?<!time )\bloss(es)?\b|(?<!time )\blost\b(?! (time|hours?|days?)\b)|\blcm\b|thief zone|losing (mud|returns)"
                  r"|flow[\s-]?out (has )?(dropped|decreas)|\breturns\b|circulation (was |is )?regain"
                  r"|regain(ed|ing)? (full )?circulation",
    "kick":       r"\bkicks?\b|influx|pit (gain|volume)|over[\s-]?pressur|shut[\s-]?in\b|\bkill"
                  r"|well control|drilling break|\bsidpp\b|\bsicp\b|\bbop\b",
    "torque_spike": r"\btorque\b|stick[\s-]?slip|vibration",
    "cementing":  r"\bcement|squeeze|\bwoc\b",
}

INTENT_PATTERNS = {
    "interventions": r"interven|what (should|do|can|must) (i|we)|how (do|to|should|can|did|was|were)"
                     r"|handle|resolv|mitigat|\bcure|\bfix|recommend|action|remed|prevent|avoid"
                     r"|what was done|respond|regain|sweep|ream|alter",
    "probability":   r"probab|likel|chance|\bodds\b|escalat|risk of|how risky",
    "npt":           r"\bnpt\b|non[\s-]?productive|downtime|time lost|how long",
    "volume":        r"volume|how much\b.*\blost|\bbbls?\b|barrels?",
    "mud_weight":    r"mud weights?|\bmw\b|kill mud|density|\bsg\b|\bppg\b",
    "frequency":     r"most common|how common|frequen|how often|which hazards?|what hazards?|typical hazards?",
}

# Broad drilling vocabulary: a question with none of these words and no hazard term
# is treated as out of scope ("what's the weather?", "tell me a joke").
_DOMAIN_RE = re.compile(
    r"drill|\bwells?\b|wellbore|\bbit\b|\bbha\b|\bmud\b|formation|depth|\bhole\b|casing|pressure"
    r"|\brop\b|\bwob\b|\brpm\b|\bpump|\brig\b|\becd\b|hazard|\bnpt\b|offset|analog|\btrip"
    r"|ream|circulat|string|\bpipe\b|section|reservoir|shale|sand|limestone|\bddr\b|event"
    r"|lithology|survey|\bbop\b|hydraulic|torque|\bflow\b|\bpit\b|cement|liner|sidetrack"
    r"|kick|loss|stuck|influx|gas|\bsg\b|\bppg\b|\bmw\b|interven|incident|volve|equinor|\bfm\b"
    r"|\b\d+(\.\d+)?\s?m\b|metre|meter|weight|density|geolog|tool|motor|mwd|lwd|log",
    re.I,
)


@dataclass
class QuestionInfo:
    text: str
    hazards: List[str] = field(default_factory=list)      # hazards named in the question
    intents: Set[str] = field(default_factory=set)
    in_domain: bool = True
    lookahead_m: Optional[float] = None                   # "next 300 m" -> 300

    @property
    def topic_labels(self) -> List[str]:
        names = [HAZARD_DISPLAY.get(h, h) for h in self.hazards]
        nice = {"interventions": "interventions", "probability": "likelihood", "npt": "NPT",
                "volume": "lost volume", "mud_weight": "mud weight", "frequency": "hazard frequency"}
        return names + [nice[i] for i in sorted(self.intents)]


def analyse_question(question: str) -> QuestionInfo:
    q = question or ""
    info = QuestionInfo(text=q)
    for hz, pat in HAZARD_PATTERNS.items():
        if re.search(pat, q, re.I):
            info.hazards.append(hz)
    for intent, pat in INTENT_PATTERNS.items():
        if re.search(pat, q, re.I):
            info.intents.add(intent)
    m = re.search(r"next\s+(\d+(?:\.\d+)?)\s*(m|meters?|metres?)\b", q, re.I)
    if m:
        info.lookahead_m = float(m.group(1))
    info.in_domain = bool(info.hazards) or bool(_DOMAIN_RE.search(q))
    return info


def expand_hazards(hazards: List[str]) -> List[str]:
    """Map hazard names to every store label of the same family, preserving order."""
    out: List[str] = []
    for h in hazards:
        for x in _HAZARD_FAMILY.get(h, [h]):
            if x not in out:
                out.append(x)
    return out


def focus_hazards(info: QuestionInfo, situation_hazard: Optional[str]) -> List[str]:
    """Hazards the answer should be about: the question's own first, then the UI focus."""
    base = list(info.hazards)
    if situation_hazard and situation_hazard != "none" and situation_hazard not in base:
        base.append(situation_hazard)
    return expand_hazards(base)
