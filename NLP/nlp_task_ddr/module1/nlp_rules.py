"""
Module 1 — deterministic NLP rules (keyword event typing + regex field extraction).

Moved verbatim out of p1_full_pipeline.py so it can be imported without running
the offline pipeline. p1_full_pipeline.py and the hybrid engine (nlp_engine.py)
both import from here; behaviour of extract_entities() is unchanged, so the
committed events.jsonl stays reproducible.
"""
import re
from datetime import datetime

# ═══ CANONICAL EVENT VOCABULARY (v1.0) ══════════════════════════════════════
EVENT_VOCAB = {
    "version":    "1.0",
    "created_by": "P1 NLP Pipeline",
    "timestamp":  datetime.now().isoformat(),
    "event_types": {
        "EVT_MUD_LOSS_PARTIAL":      {"hazard": "mud_loss",    "severity": "medium",   "description": "Partial loss of returns to formation"},
        "EVT_MUD_LOSS_TOTAL":        {"hazard": "mud_loss",    "severity": "critical", "description": "Total loss of returns"},
        "EVT_LCM_APPLIED":           {"hazard": "mud_loss",    "severity": "low",      "description": "LCM pill pumped to cure losses"},
        "EVT_CIRC_RESTORED":         {"hazard": "mud_loss",    "severity": "low",      "description": "Circulation restored after losses"},
        "EVT_STUCK_PIPE":            {"hazard": "stuck_pipe",  "severity": "critical", "description": "String mechanically stuck"},
        "EVT_DIFF_STICKING":         {"hazard": "stuck_pipe",  "severity": "high",     "description": "Differential pressure sticking"},
        "EVT_TIGHT_HOLE":            {"hazard": "stuck_pipe",  "severity": "medium",   "description": "Tight hole during trips"},
        "EVT_JARRING":               {"hazard": "stuck_pipe",  "severity": "medium",   "description": "Jarring operations to free string"},
        "EVT_FISHING":               {"hazard": "stuck_pipe",  "severity": "high",     "description": "Fishing for lost BHA/tools in hole"},
        "EVT_KICK":                  {"hazard": "kick",        "severity": "critical", "description": "Formation fluid influx into wellbore"},
        "EVT_GAS_INFLUX":            {"hazard": "kick",        "severity": "high",     "description": "Gas detected in mud returns"},
        "EVT_BOP_SHUTIN":            {"hazard": "kick",        "severity": "critical", "description": "BOP shut in for well control"},
        "EVT_OVERPRESSURE_DETECTED": {"hazard": "overpressure","severity": "high",     "description": "Abnormal formation pressure encountered"},
        "EVT_TORQUE_UP":             {"hazard": "torque_spike","severity": "medium",   "description": "High or fluctuating torque"},
        "EVT_TORQUE_SPIKE":          {"hazard": "torque_spike","severity": "high",     "description": "Sudden torque spike exceeding limit"},
        "EVT_CEMENTING_FAILURE":     {"hazard": "cementing",   "severity": "high",     "description": "Cement job anomaly or losses during cement"},
        "EVT_WOC":                   {"hazard": "cementing",   "severity": "none",     "description": "Waiting on cement"},
        "EVT_ROUTINE_DRILLING":      {"hazard": "none",        "severity": "none",     "description": "Normal drilling — no hazard"},
    }
}

KEYWORD_EVT = [
    ("total loss",            "EVT_MUD_LOSS_TOTAL"),
    ("mud loss",              "EVT_MUD_LOSS_PARTIAL"),
    ("loss of returns",       "EVT_MUD_LOSS_PARTIAL"),
    ("lost circulation",      "EVT_MUD_LOSS_PARTIAL"),
    ("lcm",                   "EVT_LCM_APPLIED"),
    ("circ restored",         "EVT_CIRC_RESTORED"),
    ("differential sticking", "EVT_DIFF_STICKING"),
    ("stuck pipe",            "EVT_STUCK_PIPE"),
    ("stuck",                 "EVT_STUCK_PIPE"),
    ("jarred",                "EVT_JARRING"),
    ("fishing",               "EVT_FISHING"),
    ("tight hole",            "EVT_TIGHT_HOLE"),
    ("tight spot",            "EVT_TIGHT_HOLE"),
    ("overpull",              "EVT_TIGHT_HOLE"),
    ("gas influx",            "EVT_GAS_INFLUX"),
    ("shut in",               "EVT_BOP_SHUTIN"),
    ("well control",          "EVT_BOP_SHUTIN"),
    ("kick",                  "EVT_KICK"),
    ("overpressure",          "EVT_OVERPRESSURE_DETECTED"),
    ("torque spike",          "EVT_TORQUE_SPIKE"),
    ("high torque",           "EVT_TORQUE_UP"),
    ("torque",                "EVT_TORQUE_UP"),
    ("cement failure",        "EVT_CEMENTING_FAILURE"),
    ("waiting on cement",     "EVT_WOC"),
    ("woc",                   "EVT_WOC"),
]

# Record keys, in the exact order every downstream module expects.
EVENT_RECORD_KEYS = (
    "well_id", "event_id", "report_date", "depth_m", "formation_id",
    "mud_weight_ppg", "npt_hours", "volume_lost_bbl", "event_type_id",
    "hazard", "severity", "source", "is_synthetic", "confidence", "raw_text",
)


def classify_event(text):
    t = text.lower()
    for kw, evt in KEYWORD_EVT:
        if kw in t:
            return evt
    return "EVT_ROUTINE_DRILLING"


def matched_keyword(text):
    """Return the (keyword, event_type_id) pair classify_event() would use, or None."""
    t = text.lower()
    for kw, evt in KEYWORD_EVT:
        if kw in t:
            return kw, evt
    return None


def extract_entities(text, well_id, date, source):
    t = str(text) if text else ""
    depths   = re.findall(r"(\d[\d,]*)\s*(?:m\b|mTVD|mMD|meters?)", t, re.I)
    depth_m  = float(depths[0].replace(",","")) if depths else 0.0
    mw_h     = re.search(r"(\d+\.?\d*)\s*(?:ppg|sg\b|SG\b|pcf)", t, re.I)
    mud_ppg  = float(mw_h.group(1)) if mw_h else None
    npt_h    = re.search(r"npt[\s:]*(\d+\.?\d*)\s*h", t, re.I)
    npt_hrs  = float(npt_h.group(1)) if npt_h else 0.0
    vol_h    = re.search(r"(\d+\.?\d*)\s*bbl", t, re.I)
    vol_bbl  = float(vol_h.group(1)) if vol_h else 0.0
    fm_hits  = re.findall(r"(Hordaland|Shetland|Draupne|Utsira|Statfjord|Smith|Lista|Lyr|Skagerrak|Balder|Heimdal|Rogaland)", t, re.I)
    fm       = fm_hits[0] if fm_hits else "Unknown"
    evt_id   = classify_event(t)
    evt_info = EVENT_VOCAB["event_types"].get(evt_id, {})
    return {
        "well_id":         well_id,
        "event_id":        f"{well_id}_{date}_{evt_id}",
        "report_date":     date,
        "depth_m":         depth_m,
        "formation_id":    fm,
        "mud_weight_ppg":  mud_ppg,
        "npt_hours":       npt_hrs,
        "volume_lost_bbl": vol_bbl,
        "event_type_id":   evt_id,
        "hazard":          evt_info.get("hazard", "none"),
        "severity":        evt_info.get("severity", "none"),
        "source":          source,
        "is_synthetic":    source == "synthetic",
        "confidence":      0.85 if evt_id != "EVT_ROUTINE_DRILLING" else 0.95,
        "raw_text":        t[:400],
    }
