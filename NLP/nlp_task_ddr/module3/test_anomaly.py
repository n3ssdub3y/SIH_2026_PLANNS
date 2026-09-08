"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 3 — Unit Tests: Anomaly Detector (Step 2)

Tests:
  1. Detector returns no alerts on fewer rows than MIN_ROWS_NEEDED
  2. Z-score alert fires correctly on injected spike
  3. CUSUM alert fires on sustained drift (slow shift, no single z-spike)
  4. Direction filtering: high-direction alert does NOT fire on low deviation
  5. Severity labels are correct (WARN / ALERT / CRITICAL)
  6. CUSUM self-resets after alarm
  7. compute_channel_stats returns all configured channels
  8. reset_cusum_state clears all accumulators
  9. Null values in buffer do not cause crashes

Usage:
    python module3/test_anomaly.py
"""

import sys
import os
import math
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anomaly_detector import AnomalyDetector, HAZARD_CHANNEL_CONFIG, MIN_ROWS_NEEDED


def make_row(depth: float, hookload: float = None, wob: float = None,
             rpm: float = None, mud_in: float = None, mud_out: float = None,
             ropih: float = None) -> dict:
    """Build a minimal telemetry row dict for testing."""
    return {
        "Measured Depth m": depth,
        "Corrected Total Hookload kkgf": hookload,
        "Averaged WOB kkgf": wob,
        "Average Rotary Speed rpm": rpm,
        "Mud Density In g/cm3": mud_in,
        "Mud Density Out g/cm3": mud_out,
        "ROPIH s/m": ropih,
        # Remaining columns — set to None (expected for real Volve data)
        "Corrected Hookload kkgf": None,
        "Total Hookload kkgf": None,
        "MWD Turbine RPM rpm": None,
        "Average Hookload kkgf": None,
        "Lag Depth (TVD) m": None,
        "Total Vertical Depth m": None,
        "Mud Density In g/cm3.1": mud_in,
        "Hole Depth (TVD) m": depth,
    }


def make_steady_buffer(n: int, hookload: float = 100.0, wob: float = 20.0,
                        rpm: float = 120.0, mud_in: float = 1.5, mud_out: float = 1.5,
                        ropih: float = 10.0) -> list:
    """Create a buffer of `n` rows with stable, near-constant values."""
    return [
        make_row(
            depth=float(2000 + i),
            hookload=hookload + (0.1 * (i % 3)),   # tiny noise
            wob=wob + (0.05 * (i % 2)),
            rpm=rpm + (0.2 * (i % 4)),
            mud_in=mud_in,
            mud_out=mud_out,
            ropih=ropih + (0.01 * i),
        )
        for i in range(n)
    ]


class TestAnomalyDetector(unittest.TestCase):

    def setUp(self):
        self.det = AnomalyDetector(zscore_window=20, zscore_threshold=2.5,
                                   cusum_k_sigma=0.5, cusum_h_sigma=5.0, min_rows=10)

    # ── Test 1 ────────────────────────────────────────────────────────────────

    def test_no_alerts_below_min_rows(self):
        """Detector must return [] when buffer has fewer than min_rows entries."""
        buf = make_steady_buffer(5)
        alerts = self.det.detect(buf, current_row_index=5)
        self.assertEqual(alerts, [],
                         "Expected no alerts with only 5 rows in buffer (min=10)")

    # ── Test 2 ────────────────────────────────────────────────────────────────

    def test_zscore_alert_on_hookload_spike(self):
        """
        Inject a severe hookload spike at the last row.
        Expect a Z-score 'stuck_pipe' alert to fire.
        """
        # 30 stable rows at hookload=100
        buf = make_steady_buffer(30, hookload=100.0)
        # Inject spike: hookload = 100 + 15σ ≈ very far above baseline
        # σ ≈ 0.05 for the tiny noise we added; spike of 10 units = ~200σ
        spike_row = make_row(depth=2031.0, hookload=110.0, wob=20.0, rpm=120.0)
        buf.append(spike_row)

        alerts = self.det.detect(buf, current_row_index=30)
        hazards = [a.hazard for a in alerts]
        detectors = [a.detector for a in alerts]

        self.assertIn("stuck_pipe", hazards,
                      f"Expected stuck_pipe z-score alert. Got hazards: {hazards}")
        self.assertIn("zscore", detectors,
                      "Expected at least one zscore alert")

    # ── Test 3 ────────────────────────────────────────────────────────────────

    def test_cusum_fires_on_sustained_drift(self):
        """
        CUSUM should fire on a persistent small upward drift that stays below
        the z-score single-sample threshold.
        """
        det = AnomalyDetector(zscore_window=20, zscore_threshold=10.0,   # very high z threshold → z never fires
                              cusum_k_sigma=0.5, cusum_h_sigma=3.0,      # lower h → CUSUM fires faster
                              min_rows=10)

        # Base: 30 stable rows, hookload=100, σ ≈ 0.05
        buf = make_steady_buffer(30, hookload=100.0)
        alerts_all = []

        # Now add 40 rows with a sustained upward drift (+0.3 each row >> k=0.5*0.05)
        for i in range(40):
            drift_row = make_row(depth=2031.0 + i, hookload=100.3 + 0.2 * i,
                                  wob=20.0, rpm=120.0)
            buf.append(drift_row)
            alerts = det.detect(list(buf), current_row_index=30 + i)
            alerts_all.extend(alerts)

        cusum_alerts = [a for a in alerts_all if a.detector == "cusum"
                        and a.hazard == "stuck_pipe"]
        self.assertTrue(
            len(cusum_alerts) > 0,
            f"Expected CUSUM stuck_pipe alert after sustained drift. Got: {alerts_all}"
        )

    # ── Test 4 ────────────────────────────────────────────────────────────────

    def test_high_direction_does_not_fire_on_low_deviation(self):
        """
        Hookload channel is 'high' direction. A sudden DROP in hookload
        should NOT trigger a stuck_pipe alert.
        """
        buf = make_steady_buffer(30, hookload=100.0)
        # Drop hookload far below baseline
        drop_row = make_row(depth=2031.0, hookload=50.0, wob=20.0, rpm=120.0)
        buf.append(drop_row)

        alerts = self.det.detect(buf, current_row_index=30)
        high_hookload_alerts = [
            a for a in alerts
            if a.channel == "Corrected Total Hookload kkgf" and a.hazard == "stuck_pipe"
        ]
        self.assertEqual(
            len(high_hookload_alerts), 0,
            "Hookload DROP should not trigger stuck_pipe (high-direction only channel)"
        )

    # ── Test 5 ────────────────────────────────────────────────────────────────

    def test_severity_labels(self):
        """Verify severity label logic: WARN / ALERT / CRITICAL."""
        # _z_to_severity tested directly
        self.assertEqual(AnomalyDetector._z_to_severity(2.6), "WARN")
        self.assertEqual(AnomalyDetector._z_to_severity(3.1), "ALERT")
        self.assertEqual(AnomalyDetector._z_to_severity(4.5), "CRITICAL")

        # _cusum_to_severity
        h = 5.0
        self.assertEqual(AnomalyDetector._cusum_to_severity(5.5, h), "WARN")     # 5.5/5 = 1.1
        self.assertEqual(AnomalyDetector._cusum_to_severity(8.0, h), "ALERT")    # 8/5 = 1.6
        self.assertEqual(AnomalyDetector._cusum_to_severity(15.0, h), "CRITICAL")# 15/5 = 3.0

    # ── Test 6 ────────────────────────────────────────────────────────────────

    def test_cusum_self_resets_after_alarm(self):
        """After a CUSUM alarm fires, the accumulator should be reset to 0."""
        det = AnomalyDetector(zscore_window=20, zscore_threshold=10.0,
                              cusum_k_sigma=0.1, cusum_h_sigma=1.0,
                              min_rows=10)
        buf = make_steady_buffer(30, hookload=100.0)
        fired = False
        for i in range(50):
            drift_row = make_row(depth=2031.0 + i, hookload=102.0,
                                  wob=20.0, rpm=120.0)
            buf.append(drift_row)
            alerts = det.detect(list(buf), current_row_index=30 + i)
            if any(a.detector == "cusum" and a.hazard == "stuck_pipe" for a in alerts):
                fired = True
                # Check the CUSUM state was reset
                state = det._cusum_states[("Corrected Total Hookload kkgf", "stuck_pipe")]
                self.assertEqual(state.s_plus, 0.0,
                                 "CUSUM s_plus should be 0 immediately after alarm reset")
                break
        # We expect CUSUM to have fired given the setup
        self.assertTrue(fired, "CUSUM should have fired at some point in this test")

    # ── Test 7 ────────────────────────────────────────────────────────────────

    def test_compute_channel_stats_returns_all_channels(self):
        """compute_channel_stats should return one entry per HAZARD_CHANNEL_CONFIG entry."""
        det = AnomalyDetector()
        buf = make_steady_buffer(30, hookload=100.0, wob=20.0, rpm=120.0,
                                  mud_in=1.5, mud_out=1.5, ropih=10.0)
        stats = det.compute_channel_stats(buf)
        expected_channels = {cfg["channel"] for cfg in HAZARD_CHANNEL_CONFIG}
        returned_channels = {s["channel"] for s in stats}
        self.assertEqual(
            expected_channels, returned_channels,
            f"Missing channels in stats: {expected_channels - returned_channels}"
        )

    # ── Test 8 ────────────────────────────────────────────────────────────────

    def test_reset_clears_cusum_accumulators(self):
        """reset_cusum_state should zero all CUSUM accumulators."""
        det = AnomalyDetector(zscore_window=20, zscore_threshold=10.0,
                              cusum_k_sigma=0.1, cusum_h_sigma=0.01, min_rows=10)
        buf = make_steady_buffer(30, hookload=105.0)  # drift to build up CUSUM
        det.detect(buf, current_row_index=30)

        # Force a non-zero accumulator
        state = det._cusum_states[("Corrected Total Hookload kkgf", "stuck_pipe")]
        state.s_plus = 99.9

        det.reset_cusum_state()
        self.assertEqual(state.s_plus, 0.0, "s_plus should be 0 after reset")
        self.assertEqual(state.s_minus, 0.0, "s_minus should be 0 after reset")

    # ── Test 9 ────────────────────────────────────────────────────────────────

    def test_null_values_do_not_crash(self):
        """Buffer with all-None sensor values should return empty alerts without error."""
        buf = [make_row(depth=float(2000 + i)) for i in range(20)]  # all sensors = None
        try:
            alerts = self.det.detect(buf, current_row_index=20)
        except Exception as e:
            self.fail(f"detect() raised exception on all-null buffer: {e}")
        # No alerts expected since no valid sensor readings
        self.assertEqual(alerts, [], "Expected empty alerts on all-null buffer")


if __name__ == "__main__":
    print("=" * 60)
    print("NWIS-Sentinel Module 3 — Anomaly Detector Unit Tests")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAnomalyDetector)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
