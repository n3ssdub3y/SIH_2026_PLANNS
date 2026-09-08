"""
Live Telemetry Simulator — production version would connect directly to eRTMAC's WITSML feed.

NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 3: Step 1 - Live Telemetry Replay Engine

This module is responsible for:
  - Loading real drilling telemetry data (Volve Well 15/9-F-9A).
  - Maintaining strict chronological / depth row order.
  - Streaming records sequentially one row at a time.
  - Supporting configurable playback speed (intervals and speed multipliers).
  - Preserving all 15 original feature names and sensor units without modification.
  - Safe client connection/disconnection and stream reset/loop handling.
  - Pure simulation logic: NO risk prediction or alert logic is in this simulator.
"""

import os
import math
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Generator
import pandas as pd

logger = logging.getLogger("telemetry_simulator")

# Default path to the real Volve WITSML telemetry file
DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "results" / "module1_outputs" / "telemetry" / "15_9-F-9A.csv"

# Configuration defaults
DEFAULT_BASE_INTERVAL = float(os.getenv("TELEMETRY_BASE_INTERVAL", "1.0"))  # Default 1.0s delay between rows
DEFAULT_SPEED_MULTIPLIER = float(os.getenv("TELEMETRY_SPEED_MULTIPLIER", "1.0"))  # 1x, 2x, 5x, 10x, 100x
DEFAULT_WELL_ID = "15/9-F-9A"


class TelemetrySimulator:
    """
    Stateful telemetry replay engine.
    Replays real WITSML drilling sensor data sequentially row-by-row.
    """

    def __init__(
        self,
        csv_path: Optional[Path | str] = None,
        well_id: str = DEFAULT_WELL_ID,
        base_interval: float = DEFAULT_BASE_INTERVAL,
        speed_multiplier: float = DEFAULT_SPEED_MULTIPLIER,
        loop: bool = True
    ):
        self.csv_path = Path(csv_path) if csv_path else DEFAULT_DATA_PATH
        self.well_id = well_id
        self.base_interval = max(0.01, float(base_interval))
        self.speed_multiplier = max(0.01, float(speed_multiplier))
        self.loop = loop

        self._records: List[Dict[str, Any]] = []
        self._columns: List[str] = []
        self._current_index: int = 0
        self._is_paused: bool = False
        self._is_completed: bool = False

        self._load_dataset()

    def _load_dataset(self) -> None:
        """Load telemetry dataset from CSV, preserving all column headers and cleaning NaN to None."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Telemetry CSV file not found at: {self.csv_path}")

        df = pd.read_csv(self.csv_path)
        self._columns = df.columns.tolist()

        # Convert numpy/pandas NaN, Infinity, -Infinity to None for valid JSON serialization
        records = df.to_dict(orient="records")
        cleaned_records = []
        for row in records:
            cleaned_row = {}
            for k, v in row.items():
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    cleaned_row[k] = None
                else:
                    cleaned_row[k] = v
            cleaned_records.append(cleaned_row)

        self._records = cleaned_records
        self._current_index = 0
        self._is_completed = False
        logger.info("Loaded %d telemetry records from %s", len(self._records), self.csv_path.name)

    @property
    def total_rows(self) -> int:
        return len(self._records)

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def columns(self) -> List[str]:
        return list(self._columns)

    @property
    def delay_seconds(self) -> float:
        """Effective delay between rows in seconds."""
        return max(0.001, self.base_interval / self.speed_multiplier)

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def is_completed(self) -> bool:
        return self._is_completed

    def set_speed_multiplier(self, speed: float) -> float:
        """Configure speed multiplier (e.g. 1.0, 5.0, 10.0, 100.0)."""
        self.speed_multiplier = max(0.01, float(speed))
        return self.delay_seconds

    def set_base_interval(self, interval: float) -> float:
        """Configure base delay interval in seconds (e.g. 0.1, 0.5, 1.0, 2.0)."""
        self.base_interval = max(0.001, float(interval))
        return self.delay_seconds

    def pause(self) -> None:
        self._is_paused = True

    def resume(self) -> None:
        self._is_paused = False

    def reset(self) -> None:
        """Restart stream from row 0."""
        self._current_index = 0
        self._is_completed = False

    def get_current_record(self) -> Optional[Dict[str, Any]]:
        """Return the current record snapshot without advancing."""
        if not self._records:
            return None
        idx = min(self._current_index, len(self._records) - 1)
        return self._format_message(idx)

    def advance_next_record(self) -> Optional[Dict[str, Any]]:
        """
        Advance and return the next telemetry record.
        Handles loop behavior or completion cleanly.
        """
        if not self._records:
            return None

        if self._current_index >= len(self._records):
            if self.loop:
                self._current_index = 0
                self._is_completed = False
            else:
                self._is_completed = True
                return {
                    "event": "stream_completed",
                    "status": "completed",
                    "total_rows_streamed": len(self._records),
                    "well_id": self.well_id
                }

        idx = self._current_index
        self._current_index += 1
        return self._format_message(idx)

    def _format_message(self, index: int) -> Dict[str, Any]:
        """Wrap row data with simulation metadata while strictly preserving telemetry features."""
        row_data = self._records[index]
        return {
            "well_id": self.well_id,
            "row_index": index,
            "total_rows": len(self._records),
            "delay_seconds": round(self.delay_seconds, 4),
            "is_last_row": (index == len(self._records) - 1),
            "telemetry": row_data
        }

    def get_status(self) -> Dict[str, Any]:
        """Return engine operational status."""
        curr = self._records[min(self._current_index, len(self._records) - 1)] if self._records else {}
        current_md = curr.get("Measured Depth m")
        return {
            "well_id": self.well_id,
            "current_index": self._current_index,
            "total_rows": len(self._records),
            "current_measured_depth_m": current_md,
            "base_interval_sec": self.base_interval,
            "speed_multiplier": self.speed_multiplier,
            "delay_seconds": round(self.delay_seconds, 4),
            "is_paused": self._is_paused,
            "is_completed": self._is_completed,
            "loop_enabled": self.loop
        }
