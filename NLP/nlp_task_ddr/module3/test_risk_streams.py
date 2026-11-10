"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 3: Risk-prediction stream separation & schema-harmony tests

Module 3 produces two JSONL risk streams in module3/outputs/:

  risk_predictions_backtest.jsonl  written by backtest_runner.py; COMMITTED seed, so the
                                   +106.48 m headline data works on a fresh clone.
  risk_predictions_live.jsonl      written by anomaly_server.py while telemetry replays;
                                   git-ignored and truncated on every server start.

Module 4 reads them interchangeably (live first, backtest fallback), so the live record
must be a structural superset of the backtest record. These tests enforce that, using real
SequenceMatcher output pushed through the real live writer, and prove the live server's
startup cleanup can never delete the committed backtest stream.
"""

import json
import os
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anomaly_server
from sequence_matcher import SequenceMatcher

_MODULE3_DIR = Path(__file__).resolve().parent
BACKTEST_PATH = _MODULE3_DIR / "outputs" / "risk_predictions_backtest.jsonl"
GITIGNORE_PATH = _MODULE3_DIR.parents[2] / ".gitignore"  # repo root

# Fields every consumer (Module 4 briefing, monitor table) relies on.
CORE_KEYS = {
    "timestamp", "well_id", "hazard", "risk_level", "risk_score", "wilson_ci",
    "query_sequence", "top_analog_alignments", "explanation",
    "measured_depth_m", "row_index", "actionable_threshold_crossed",
}


def _read_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestBacktestStreamSeed(unittest.TestCase):
    """The committed backtest stream must be present and complete."""

    def test_committed_backtest_stream_is_complete(self):
        self.assertTrue(BACKTEST_PATH.exists(), f"missing committed seed: {BACKTEST_PATH}")
        records = _read_jsonl(BACKTEST_PATH)
        self.assertGreater(len(records), 0)
        for rec in records:
            self.assertLessEqual(CORE_KEYS - set(rec), set(), "backtest record missing core fields")
            self.assertLessEqual({"lower", "center", "upper"} - set(rec["wilson_ci"]), set())

    def test_backtest_stream_covers_flagship_well_and_hazard(self):
        records = _read_jsonl(BACKTEST_PATH)
        self.assertTrue(any(r["well_id"] == "15/9-F-9A" and r["hazard"] == "stuck_pipe" for r in records))

    def test_only_live_stream_is_gitignored(self):
        ignore_text = GITIGNORE_PATH.read_text(encoding="utf-8")
        self.assertIn("risk_predictions_live.jsonl", ignore_text)
        self.assertNotIn("risk_predictions_backtest.jsonl", ignore_text)


class TestLiveStreamWriter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = SequenceMatcher()
        cls.matcher.load()

    def test_stream_paths_are_distinct_and_colocated(self):
        live = anomaly_server.RISK_PREDICTIONS_PATH
        self.assertEqual(live.name, "risk_predictions_live.jsonl")
        self.assertNotEqual(live, BACKTEST_PATH)
        self.assertEqual(live.parent, BACKTEST_PATH.parent)

    def _write_live_record(self, buffer_rows, row_count):
        """Run a real matcher result through the real live writer into a temp file."""
        result = self.matcher.match_hazard(
            "stuck_pipe", ["EVT_TIGHT_HOLE", "EVT_TIGHT_HOLE"], "15/9-F-9A"
        )
        with tempfile.TemporaryDirectory() as tmp:
            live_path = Path(tmp) / "risk_predictions_live.jsonl"
            with mock.patch.object(anomaly_server, "RISK_PREDICTIONS_PATH", live_path), \
                 mock.patch.object(anomaly_server, "telemetry_buffer", deque(buffer_rows)), \
                 mock.patch.object(anomaly_server, "row_count", row_count):
                anomaly_server.append_risk_prediction(result)
            return result, _read_jsonl(live_path)[0]

    def test_live_record_is_structural_superset_of_backtest_record(self):
        backtest_keys = set(_read_jsonl(BACKTEST_PATH)[0])
        _, live = self._write_live_record([{"Measured Depth m": 512.52}], row_count=4321)
        self.assertLessEqual(backtest_keys - set(live), set(),
                             "live record lacks fields the backtest record has")
        self.assertLessEqual(CORE_KEYS - set(live), set())

    def test_live_record_populates_depth_row_and_actionable_flag(self):
        result, live = self._write_live_record([{"Measured Depth m": 512.52}], row_count=4321)
        self.assertEqual(live["measured_depth_m"], 512.52)
        self.assertEqual(live["row_index"], 4321)
        self.assertEqual(live["well_id"], "15/9-F-9A")
        self.assertEqual(live["actionable_threshold_crossed"], result["risk_level"] == "CRITICAL")
        self.assertEqual(live["risk_score"], result["risk_score"])

    def test_live_record_tolerates_missing_or_non_numeric_depth(self):
        for rows in ([], [{}], [{"Measured Depth m": "n/a"}], [{"Measured Depth m": float("nan")}]):
            with self.subTest(buffer=rows):
                _, live = self._write_live_record(rows, row_count=1)
                self.assertIsNone(live["measured_depth_m"])

    def test_server_startup_clears_only_the_live_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            live, backtest = out / "risk_predictions_live.jsonl", out / "risk_predictions_backtest.jsonl"
            live.write_text('{"stale": true}\n', encoding="utf-8")
            backtest.write_text('{"seed": true}\n', encoding="utf-8")
            with mock.patch.object(anomaly_server, "OUTPUTS_DIR", out), \
                 mock.patch.object(anomaly_server, "RISK_PREDICTIONS_PATH", live):
                anomaly_server.ensure_outputs_dir()
            self.assertFalse(live.exists())
            self.assertTrue(backtest.exists())
            self.assertEqual(backtest.read_text(encoding="utf-8"), '{"seed": true}\n')


if __name__ == "__main__":
    unittest.main()
