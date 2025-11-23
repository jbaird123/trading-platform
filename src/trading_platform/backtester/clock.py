from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from trading_platform.backtester.execution_engine import ExecutionEngineError


@dataclass(frozen=True)
class ClockFrame:
    """Snapshot of a bar's timing metadata."""

    bar: dict[str, Any]
    open_time: datetime
    close_time: datetime
    entry_open_time: datetime
    decision_time: datetime


class BarClock:
    """Authoritative clock that validates bar order and derives timestamps."""

    def __init__(self) -> None:
        self._last_open_time: datetime | None = None

    def advance(self, bar: dict[str, Any]) -> ClockFrame:
        open_time = self._coerce_datetime(bar.get("open_time"), "open_time")
        close_time = self._coerce_datetime(bar.get("close_time"), "close_time")
        if self._last_open_time and open_time <= self._last_open_time:
            raise ExecutionEngineError("Bars must be provided in ascending order.")
        self._last_open_time = open_time
        return ClockFrame(
            bar=bar,
            open_time=open_time,
            close_time=close_time,
            entry_open_time=open_time,
            decision_time=close_time,
        )

    @staticmethod
    def _coerce_datetime(value: Any, field_name: str) -> datetime:
        if isinstance(value, datetime):
            return value
        try:
            from pandas import Timestamp
        except ImportError:
            pass
        else:
            if isinstance(value, Timestamp):
                return value.to_pydatetime()
        raise ExecutionEngineError(
            f"Bar missing valid {field_name}; got {value!r} of type {type(value)}"
        )
