"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 3: Step 2 — Precursor / Anomaly Detector

Purpose
-------
Detect early abnormal behaviour in the live telemetry stream that may act
as a precursor to one of the five named drilling hazards:
    mud_loss | stuck_pipe | kick | overpressure | torque_spike

Methodology (fully transparent — no black-box models)
------------------------------------------------------
Two independent detectors run on every call, per channel, per hazard:

  1. Rolling Z-score
     ---------------
     z = (x - μ_rolling) / σ_rolling
     Window : ZSCORE_WINDOW rows  (default 30)
     Threshold : |z| > ZSCORE_THRESHOLD  (default 2.5σ)
     Uses: numpy rolling mean/std computed from the buffer supplied by caller.

  2. CUSUM (Cumulative Sum Control Chart)
     -------------------------------------
     Detects persistent upward or downward drift, even when individual Z-scores
     are below threshold (i.e., slow, sustained deviation).
     S+_n = max(0, S+_{n-1} + (x_n - μ) - k)   [upper CUSUM]
     S-_n = max(0, S-_{n-1} - (x_n - μ) + k)   [lower CUSUM]
     Alarm when S+ > h  or  S- > h
     k = CUSUM_K_SIGMA * σ  (allowance, default 0.5σ)
     h = CUSUM_H_SIGMA * σ  (decision threshold, default 5.0σ)
     State resets after alarm (self-resetting CUSUM).

Hazard → Channel Mapping
------------------------
Each hazard is monitored via 1–2 telemetry channels. The mapping is declared
explicitly in HAZARD_CHANNEL_CONFIG below — no hidden logic.

Output
------
Returns a list of AnomalyAlert dicts. Each alert contains:
  - Which detector fired  (zscore | cusum)
  - Which channel         (exact Volve column name)
  - Which hazard          (from the five named hazards)
  - Computed statistics   (z_score, cusum_s_plus, cusum_s_minus, threshold)
  - Direction             (high | low | both)
  - Severity label        (WARN | ALERT | CRITICAL)
  - Human-readable explanation

Constraints
-----------
  - This module does NOT touch Module 1 or Module 2 logic.
  - It does NOT modify event_type_vocabulary.json or analog_wells.json.
  - It does NOT make network calls.
  - It does NOT use any ML/embedding models.
  - All statistics are derived from the rolling buffer passed in by the caller.
"""

import uuid
import math
import logging
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("anomaly_detector")


# ── Configuration ─────────────────────────────────────────────────────────────

ZSCORE_WINDOW: int = 30          # rows in the rolling window for mean/std
ZSCORE_THRESHOLD: float = 2.5   # |z| threshold for alert
CUSUM_K_SIGMA: float = 0.5      # CUSUM allowance as multiple of σ
CUSUM_H_SIGMA: float = 5.0      # CUSUM decision threshold as multiple of σ
MIN_ROWS_NEEDED: int = 10        # minimum rows in buffer before any detection


# ── Hazard → Channel Mapping ──────────────────────────────────────────────────
#
# Each entry specifies:
#   channel       : exact column name from telemetry CSV
#   direction     : 'high' | 'low' | 'both'
#                   'high'  → alarm only when value is abnormally HIGH
#                   'low'   → alarm only when value is abnormally LOW
#                   'both'  → alarm in either direction
#   hazards       : list of hazards this channel is linked to
#   engineering   : brief rationale (transparency requirement)
#
# Volve column → hazard mapping grounded in SPE literature:
#   Hookload/WOB elevation   → stuck_pipe (overpull)     [SPE-179005]
#   RPM/WOB drop             → torque_spike precursor   [SPE-163420]
#   Mud density drop         → mud_loss / kick onset    [Bourgoyne et al.]
#   ROP slowdown (high s/m)  → stuck_pipe / overpressure [Maidla & Wojtanowicz]

HAZARD_CHANNEL_CONFIG: List[Dict[str, Any]] = [
    {
        "channel": "Corrected Total Hookload kkgf",
        "direction": "high",
        "hazards": ["stuck_pipe"],
        "engineering": (
            "Elevated hookload above rolling baseline indicates overpull — "
            "string mechanically resisting upward motion (stuck_pipe precursor). "
            "[Ref: Maidla & Wojtanowicz 1990; SPE-179005]"
        ),
    },
    {
        "channel": "Averaged WOB kkgf",
        "direction": "both",
        "hazards": ["stuck_pipe", "torque_spike"],
        "engineering": (
            "WOB spike above baseline: excessive formation engagement (stuck_pipe). "
            "WOB drop below baseline with depth increasing: string not advancing (torque_spike precursor). "
            "[Ref: Johancsik et al. 1984; SPE-163420]"
        ),
    },
    {
        "channel": "Average Rotary Speed rpm",
        "direction": "low",
        "hazards": ["torque_spike", "stuck_pipe"],
        "engineering": (
            "RPM drop while on-bottom indicates increased friction or beginning of "
            "rotational stalling — precursor to torque spike or differential sticking. "
            "[Ref: Johancsik et al. 1984]"
        ),
    },
    {
        "channel": "Mud Density In g/cm3",
        "direction": "low",
        "hazards": ["mud_loss", "kick", "overpressure"],
        "engineering": (
            "Mud weight-in decrease could indicate dilution from influx of formation "
            "fluid (kick onset). Sustained low MW-in increases underbalance risk. "
            "[Ref: Bourgoyne et al.; Fertl 1976]"
        ),
    },
    {
        "channel": "Mud Density Out g/cm3",
        "direction": "low",
        "hazards": ["mud_loss", "kick"],
        "engineering": (
            "Mud density-out dropping below density-in is a classic indicator of "
            "gas-cut returns — early warning of kick or total mud loss. "
            "[Ref: Bourgoyne et al.; SPE-171915]"
        ),
    },
    {
        "channel": "Mud Density In g/cm3.1",
        "direction": "low",
        "hazards": ["mud_loss", "overpressure"],
        "engineering": (
            "Secondary mud weight sensor. Corroborates MW-in readings for cross-check "
            "of loss / overpressure conditions. [Ref: SPE-171915]"
        ),
    },
    {
        "channel": "ROPIH s/m",
        "direction": "high",
        "hazards": ["stuck_pipe", "overpressure"],
        "engineering": (
            "ROPIH is seconds-per-metre (inverse of ROP). A HIGH value means slow "
            "drilling — possible formation hardness increase or string not advancing "
            "normally. Persistent high ROPIH precedes stuck pipe events. "
            "[Ref: Maidla & Wojtanowicz 1990]"
        ),
    },
]

# Build a fast lookup: channel → list of channel configs
_CHANNEL_CONFIGS: Dict[str, List[Dict]] = {}
for _cfg in HAZARD_CHANNEL_CONFIG:
    _ch = _cfg["channel"]
    if _ch not in _CHANNEL_CONFIGS:
        _CHANNEL_CONFIGS[_ch] = []
    _CHANNEL_CONFIGS[_ch].append(_cfg)


# ── CUSUM State ───────────────────────────────────────────────────────────────

@dataclass
class CUSUMState:
    """
    Tracks upward (s_plus) and downward (s_minus) CUSUM accumulators
    for a single (channel, hazard) pair. Self-resets after an alarm.
    """
    channel: str
    hazard: str
    s_plus: float = 0.0
    s_minus: float = 0.0
    n_observations: int = 0   # count of rows fed since last reset

    def reset(self) -> None:
        self.s_plus = 0.0
        self.s_minus = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "hazard": self.hazard,
            "s_plus": round(self.s_plus, 4),
            "s_minus": round(self.s_minus, 4),
            "n_observations": self.n_observations,
        }


# ── Anomaly Alert ─────────────────────────────────────────────────────────────

@dataclass
class AnomalyAlert:
    """
    Single anomaly detection result. All fields are set by the detector;
    no external mutation is expected after creation.
    """
    alert_id: str
    row_index: int
    measured_depth_m: Optional[float]
    detector: str           # 'zscore' | 'cusum'
    channel: str            # exact Volve column name
    hazard: str             # one of the five named hazards
    z_score: Optional[float]
    cusum_s_plus: Optional[float]
    cusum_s_minus: Optional[float]
    threshold_used: float
    direction: str          # 'high' | 'low'
    severity_label: str     # 'WARN' | 'ALERT' | 'CRITICAL'
    explanation: str
    rolling_mean: Optional[float] = None
    rolling_std: Optional[float] = None
    current_value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in asdict(self).items()}


# ── Core Detector ─────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Stateful anomaly detector for the live telemetry stream.

    The caller owns the rolling buffer (deque of row dicts from the simulator).
    On each call to `detect(buffer)`, this class:
      1. Extracts numeric values for each monitored channel.
      2. Computes rolling Z-score over the last ZSCORE_WINDOW rows.
      3. Updates CUSUM state for each (channel, hazard) pair.
      4. Returns a list of AnomalyAlert for any threshold violations in the
         most recent row of the buffer.

    CUSUM state is held internally between calls — the caller must NOT reset it
    unless explicitly calling `reset_cusum_state()`.
    """

    def __init__(
        self,
        zscore_window: int = ZSCORE_WINDOW,
        zscore_threshold: float = ZSCORE_THRESHOLD,
        cusum_k_sigma: float = CUSUM_K_SIGMA,
        cusum_h_sigma: float = CUSUM_H_SIGMA,
        min_rows: int = MIN_ROWS_NEEDED,
    ):
        self.zscore_window = zscore_window
        self.zscore_threshold = zscore_threshold
        self.cusum_k_sigma = cusum_k_sigma
        self.cusum_h_sigma = cusum_h_sigma
        self.min_rows = min_rows

        # Internal CUSUM state: key = (channel, hazard)
        self._cusum_states: Dict[Tuple[str, str], CUSUMState] = {}
        self._row_count: int = 0  # total rows fed since creation/reset

        # Pre-initialise CUSUM state objects for all (channel, hazard) pairs
        for cfg in HAZARD_CHANNEL_CONFIG:
            for hazard in cfg["hazards"]:
                key = (cfg["channel"], hazard)
                if key not in self._cusum_states:
                    self._cusum_states[key] = CUSUMState(
                        channel=cfg["channel"], hazard=hazard
                    )

        logger.info(
            "AnomalyDetector initialised. %d channel configs, %d CUSUM states.",
            len(HAZARD_CHANNEL_CONFIG),
            len(self._cusum_states),
        )

    # ── Public API ─────────────────────────────────────────────────────────

    def detect(
        self,
        buffer: List[Dict[str, Any]],
        current_row_index: int = 0,
    ) -> List[AnomalyAlert]:
        """
        Run anomaly detection on the current buffer state.

        Parameters
        ----------
        buffer : list of telemetry row dicts (from TelemetrySimulator)
                 The last item is the CURRENT row to analyse.
                 The earlier items provide the historical window.
        current_row_index : int
                 Row index of the most recent record (for alert metadata).

        Returns
        -------
        List of AnomalyAlert objects (may be empty if nothing detected).
        """
        if len(buffer) < self.min_rows:
            return []

        self._row_count += 1
        alerts: List[AnomalyAlert] = []
        current_row = buffer[-1]  # most recent row
        depth = self._safe_float(current_row.get("Measured Depth m"))

        # Analyse each monitored channel
        for cfg in HAZARD_CHANNEL_CONFIG:
            channel = cfg["channel"]
            direction = cfg["direction"]
            hazards = cfg["hazards"]

            # Extract the time-series values for this channel from the buffer
            values = self._extract_channel_series(buffer, channel)
            if len(values) < self.min_rows:
                continue  # not enough non-null observations in window

            current_val = values[-1]

            # Compute rolling statistics (over last zscore_window valid rows)
            window_vals = values[-self.zscore_window:]
            if len(window_vals) < 3:
                continue
            mu = float(np.mean(window_vals))
            sigma = float(np.std(window_vals, ddof=1))
            if sigma < 1e-9:
                continue  # constant channel — no deviation possible

            # ── Z-score detector ──────────────────────────────────────────
            z = (current_val - mu) / sigma
            zscore_alerts = self._check_zscore(
                z=z,
                mu=mu,
                sigma=sigma,
                current_val=current_val,
                channel=channel,
                direction=direction,
                hazards=hazards,
                row_index=current_row_index,
                depth=depth,
                cfg=cfg,
            )
            alerts.extend(zscore_alerts)

            # ── CUSUM detector ────────────────────────────────────────────
            k = self.cusum_k_sigma * sigma
            h = self.cusum_h_sigma * sigma

            for hazard in hazards:
                key = (channel, hazard)
                state = self._cusum_states[key]
                state.n_observations += 1

                dev = current_val - mu   # deviation from rolling mean
                # Upper CUSUM (detects sustained upward shift)
                s_plus = max(0.0, state.s_plus + dev - k)
                # Lower CUSUM (detects sustained downward shift)
                s_minus = max(0.0, state.s_minus - dev - k)

                state.s_plus = s_plus
                state.s_minus = s_minus

                cusum_alerts = self._check_cusum(
                    state=state,
                    h=h,
                    k=k,
                    mu=mu,
                    sigma=sigma,
                    current_val=current_val,
                    channel=channel,
                    direction=direction,
                    hazard=hazard,
                    row_index=current_row_index,
                    depth=depth,
                    cfg=cfg,
                )
                if cusum_alerts:
                    # Self-reset after alarm (standard CUSUM convention)
                    state.reset()
                alerts.extend(cusum_alerts)

        return alerts

    def reset_cusum_state(self) -> None:
        """Reset all CUSUM accumulators. Call when stream is reset to row 0."""
        for state in self._cusum_states.values():
            state.reset()
        self._row_count = 0
        logger.info("All CUSUM states reset.")

    def get_cusum_state_snapshot(self) -> List[Dict[str, Any]]:
        """Return current CUSUM state for all (channel, hazard) pairs."""
        return [s.to_dict() for s in self._cusum_states.values()]

    def compute_channel_stats(
        self, buffer: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Compute rolling statistics for all monitored channels.
        Used by the REST /api/anomaly/buffer/stats endpoint.
        """
        stats = []
        if len(buffer) < 2:
            return stats

        current_row = buffer[-1]
        depth = self._safe_float(current_row.get("Measured Depth m"))

        for cfg in HAZARD_CHANNEL_CONFIG:
            channel = cfg["channel"]
            values = self._extract_channel_series(buffer, channel)
            if len(values) < 2:
                current_v = self._safe_float(current_row.get(channel))
                stats.append({
                    "channel": channel,
                    "hazards": cfg["hazards"],
                    "direction": cfg["direction"],
                    "n_valid": len(values),
                    "current": round(current_v, 4) if current_v is not None else None,
                    "rolling_mean": None,
                    "rolling_std": None,
                    "z_score": None,
                })
                continue

            window_vals = values[-self.zscore_window:]
            mu = float(np.mean(window_vals))
            sigma = float(np.std(window_vals, ddof=1)) if len(window_vals) > 1 else 0.0
            current_v = values[-1]
            z = ((current_v - mu) / sigma) if sigma > 1e-9 else None

            # Collect CUSUM state for this channel
            cusum_info = []
            for hazard in cfg["hazards"]:
                key = (channel, hazard)
                if key in self._cusum_states:
                    cusum_info.append(self._cusum_states[key].to_dict())

            stats.append({
                "channel": channel,
                "hazards": cfg["hazards"],
                "direction": cfg["direction"],
                "engineering_note": cfg["engineering"],
                "n_valid": len(values),
                "current": round(current_v, 4),
                "rolling_mean": round(mu, 4),
                "rolling_std": round(sigma, 4),
                "z_score": round(z, 4) if z is not None else None,
                "cusum_states": cusum_info,
                "measured_depth_m": depth,
            })

        return stats

    # ── Private Helpers ────────────────────────────────────────────────────

    def _extract_channel_series(
        self, buffer: List[Dict[str, Any]], channel: str
    ) -> List[float]:
        """
        Extract a list of valid (non-null, finite) float values for `channel`
        from the buffer. The buffer order is preserved (oldest → newest).
        """
        values = []
        for row in buffer:
            v = self._safe_float(row.get(channel))
            if v is not None:
                values.append(v)
        return values

    @staticmethod
    def _safe_float(val: Any) -> Optional[float]:
        """Convert a value to float, returning None for null/inf/nan."""
        if val is None:
            return None
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except (TypeError, ValueError):
            return None

    def _check_zscore(
        self,
        z: float,
        mu: float,
        sigma: float,
        current_val: float,
        channel: str,
        direction: str,
        hazards: List[str],
        row_index: int,
        depth: Optional[float],
        cfg: Dict,
    ) -> List[AnomalyAlert]:
        """Generate Z-score alerts for all relevant hazards if threshold exceeded."""
        alerts = []
        should_alarm = False
        alarm_direction = ""

        if direction == "high" and z > self.zscore_threshold:
            should_alarm = True
            alarm_direction = "high"
        elif direction == "low" and z < -self.zscore_threshold:
            should_alarm = True
            alarm_direction = "low"
        elif direction == "both":
            if abs(z) > self.zscore_threshold:
                should_alarm = True
                alarm_direction = "high" if z > 0 else "low"

        if not should_alarm:
            return alerts

        severity = self._z_to_severity(abs(z))
        delta_desc = f"{abs(current_val - mu):.3f} {'above' if alarm_direction == 'high' else 'below'}"

        for hazard in hazards:
            explanation = (
                f"[Z-score] Channel '{channel}' is {abs(z):.2f}σ "
                f"{'above' if alarm_direction == 'high' else 'below'} "
                f"the {self.zscore_window}-row rolling mean "
                f"(mean={mu:.3f}, σ={sigma:.3f}, current={current_val:.3f}, "
                f"Δ={delta_desc}). "
                f"Hazard indicator: {hazard}. "
                f"Engineering basis: {cfg['engineering'][:120]}..."
            )
            alerts.append(AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                row_index=row_index,
                measured_depth_m=depth,
                detector="zscore",
                channel=channel,
                hazard=hazard,
                z_score=round(z, 4),
                cusum_s_plus=None,
                cusum_s_minus=None,
                threshold_used=self.zscore_threshold,
                direction=alarm_direction,
                severity_label=severity,
                explanation=explanation,
                rolling_mean=round(mu, 4),
                rolling_std=round(sigma, 4),
                current_value=round(current_val, 4),
            ))

        return alerts

    def _check_cusum(
        self,
        state: CUSUMState,
        h: float,
        k: float,
        mu: float,
        sigma: float,
        current_val: float,
        channel: str,
        direction: str,
        hazard: str,
        row_index: int,
        depth: Optional[float],
        cfg: Dict,
    ) -> List[AnomalyAlert]:
        """Generate CUSUM alerts for a single (channel, hazard) pair."""
        alerts = []

        alarm_high = state.s_plus > h and direction in ("high", "both")
        alarm_low = state.s_minus > h and direction in ("low", "both")

        if not alarm_high and not alarm_low:
            return alerts

        if alarm_high:
            alarm_dir = "high"
            cusum_val = state.s_plus
        else:
            alarm_dir = "low"
            cusum_val = state.s_minus

        severity = self._cusum_to_severity(cusum_val, h)
        explanation = (
            f"[CUSUM] Channel '{channel}' sustained {'upward' if alarm_dir == 'high' else 'downward'} drift. "
            f"CUSUM accumulator = {cusum_val:.3f} > decision threshold h = {h:.3f}. "
            f"Rolling mean = {mu:.3f}, σ = {sigma:.3f}, current = {current_val:.3f}. "
            f"This indicates a persistent, slow drift rather than a single spike — "
            f"consistent with early {hazard} onset. "
            f"Engineering basis: {cfg['engineering'][:120]}..."
        )

        alerts.append(AnomalyAlert(
            alert_id=str(uuid.uuid4()),
            row_index=row_index,
            measured_depth_m=depth,
            detector="cusum",
            channel=channel,
            hazard=hazard,
            z_score=None,
            cusum_s_plus=round(state.s_plus, 4),
            cusum_s_minus=round(state.s_minus, 4),
            threshold_used=round(h, 4),
            direction=alarm_dir,
            severity_label=severity,
            explanation=explanation,
            rolling_mean=round(mu, 4),
            rolling_std=round(sigma, 4),
            current_value=round(current_val, 4),
        ))

        return alerts

    @staticmethod
    def _z_to_severity(abs_z: float) -> str:
        """Map |z| to severity label."""
        if abs_z >= 4.0:
            return "CRITICAL"
        elif abs_z >= 3.0:
            return "ALERT"
        return "WARN"

    @staticmethod
    def _cusum_to_severity(cusum_val: float, h: float) -> str:
        """Map CUSUM accumulator magnitude relative to h to severity label."""
        ratio = cusum_val / h if h > 0 else 0
        if ratio >= 2.5:
            return "CRITICAL"
        elif ratio >= 1.5:
            return "ALERT"
        return "WARN"


# ── Module-level convenience ───────────────────────────────────────────────────

def make_detector(**kwargs) -> AnomalyDetector:
    """Factory function — returns a fresh AnomalyDetector with optional overrides."""
    return AnomalyDetector(**kwargs)
