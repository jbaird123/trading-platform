from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


class TelemetryTracker:
    """Very lightweight telemetry/logging of loop progress."""

    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []

    def record(
        self,
        *,
        bar_open_time: datetime,
        bars_processed: int,
        fills_generated: int,
    ) -> None:
        self._history.append(
            {
                "bar_open_time": bar_open_time,
                "bars_processed": bars_processed,
                "fills_generated": fills_generated,
            }
        )

    @property
    def history(self) -> Iterable[dict[str, Any]]:
        return tuple(self._history)
