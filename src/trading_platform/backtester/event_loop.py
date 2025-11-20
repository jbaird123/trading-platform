from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Sequence

from trading_platform.backtester.clock import BarClock
from trading_platform.backtester.execution_engine import NextBarExecutionEngine
from trading_platform.backtester.models import ExecutionIntent, FillEvent, RiskExitEvent
from trading_platform.backtester.telemetry import TelemetryTracker


class EventLoop:
    """Coordinates intents/risk events with the execution engine and clock."""

    def __init__(
        self,
        *,
        clock: BarClock | None = None,
        execution_engine: NextBarExecutionEngine | None = None,
        telemetry: TelemetryTracker | None = None,
    ) -> None:
        self._clock = clock or BarClock()
        self._engine = execution_engine or NextBarExecutionEngine()
        self._telemetry = telemetry or TelemetryTracker()
        self._metrics = {"bars_processed": 0, "fills_generated": 0}

    def on_bar(
        self,
        bar: dict[str, Any],
        intents: Sequence[ExecutionIntent] | None = None,
        risk_events: Sequence[RiskExitEvent] | None = None,
    ) -> Iterable[FillEvent]:
        """Process a new bar, returning any fills that occur."""
        frame = self._clock.advance(bar)  # validates ordering & timestamps
        self._metrics["bars_processed"] += 1
        for intent in intents or ():
            self._engine.submit_intent(intent)
        for event in risk_events or ():
            self._engine.submit_risk_event(event)
        fills = list(self._engine.advance_clock(bar))
        self._metrics["fills_generated"] += len(fills)
        self._telemetry.record(
            bar_open_time=frame.open_time,
            bars_processed=self._metrics["bars_processed"],
            fills_generated=self._metrics["fills_generated"],
        )
        return fills

    @property
    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)
