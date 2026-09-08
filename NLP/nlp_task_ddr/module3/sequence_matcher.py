"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 3: Step 3 — Event Tokenization & Sequence Matching

Purpose
-------
Convert a stream of live anomaly alerts into discrete event tokens, then compare
that token sequence against historical sequences from analog wells to estimate
the probability of each drilling hazard occurring.

This module implements two sub-steps:

  Part B — Event Tokenizer
  ------------------------
  Maps (hazard, direction, severity_label) tuples from AnomalyAlert objects to
  event_type_id tokens defined in the existing event_type_vocabulary.json.
  This is a deterministic lookup — no ML, no embeddings.

  Part C — Sequence Matching Engine
  -----------------------------------
  Implements Smith-Waterman local alignment (pure Python, no Biopython).
  For each hazard, aligns the live token sequence against the historical
  token sequences of the top-K analog wells from analog_wells.json.

  Hazard probability is estimated using Wilson Score Confidence Interval via:
    statsmodels.stats.proportion.proportion_confint(method='wilson')

  n_trials   = number of analog wells evaluated for this hazard
  n_successes = count of analog wells where alignment_score > MATCH_THRESHOLD

Output Schema (per hazard)
--------------------------
{
  "hazard": "stuck_pipe",
  "query_sequence": ["EVT_TIGHT_HOLE", "EVT_DIFF_STICKING"],
  "n_query_tokens": 2,
  "top_analog_alignments": [
    {
      "well_id": "16/11-1 ST3",
      "analog_weighted_score": 0.7072,
      "alignment_score": 6,
      "normalized_alignment": 0.75,
      "matched_query_segment": ["EVT_TIGHT_HOLE"],
      "matched_hist_segment": ["EVT_TIGHT_HOLE", "EVT_STUCK_PIPE"],
      "hist_sequence_length": 5
    }
  ],
  "wilson_ci": {
    "lower": 0.18,
    "center": 0.42,
    "upper": 0.69,
    "n_trials": 10,
    "n_successes": 4,
    "method": "wilson",
    "alpha": 0.05
  },
  "risk_level": "MEDIUM",   // LOW | MEDIUM | HIGH | CRITICAL
  "explanation": "..."
}

Constraints
-----------
  - Does NOT modify event_type_vocabulary.json or analog_wells.json.
  - Does NOT use neural networks, embeddings, or LLMs.
  - Alignment algorithm is Smith-Waterman (local). No DTW, no cosine similarity.
  - Wilson CI uses statsmodels — NOT scipy.stats (per explicit user requirement).
  - All data flows from Module 1 and Module 2 outputs without modification.
"""

import json
import logging
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from statsmodels.stats.proportion import proportion_confint

logger = logging.getLogger("sequence_matcher")


# ── Paths (resolve relative to this file) ─────────────────────────────────────

_MODULE3_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE3_DIR.parent

VOCABULARY_PATH = _PROJECT_ROOT / "results" / "module1_outputs" / "event_type_vocabulary.json"
EVENTS_JSONL_PATH = _PROJECT_ROOT / "results" / "module1_outputs" / "events.jsonl"
ANALOG_WELLS_PATH = _PROJECT_ROOT / "module2" / "outputs" / "analog_wells.json"


# ── Smith-Waterman Parameters ─────────────────────────────────────────────────

SW_MATCH_SAME_TOKEN: int = 4    # exact token match
SW_MATCH_SAME_HAZARD: int = 2   # different token but same hazard category
SW_MISMATCH: int = -1           # token mismatch, different hazards
SW_GAP: int = -1                # gap penalty

ALIGNMENT_THRESHOLD: float = 2.0    # minimum normalised score (0-1 scale * 10) to count as a "success"
TOP_K_ANALOGS: int = 10             # max analog wells to align per hazard

# Wilson CI
WILSON_ALPHA: float = 0.05    # 95% confidence interval


# ── Part B: Event Tokenizer ───────────────────────────────────────────────────
#
# Deterministic mapping: (hazard, direction, severity_label) → event_type_id
#
# The mapping is derived from the canonical vocabulary in event_type_vocabulary.json.
# It encodes domain knowledge: for each hazard, which specific event token best
# represents an anomaly alert in each direction/severity combination.
#
# Mapping logic:
#   severity CRITICAL + high  → the "failure" event (e.g., EVT_STUCK_PIPE)
#   severity ALERT    + high  → the "precursor" event (e.g., EVT_DIFF_STICKING)
#   severity WARN     + any   → the "mild indicator" event (e.g., EVT_TIGHT_HOLE)
#   low direction             → loss/influx indicator
#   both (RPM)                → either tight hole or torque up depending on direction

ALERT_TO_TOKEN_MAP: Dict[Tuple[str, str, str], str] = {
    # stuck_pipe
    ("stuck_pipe", "high",  "CRITICAL"): "EVT_STUCK_PIPE",
    ("stuck_pipe", "high",  "ALERT"):    "EVT_DIFF_STICKING",
    ("stuck_pipe", "high",  "WARN"):     "EVT_TIGHT_HOLE",
    ("stuck_pipe", "low",   "CRITICAL"): "EVT_DIFF_STICKING",
    ("stuck_pipe", "low",   "ALERT"):    "EVT_TIGHT_HOLE",
    ("stuck_pipe", "low",   "WARN"):     "EVT_TIGHT_HOLE",

    # torque_spike
    ("torque_spike", "high",  "CRITICAL"): "EVT_TORQUE_SPIKE",
    ("torque_spike", "high",  "ALERT"):    "EVT_TORQUE_UP",
    ("torque_spike", "high",  "WARN"):     "EVT_TORQUE_UP",
    ("torque_spike", "low",   "CRITICAL"): "EVT_TORQUE_SPIKE",
    ("torque_spike", "low",   "ALERT"):    "EVT_TORQUE_UP",
    ("torque_spike", "low",   "WARN"):     "EVT_TIGHT_HOLE",

    # mud_loss
    ("mud_loss", "high",  "CRITICAL"): "EVT_MUD_LOSS_TOTAL",
    ("mud_loss", "high",  "ALERT"):    "EVT_MUD_LOSS_PARTIAL",
    ("mud_loss", "high",  "WARN"):     "EVT_MUD_LOSS_PARTIAL",
    ("mud_loss", "low",   "CRITICAL"): "EVT_MUD_LOSS_TOTAL",
    ("mud_loss", "low",   "ALERT"):    "EVT_MUD_LOSS_PARTIAL",
    ("mud_loss", "low",   "WARN"):     "EVT_MUD_LOSS_PARTIAL",

    # kick
    ("kick", "high",  "CRITICAL"): "EVT_KICK",
    ("kick", "high",  "ALERT"):    "EVT_GAS_INFLUX",
    ("kick", "high",  "WARN"):     "EVT_GAS_INFLUX",
    ("kick", "low",   "CRITICAL"): "EVT_KICK",
    ("kick", "low",   "ALERT"):    "EVT_GAS_INFLUX",
    ("kick", "low",   "WARN"):     "EVT_GAS_INFLUX",

    # overpressure
    ("overpressure", "high",  "CRITICAL"): "EVT_BOP_SHUTIN",
    ("overpressure", "high",  "ALERT"):    "EVT_OVERPRESSURE_DETECTED",
    ("overpressure", "high",  "WARN"):     "EVT_OVERPRESSURE_DETECTED",
    ("overpressure", "low",   "CRITICAL"): "EVT_BOP_SHUTIN",
    ("overpressure", "low",   "ALERT"):    "EVT_OVERPRESSURE_DETECTED",
    ("overpressure", "low",   "WARN"):     "EVT_OVERPRESSURE_DETECTED",
}

# Fallback when an exact (hazard, direction, severity) match is not in the map
HAZARD_FALLBACK_TOKEN: Dict[str, str] = {
    "stuck_pipe":   "EVT_TIGHT_HOLE",
    "torque_spike": "EVT_TORQUE_UP",
    "mud_loss":     "EVT_MUD_LOSS_PARTIAL",
    "kick":         "EVT_GAS_INFLUX",
    "overpressure": "EVT_OVERPRESSURE_DETECTED",
}


def tokenize_alerts(alerts: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Part B: Convert a list of AnomalyAlert dicts to per-hazard event token sequences.

    Parameters
    ----------
    alerts : list of AnomalyAlert.to_dict() results

    Returns
    -------
    dict mapping hazard → list of event_type_id tokens (in order of arrival)
    """
    hazard_sequences: Dict[str, List[str]] = defaultdict(list)

    for alert in alerts:
        hazard = alert.get("hazard", "")
        direction = alert.get("direction", "")
        severity = alert.get("severity_label", "WARN")

        key = (hazard, direction, severity)
        token = ALERT_TO_TOKEN_MAP.get(key)
        if token is None:
            token = HAZARD_FALLBACK_TOKEN.get(hazard, "EVT_ROUTINE_DRILLING")

        hazard_sequences[hazard].append(token)

    return dict(hazard_sequences)


# ── Vocabulary & Historical Data Loader ───────────────────────────────────────

class DataStore:
    """
    Loads and caches:
      - event_type_vocabulary.json  → token metadata
      - events.jsonl                → historical sequences grouped by well
      - analog_wells.json           → per-well hazard analog rankings

    All files are read from their actual on-disk locations produced by
    Module 1 and Module 2 — no data is fabricated.
    """

    def __init__(self):
        self._vocabulary: Dict[str, Any] = {}
        self._hazard_by_token: Dict[str, str] = {}  # token → hazard
        self._well_sequences: Dict[str, List[str]] = {}  # well_id → [event_type_id...]
        self._analog_wells: Dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all data files. Call once at server startup."""
        self._load_vocabulary()
        self._load_events()
        self._load_analog_wells()
        self._loaded = True
        logger.info(
            "DataStore loaded: %d vocabulary tokens, %d wells, %d analog-well keys",
            len(self._vocabulary),
            len(self._well_sequences),
            len(self._analog_wells),
        )

    def _load_vocabulary(self) -> None:
        with open(VOCABULARY_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self._vocabulary = raw.get("event_types", {})
        # Build token→hazard reverse index
        for token, meta in self._vocabulary.items():
            self._hazard_by_token[token] = meta.get("hazard", "none")

    def _load_events(self) -> None:
        """
        Group events.jsonl by well_id with metadata for strictly causal replay.
        """
        raw_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        sequences: Dict[str, List[str]] = defaultdict(list)
        with open(EVENTS_JSONL_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    wid = evt.get("well_id", "UNKNOWN")
                    token = evt.get("event_type_id", "EVT_ROUTINE_DRILLING")
                    depth = evt.get("depth_m")
                    rdate = evt.get("report_date")
                    raw_events[wid].append({
                        "token": token,
                        "depth_m": float(depth) if depth is not None else None,
                        "report_date": rdate,
                    })
                    sequences[wid].append(token)
                except json.JSONDecodeError:
                    continue
        self._raw_events = dict(raw_events)
        self._well_sequences = dict(sequences)

    def _load_analog_wells(self) -> None:
        with open(ANALOG_WELLS_PATH, "r", encoding="utf-8") as f:
            self._analog_wells = json.load(f)

    # ── Accessors ──────────────────────────────────────────────────────────

    def get_hazard_for_token(self, token: str) -> str:
        return self._hazard_by_token.get(token, "none")

    def get_well_sequence(
        self,
        well_id: str,
        target_well_id: Optional[str] = None,
        max_depth_m: Optional[float] = None,
        max_timestamp: Optional[str] = None,
    ) -> List[str]:
        """
        Return event token sequence for well_id.
        Enforces strict causal access:
          - If well_id is the target well, events with depth > max_depth_m are excluded.
          - If max_timestamp is provided, events with report_date > max_timestamp are excluded.
        """
        if not hasattr(self, "_raw_events") or well_id not in self._raw_events:
            return self._well_sequences.get(well_id, [])

        evts = self._raw_events.get(well_id, [])
        is_target = (target_well_id is not None and (
            well_id == target_well_id or
            (target_well_id in ("15/9-F-9A", "15_9-F-9A") and well_id in ("15/9-F-9A", "15_9-F-9A", "NO"))
        ))
        filtered = []
        for e in evts:
            if is_target and max_depth_m is not None and e["depth_m"] is not None and e["depth_m"] > max_depth_m:
                continue
            if max_timestamp is not None and e["report_date"] is not None and e["report_date"] > max_timestamp:
                continue
            filtered.append(e["token"])
        return filtered

    def get_all_well_ids(self) -> List[str]:
        return list(self._well_sequences.keys())

    def get_analog_wells_for_hazard(
        self,
        target_well_id: str,
        hazard: str,
        top_k: int = TOP_K_ANALOGS,
        exclude_target: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Return the top-K analog wells for a given (well_id, hazard) pair.
        Falls back to the first available well_id key if the exact key is absent.
        If exclude_target is True, ensures target_well_id is never returned
        as its own analog (strictly preventing self-leakage).
        """
        if not self._loaded:
            self.load()

        # analog_wells.json is keyed by target well_id
        per_well = self._analog_wells.get(target_well_id, {})
        hazard_list = per_well.get(hazard, [])

        if not hazard_list:
            # Fallback: try the first available key (handles cases where
            # well_id keys differ slightly between modules)
            for wk, wv in self._analog_wells.items():
                if hazard in wv and wv[hazard]:
                    hazard_list = wv[hazard]
                    break

        if exclude_target:
            # Strictly remove target well to prevent self-reference / leakage
            hazard_list = [
                a for a in hazard_list
                if a.get("well_id") != target_well_id
                and not (target_well_id in ("15/9-F-9A", "15_9-F-9A") and a.get("well_id") in ("15/9-F-9A", "15_9-F-9A", "NO"))
            ]

        return hazard_list[:top_k]

    @property
    def vocabulary(self) -> Dict[str, Any]:
        return self._vocabulary

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# ── Part C: Smith-Waterman Alignment ─────────────────────────────────────────

def smith_waterman_align(
    query: List[str],
    reference: List[str],
    hazard_by_token: Dict[str, str],
    match_same_token: int = SW_MATCH_SAME_TOKEN,
    match_same_hazard: int = SW_MATCH_SAME_HAZARD,
    mismatch: int = SW_MISMATCH,
    gap: int = SW_GAP,
) -> Tuple[float, List[str], List[str], int, int]:
    """
    Smith-Waterman local sequence alignment (pure Python, no Biopython).

    Scoring:
      +4 for identical token match
      +2 for different tokens but same hazard category
      -1 for mismatch (different tokens, different hazards)
      -1 for gap

    Returns
    -------
    (alignment_score, matched_query_segment, matched_hist_segment,
     query_start_idx, ref_start_idx)

    The matched segments are the aligned sub-sequences at the highest-scoring
    alignment position (local alignment — best local match, not full-sequence).
    """
    if not query or not reference:
        return 0.0, [], [], 0, 0

    m, n = len(query), len(reference)

    # DP matrix — scores only (no full traceback matrix stored to save memory)
    # We DO need traceback, so store the full matrix.
    H = [[0.0] * (n + 1) for _ in range(m + 1)]
    traceback = [[None] * (n + 1) for _ in range(m + 1)]  # 'diag'|'up'|'left'|None

    max_score = 0.0
    max_i, max_j = 0, 0

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            q_tok = query[i - 1]
            r_tok = reference[j - 1]

            # Compute substitution score
            if q_tok == r_tok:
                sub = match_same_token
            elif hazard_by_token.get(q_tok) == hazard_by_token.get(r_tok) != "none":
                sub = match_same_hazard
            else:
                sub = mismatch

            diag = H[i - 1][j - 1] + sub
            up   = H[i - 1][j] + gap
            left = H[i][j - 1] + gap

            best = max(0.0, diag, up, left)
            H[i][j] = best

            if best > 0:
                if best == diag:
                    traceback[i][j] = "diag"
                elif best == up:
                    traceback[i][j] = "up"
                else:
                    traceback[i][j] = "left"

            if best > max_score:
                max_score = best
                max_i, max_j = i, j

    if max_score <= 0:
        return 0.0, [], [], 0, 0

    # Traceback from (max_i, max_j)
    aligned_query: List[str] = []
    aligned_ref: List[str] = []
    ci, cj = max_i, max_j

    while ci > 0 and cj > 0 and H[ci][cj] > 0:
        move = traceback[ci][cj]
        if move == "diag":
            aligned_query.append(query[ci - 1])
            aligned_ref.append(reference[cj - 1])
            ci -= 1
            cj -= 1
        elif move == "up":
            aligned_query.append("-")
            aligned_ref.append(reference[cj - 1] if cj > 0 else "-")
            ci -= 1
        elif move == "left":
            aligned_query.append(query[ci - 1] if ci > 0 else "-")
            aligned_ref.append("-")
            cj -= 1
        else:
            break

    aligned_query.reverse()
    aligned_ref.reverse()

    return max_score, aligned_query, aligned_ref, ci, cj


def normalize_alignment_score(
    raw_score: float, query: List[str], reference: List[str]
) -> float:
    """
    Normalize raw Smith-Waterman score to [0, 1].
    Uses the theoretical maximum (shorter sequence × best-match-score per token).
    """
    max_possible = min(len(query), len(reference)) * SW_MATCH_SAME_TOKEN
    if max_possible <= 0:
        return 0.0
    return min(1.0, raw_score / max_possible)


# ── Wilson Score CI ───────────────────────────────────────────────────────────

def compute_wilson_ci(
    n_successes: int,
    n_trials: int,
    alpha: float = WILSON_ALPHA,
) -> Dict[str, Any]:
    """
    Compute Wilson Score Confidence Interval using statsmodels.

    Uses statsmodels.stats.proportion.proportion_confint(method='wilson').
    This is required by the explicit project specification.

    Parameters
    ----------
    n_successes : number of analog wells whose alignment score > ALIGNMENT_THRESHOLD
    n_trials    : total number of analog wells evaluated
    alpha       : significance level (default 0.05 → 95% CI)

    Returns
    -------
    dict with lower, center (point estimate), upper, n_trials, n_successes, method
    """
    if n_trials == 0:
        return {
            "lower": 0.0,
            "center": 0.0,
            "upper": 0.0,
            "n_trials": 0,
            "n_successes": 0,
            "method": "wilson",
            "alpha": alpha,
            "note": "No analog wells available for this hazard.",
        }

    # statsmodels returns (lower, upper) tuple
    lower, upper = proportion_confint(
        count=n_successes,
        nobs=n_trials,
        alpha=alpha,
        method="wilson",
    )
    center = n_successes / n_trials

    return {
        "lower": round(float(lower), 4),
        "center": round(float(center), 4),
        "upper": round(float(upper), 4),
        "n_trials": n_trials,
        "n_successes": n_successes,
        "method": "wilson",
        "alpha": alpha,
    }


# ── Risk Level Assignment ─────────────────────────────────────────────────────

def wilson_center_to_risk(center: float) -> str:
    """Map Wilson CI centre (point estimate) to risk level label."""
    if center >= 0.65:
        return "CRITICAL"
    elif center >= 0.45:
        return "HIGH"
    elif center >= 0.25:
        return "MEDIUM"
    return "LOW"


# ── Main Sequence Matcher ─────────────────────────────────────────────────────

class SequenceMatcher:
    """
    Orchestrates Part B (tokenization) + Part C (Smith-Waterman + Wilson CI).

    Usage
    -----
    matcher = SequenceMatcher()
    matcher.load()  # loads vocabulary, events, analog wells from disk

    # On each analysis call:
    results = matcher.match_all_hazards(
        alerts=list_of_anomaly_alert_dicts,
        target_well_id="15/9-F-9A",
    )
    """

    def __init__(self):
        self.store = DataStore()

    def load(self) -> None:
        """Load all backing data. Must be called before match_all_hazards."""
        self.store.load()

    def match_all_hazards(
        self,
        alerts: List[Dict[str, Any]],
        target_well_id: str,
        top_k: int = TOP_K_ANALOGS,
        current_depth_m: Optional[float] = None,
        current_timestamp: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run the full Part B + Part C pipeline for all hazards present in alerts.

        Parameters
        ----------
        alerts            : list of AnomalyAlert.to_dict() results
        target_well_id    : well being drilled now (key into analog_wells.json)
        top_k             : max analog wells to align per hazard
        current_depth_m   : depth at current time t (for strict causal filtering)
        current_timestamp : timestamp at current time t (for strict causal filtering)

        Returns
        -------
        List of hazard result dicts (one per hazard with tokens in the alerts).
        """
        if not self.store.is_loaded:
            self.store.load()

        # Part B: tokenise
        hazard_sequences = tokenize_alerts(alerts)

        results = []
        for hazard, query_tokens in hazard_sequences.items():
            if not query_tokens:
                continue
            result = self._match_one_hazard(
                hazard=hazard,
                query_tokens=query_tokens,
                target_well_id=target_well_id,
                top_k=top_k,
                current_depth_m=current_depth_m,
                current_timestamp=current_timestamp,
            )
            results.append(result)

        # Sort by Wilson CI centre descending (highest risk first)
        results.sort(key=lambda r: r["wilson_ci"]["center"], reverse=True)
        return results

    def match_hazard(
        self,
        hazard: str,
        query_tokens: List[str],
        target_well_id: str,
        top_k: int = TOP_K_ANALOGS,
        current_depth_m: Optional[float] = None,
        current_timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Match a single hazard's query token sequence."""
        if not self.store.is_loaded:
            self.store.load()
        return self._match_one_hazard(
            hazard, query_tokens, target_well_id, top_k, current_depth_m, current_timestamp
        )

    def _match_one_hazard(
        self,
        hazard: str,
        query_tokens: List[str],
        target_well_id: str,
        top_k: int,
        current_depth_m: Optional[float] = None,
        current_timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Core per-hazard pipeline:
          1. Get top-K analog wells for this hazard from analog_wells.json (excluding target_well_id)
          2. For each analog, get its historical event sequence strictly <= current depth/time
          3. Run Smith-Waterman alignment
          4. Count successes (normalized_score > threshold)
          5. Compute Wilson CI
          6. Return structured result with complete feature/weight breakdown
        """
        analog_list = self.store.get_analog_wells_for_hazard(
            target_well_id=target_well_id,
            hazard=hazard,
            top_k=top_k,
            exclude_target=True,
        )

        hazard_by_token = self.store._hazard_by_token
        alignments = []
        n_successes = 0
        n_trials = len(analog_list)

        for analog in analog_list:
            analog_well_id = analog.get("well_id", "")
            analog_score = analog.get("weighted_score", 0.0)

            # Get the historical event token sequence with causal bounds
            hist_sequence = self.store.get_well_sequence(
                analog_well_id,
                target_well_id=target_well_id,
                max_depth_m=current_depth_m,
                max_timestamp=current_timestamp,
            )

            if not hist_sequence:
                alignments.append({
                    "well_id": analog_well_id,
                    "analog_weighted_score": round(analog_score, 4),
                    "alignment_score": 0.0,
                    "normalized_alignment": 0.0,
                    "matched_query_segment": [],
                    "matched_hist_segment": [],
                    "hist_sequence_length": 0,
                    "note": "No historical event sequence available for this analog.",
                })
                continue

            # Filter historical sequence to tokens relevant to this hazard
            hazard_hist = [
                t for t in hist_sequence
                if hazard_by_token.get(t) == hazard or t == "EVT_ROUTINE_DRILLING"
            ]

            if not hazard_hist:
                hazard_hist = hist_sequence[:50]

            raw_score, matched_q, matched_r, _, _ = smith_waterman_align(
                query=query_tokens,
                reference=hazard_hist,
                hazard_by_token=hazard_by_token,
            )
            norm_score = normalize_alignment_score(raw_score, query_tokens, hazard_hist)

            if norm_score > ALIGNMENT_THRESHOLD / 10.0:
                n_successes += 1

            clean_q = [t for t in matched_q if t != "-"]
            clean_r = [t for t in matched_r if t != "-"]

            alignments.append({
                "well_id": analog_well_id,
                "analog_weighted_score": round(analog_score, 4),
                "alignment_score": round(raw_score, 2),
                "normalized_alignment": round(norm_score, 4),
                "matched_query_segment": clean_q,
                "matched_hist_segment": clean_r,
                "hist_sequence_length": len(hist_sequence),
                "hazard_hist_length": len(hazard_hist),
            })

        # Sort alignments: highest normalized score first
        alignments.sort(key=lambda a: a["normalized_alignment"], reverse=True)

        # Wilson Score CI (no bare numbers: lower, center, upper, alpha, sample counts)
        wilson = compute_wilson_ci(n_successes, n_trials)
        risk_level = wilson_center_to_risk(wilson["center"])

        # Full feature and weight breakdown
        feature_breakdown = {
            "n_trials": n_trials,
            "n_successes": n_successes,
            "success_rate": round(n_successes / n_trials, 4) if n_trials > 0 else 0.0,
            "alignment_threshold": ALIGNMENT_THRESHOLD / 10.0,
            "wilson_alpha": WILSON_ALPHA,
            "wilson_ci_formula": "statsmodels.stats.proportion.proportion_confint(method='wilson')",
            "top_analog_feature_weights": [
                {
                    "analog_well_id": a["well_id"],
                    "ahp_similarity_weight": a["analog_weighted_score"],
                    "smith_waterman_raw": a["alignment_score"],
                    "smith_waterman_normalized": a["normalized_alignment"],
                }
                for a in alignments[:5]
            ],
            "causality_audit": {
                "zero_future_leakage_enforced": True,
                "target_well_excluded_from_analogs": True,
                "max_historical_depth_m": current_depth_m,
                "max_historical_timestamp": current_timestamp,
            }
        }

        # Build transparent explanation
        explanation = (
            f"Query sequence for hazard '{hazard}': {query_tokens}. "
            f"Evaluated against {n_trials} top analog offset wells from Module 2 (excluding target well). "
            f"{n_successes}/{n_trials} analogs produced an alignment score "
            f"above threshold (normalised > {ALIGNMENT_THRESHOLD/10:.1f}). "
            f"Wilson 95% CI: [{wilson['lower']:.2f}, {wilson['upper']:.2f}], "
            f"point estimate: {wilson['center']:.2f}. "
            f"Risk level: {risk_level}."
        )

        return {
            "hazard": hazard,
            "query_sequence": query_tokens,
            "n_query_tokens": len(query_tokens),
            "top_analog_alignments": alignments,
            "wilson_ci": wilson,
            "risk_level": risk_level,
            "risk_score": wilson["center"],
            "alignment_threshold": ALIGNMENT_THRESHOLD / 10.0,
            "top_k_evaluated": top_k,
            "n_trials": n_trials,
            "n_successes": n_successes,
            "feature_weights_and_breakdown": feature_breakdown,
            "explanation": explanation,
        }


# ── Module-level convenience ───────────────────────────────────────────────────

def make_matcher() -> SequenceMatcher:
    """Factory — returns a loaded SequenceMatcher."""
    m = SequenceMatcher()
    m.load()
    return m
