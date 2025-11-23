from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Sequence

from trading_platform.backtester.clock import BarClock
from trading_platform.backtester.execution_engine import NextBarExecutionEngine
from trading_platform.backtester.models import ExecutionIntent, FillEvent, RiskExitEvent
from trading_platform.backtester.portfolio_manager import PortfolioManager
from trading_platform.backtester.risk import RiskExitAdapter
from trading_platform.backtester.telemetry import TelemetryTracker


class EventLoop:
    """Coordinates intents/risk events with the execution engine and clock."""

    def __init__(
        self,
        *,
        clock: BarClock | None = None,
        execution_engine: NextBarExecutionEngine | None = None,
        telemetry: TelemetryTracker | None = None,
        portfolio: PortfolioManager | None = None,
        risk_adapter: RiskExitAdapter | None = None,
    ) -> None:
        self._clock = clock or BarClock()
        self._engine = execution_engine or NextBarExecutionEngine()
        self._telemetry = telemetry or TelemetryTracker()
        self._portfolio = portfolio
        self._risk_adapter = risk_adapter
        self._metrics = {"bars_processed": 0, "fills_generated": 0}

    def on_bar(
        self,
        bar: dict[str, Any],
        intents: Sequence[ExecutionIntent] | None = None,
        risk_events: Sequence[RiskExitEvent] | None = None,
    ) -> Iterable[FillEvent]:
        """Process a new bar, returning any fills that occur."""
        frame = self._clock.advance(bar)  # validates ordering & timestamps
        bar_series = self._extract_bar_series(bar)
        if self._portfolio:
            self._portfolio.on_clock_tick(frame)
        self._metrics["bars_processed"] += 1
        prepared_intents = list(intents or ())
        if self._portfolio:
            prepared_intents = self._portfolio.authorize_intents(prepared_intents)
        for intent in prepared_intents:
            self._engine.submit_intent(intent)
        pending_events: list[RiskExitEvent] | None = None
        if risk_events:
            pending_events = list(risk_events)
        if pending_events:
            for event in pending_events:
                self._engine.submit_risk_event(event)
        fills = list(self._engine.advance_clock(bar))
        if self._portfolio:
            for fill in fills:
                self._portfolio.apply_fill(fill)
        risk_fills: list[FillEvent] = []
        if self._risk_adapter and self._portfolio and bar_series is not None:
            active_views = list(self._portfolio.active_position_views())
            auto_events = self._risk_adapter.evaluate(
                frame=frame,
                positions=active_views,
                current_bar=bar_series,
                commit=True,
            )
            if auto_events:
                for event in auto_events:
                    self._engine.submit_risk_event(event)
                risk_fills = list(self._engine.flush_risk_events())
                fills.extend(risk_fills)
                for fill in risk_fills:
                    self._portfolio.apply_fill(fill)
        if self._risk_adapter:
            self._risk_adapter.commit_pending_bar()
        if self._portfolio:
            self._portfolio.finalize_bar(bar)
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

    @staticmethod
    def _extract_bar_series(bar: Any) -> Any:
        try:
            import pandas as pd
        except ImportError:  # pragma: no cover - pandas is an existing dependency
            return None
        if isinstance(bar, pd.Series):
            return bar
        if isinstance(bar, dict):
            candidate = bar.get("bar")
            if isinstance(candidate, pd.Series):
                return candidate
        return None
