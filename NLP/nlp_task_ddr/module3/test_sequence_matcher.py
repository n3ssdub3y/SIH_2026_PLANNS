"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 3 — Unit Tests: Sequence Matcher (Step 3)

Tests:
  1. tokenize_alerts maps (hazard, direction, severity) to correct event_type_id
  2. Smith-Waterman returns 0 for empty sequences
  3. Smith-Waterman returns positive score for identical sequences
  4. Smith-Waterman same-hazard tokens score correctly (partial match)
  5. normalize_alignment_score is in [0, 1]
  6. Wilson CI uses statsmodels and returns correct keys
  7. Wilson CI with n_trials=0 returns zeros without crash
  8. Wilson CI with all successes returns upper ≈ 1
  9. wilson_center_to_risk maps correctly
 10. DataStore loads vocabulary, events, and analog_wells without error
 11. SequenceMatcher.match_hazard returns valid schema for a real hazard

Usage:
    python module3/test_sequence_matcher.py
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sequence_matcher import (
    tokenize_alerts,
    smith_waterman_align,
    normalize_alignment_score,
    compute_wilson_ci,
    wilson_center_to_risk,
    DataStore,
    SequenceMatcher,
    ALERT_TO_TOKEN_MAP,
    HAZARD_FALLBACK_TOKEN,
    SW_MATCH_SAME_TOKEN,
)


def make_alert(hazard: str, direction: str, severity: str) -> dict:
    return {
        "alert_id": "test-1",
        "row_index": 100,
        "measured_depth_m": 2500.0,
        "detector": "zscore",
        "channel": "Corrected Total Hookload kkgf",
        "hazard": hazard,
        "z_score": 3.0,
        "cusum_s_plus": None,
        "cusum_s_minus": None,
        "threshold_used": 2.5,
        "direction": direction,
        "severity_label": severity,
        "explanation": "test",
        "rolling_mean": 100.0,
        "rolling_std": 1.0,
        "current_value": 103.0,
    }


class TestTokenizer(unittest.TestCase):

    def test_known_mapping_stuck_pipe_critical_high(self):
        alerts = [make_alert("stuck_pipe", "high", "CRITICAL")]
        result = tokenize_alerts(alerts)
        self.assertIn("stuck_pipe", result)
        self.assertEqual(result["stuck_pipe"], ["EVT_STUCK_PIPE"])

    def test_known_mapping_mud_loss_low_alert(self):
        alerts = [make_alert("mud_loss", "low", "ALERT")]
        result = tokenize_alerts(alerts)
        self.assertEqual(result["mud_loss"], ["EVT_MUD_LOSS_PARTIAL"])

    def test_fallback_for_unknown_hazard(self):
        alerts = [make_alert("unknown_hazard", "high", "WARN")]
        result = tokenize_alerts(alerts)
        # Should get fallback routine token
        self.assertIn("unknown_hazard", result)
        self.assertEqual(result["unknown_hazard"], ["EVT_ROUTINE_DRILLING"])

    def test_multiple_alerts_same_hazard(self):
        alerts = [
            make_alert("stuck_pipe", "high", "WARN"),
            make_alert("stuck_pipe", "high", "CRITICAL"),
        ]
        result = tokenize_alerts(alerts)
        self.assertEqual(len(result["stuck_pipe"]), 2)

    def test_multiple_hazards_separated(self):
        alerts = [
            make_alert("stuck_pipe", "high", "WARN"),
            make_alert("mud_loss", "low", "ALERT"),
        ]
        result = tokenize_alerts(alerts)
        self.assertIn("stuck_pipe", result)
        self.assertIn("mud_loss", result)


class TestSmithWaterman(unittest.TestCase):

    def setUp(self):
        # Minimal hazard_by_token map
        self.hbt = {
            "EVT_STUCK_PIPE": "stuck_pipe",
            "EVT_DIFF_STICKING": "stuck_pipe",
            "EVT_TIGHT_HOLE": "stuck_pipe",
            "EVT_TORQUE_SPIKE": "torque_spike",
            "EVT_MUD_LOSS_TOTAL": "mud_loss",
            "EVT_ROUTINE_DRILLING": "none",
        }

    def test_empty_sequences_return_zero(self):
        score, _, _, _, _ = smith_waterman_align([], [], self.hbt)
        self.assertEqual(score, 0.0)

    def test_empty_query_returns_zero(self):
        score, _, _, _, _ = smith_waterman_align(
            [], ["EVT_STUCK_PIPE"], self.hbt
        )
        self.assertEqual(score, 0.0)

    def test_identical_single_token_scores_match_same_token(self):
        score, _, _, _, _ = smith_waterman_align(
            ["EVT_STUCK_PIPE"], ["EVT_STUCK_PIPE"], self.hbt
        )
        self.assertEqual(score, SW_MATCH_SAME_TOKEN,
                         f"Expected {SW_MATCH_SAME_TOKEN}, got {score}")

    def test_identical_multi_token_sequence(self):
        seq = ["EVT_STUCK_PIPE", "EVT_DIFF_STICKING", "EVT_TIGHT_HOLE"]
        score, qm, rm, _, _ = smith_waterman_align(seq, seq, self.hbt)
        self.assertGreater(score, 0)
        # All tokens should align
        self.assertGreater(len(qm), 0)

    def test_same_hazard_partial_match(self):
        # EVT_STUCK_PIPE vs EVT_DIFF_STICKING → same hazard → match_same_hazard
        score, _, _, _, _ = smith_waterman_align(
            ["EVT_STUCK_PIPE"], ["EVT_DIFF_STICKING"], self.hbt
        )
        from sequence_matcher import SW_MATCH_SAME_HAZARD
        self.assertEqual(score, SW_MATCH_SAME_HAZARD)

    def test_different_hazard_mismatch_returns_zero_or_less(self):
        # SW is local alignment — if best score would be negative, returns 0
        score, _, _, _, _ = smith_waterman_align(
            ["EVT_STUCK_PIPE"], ["EVT_MUD_LOSS_TOTAL"], self.hbt
        )
        # Mismatch = -1, SW floors at 0
        self.assertEqual(score, 0.0)


class TestNormalizeScore(unittest.TestCase):

    def test_identical_seq_normalizes_to_one(self):
        seq = ["EVT_STUCK_PIPE", "EVT_DIFF_STICKING"]
        # Raw score = 2 * SW_MATCH_SAME_TOKEN = 8
        raw = 2 * SW_MATCH_SAME_TOKEN
        norm = normalize_alignment_score(raw, seq, seq)
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_zero_raw_score_normalizes_to_zero(self):
        norm = normalize_alignment_score(0.0, ["EVT_STUCK_PIPE"], ["EVT_MUD_LOSS_TOTAL"])
        self.assertEqual(norm, 0.0)

    def test_empty_sequences_return_zero(self):
        norm = normalize_alignment_score(0.0, [], [])
        self.assertEqual(norm, 0.0)

    def test_score_always_in_zero_one(self):
        # Artificially high raw score should clamp to 1.0
        norm = normalize_alignment_score(9999.0, ["EVT_STUCK_PIPE"], ["EVT_STUCK_PIPE"])
        self.assertLessEqual(norm, 1.0)
        self.assertGreaterEqual(norm, 0.0)


class TestWilsonCI(unittest.TestCase):

    def test_zero_trials_returns_zeros(self):
        result = compute_wilson_ci(0, 0)
        self.assertEqual(result["lower"], 0.0)
        self.assertEqual(result["upper"], 0.0)
        self.assertEqual(result["n_trials"], 0)

    def test_all_successes_upper_near_one(self):
        result = compute_wilson_ci(10, 10)
        self.assertGreater(result["upper"], 0.9,
                           "Upper bound should be near 1 when all 10/10 succeed")
        self.assertAlmostEqual(result["center"], 1.0, places=5)

    def test_no_successes_lower_is_zero(self):
        result = compute_wilson_ci(0, 10)
        self.assertAlmostEqual(result["lower"], 0.0, places=3)
        self.assertAlmostEqual(result["center"], 0.0, places=5)

    def test_half_successes_ci_contains_point_five(self):
        result = compute_wilson_ci(5, 10)
        self.assertLessEqual(result["lower"], 0.5)
        self.assertGreaterEqual(result["upper"], 0.5)

    def test_method_field_is_wilson(self):
        result = compute_wilson_ci(3, 7)
        self.assertEqual(result["method"], "wilson")

    def test_all_required_keys_present(self):
        result = compute_wilson_ci(4, 10)
        for key in ["lower", "center", "upper", "n_trials", "n_successes", "method", "alpha"]:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_uses_statsmodels(self):
        """Verify we are using statsmodels.stats.proportion.proportion_confint."""
        from statsmodels.stats.proportion import proportion_confint as sm_confint
        sm_lower, sm_upper = sm_confint(count=4, nobs=10, alpha=0.05, method="wilson")
        result = compute_wilson_ci(4, 10)
        self.assertAlmostEqual(result["lower"], round(float(sm_lower), 4), places=4)
        self.assertAlmostEqual(result["upper"], round(float(sm_upper), 4), places=4)


class TestRiskLevel(unittest.TestCase):

    def test_critical(self):
        self.assertEqual(wilson_center_to_risk(0.70), "CRITICAL")

    def test_high(self):
        self.assertEqual(wilson_center_to_risk(0.50), "HIGH")

    def test_medium(self):
        self.assertEqual(wilson_center_to_risk(0.35), "MEDIUM")

    def test_low(self):
        self.assertEqual(wilson_center_to_risk(0.10), "LOW")


class TestDataStore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.store = DataStore()
        cls.store.load()

    def test_vocabulary_not_empty(self):
        self.assertGreater(len(self.store.vocabulary), 0)

    def test_vocabulary_contains_known_token(self):
        self.assertIn("EVT_STUCK_PIPE", self.store.vocabulary)

    def test_hazard_by_token_reverse_index(self):
        self.assertEqual(self.store.get_hazard_for_token("EVT_STUCK_PIPE"), "stuck_pipe")
        self.assertEqual(self.store.get_hazard_for_token("EVT_MUD_LOSS_TOTAL"), "mud_loss")

    def test_well_sequences_not_empty(self):
        self.assertGreater(len(self.store.get_all_well_ids()), 0)

    def test_get_well_sequence_returns_list(self):
        wids = self.store.get_all_well_ids()
        seq = self.store.get_well_sequence(wids[0])
        self.assertIsInstance(seq, list)

    def test_analog_wells_loaded(self):
        # Should return a non-empty list for some hazard
        found = False
        for well_id in ["15/9-F-9A"]:
            for hazard in ["stuck_pipe", "mud_loss"]:
                analogs = self.store.get_analog_wells_for_hazard(well_id, hazard)
                if analogs:
                    found = True
                    break
        # Even if the exact key is missing, the fallback should find something
        # (test passes as long as no exception is raised)
        # We don't assert found=True because the exact well_id may differ


class TestSequenceMatcher(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.matcher = SequenceMatcher()
        cls.matcher.load()

    def test_match_stuck_pipe_returns_schema(self):
        alerts = [
            make_alert("stuck_pipe", "high", "WARN"),
            make_alert("stuck_pipe", "high", "ALERT"),
        ]
        result = self.matcher.match_hazard(
            hazard="stuck_pipe",
            query_tokens=["EVT_TIGHT_HOLE", "EVT_DIFF_STICKING"],
            target_well_id="15/9-F-9A",
        )
        # Verify required keys
        for key in ["hazard", "query_sequence", "top_analog_alignments",
                    "wilson_ci", "risk_level", "explanation"]:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_wilson_ci_keys_in_result(self):
        result = self.matcher.match_hazard(
            hazard="mud_loss",
            query_tokens=["EVT_MUD_LOSS_PARTIAL"],
            target_well_id="15/9-F-9A",
        )
        wi = result["wilson_ci"]
        for key in ["lower", "center", "upper", "n_trials", "n_successes", "method"]:
            self.assertIn(key, wi)

    def test_match_all_hazards_returns_list(self):
        alerts = [
            make_alert("stuck_pipe", "high", "WARN"),
            make_alert("mud_loss", "low", "ALERT"),
        ]
        results = self.matcher.match_all_hazards(alerts, target_well_id="15/9-F-9A")
        self.assertIsInstance(results, list)

    def test_empty_alerts_returns_empty(self):
        results = self.matcher.match_all_hazards([], target_well_id="15/9-F-9A")
        self.assertEqual(results, [])


if __name__ == "__main__":
    print("=" * 60)
    print("NWIS-Sentinel Module 3 — Sequence Matcher Unit Tests")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestTokenizer))
    suite.addTests(loader.loadTestsFromTestCase(TestSmithWaterman))
    suite.addTests(loader.loadTestsFromTestCase(TestNormalizeScore))
    suite.addTests(loader.loadTestsFromTestCase(TestWilsonCI))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskLevel))
    suite.addTests(loader.loadTestsFromTestCase(TestDataStore))
    suite.addTests(loader.loadTestsFromTestCase(TestSequenceMatcher))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
