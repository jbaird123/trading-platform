from __future__ import annotations

from collections.abc import Collection
from typing import Any, Protocol

import pandas as pd

from trading_platform.backtester.clock import ClockFrame
from trading_platform.backtester.models import RiskExitEvent
from trading_platform.backtester.portfolio_manager import ActivePosition
from trading_platform.core.types import BarData
from trading_platform.portfolio.position import Position


class RiskEvaluator(Protocol):
    def check_exits(
        self,
        position: Position,
        current_bar: BarData,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any] | None: ...


class RiskExitAdapter:
    """Thin adapter that converts REM responses into RiskExitEvents."""

    _VALID_REASONS: set[str] = {"stop_loss", "take_profit", "trailing_stop"}

    def __init__(
        self,
        *,
        rem: RiskEvaluator,
        data_handler: Any | None = None,
        bar_minutes: int | None = None,
    ) -> None:
        self._rem = rem
        self._data_handler = data_handler
        self._bar_minutes = bar_minutes
        self._previous_bar: pd.Series | None = None

    def evaluate(
        self,
        *,
        frame: ClockFrame,
        positions: Collection[ActivePosition],
        current_bar: pd.Series | None = None,
    ) -> list[RiskExitEvent]:
        if not positions:
            self._previous_bar = self._coerce_series(
                current_bar, fallback=self._previous_bar
            )
            return []
        bar = self._coerce_series(current_bar, fallback=self._previous_bar)
        if bar is None:
            raise ValueError(
                "RiskExitAdapter requires a pandas Series for REM evaluation."
            )
        events: list[RiskExitEvent] | None = None
        for active in positions:
            result = self._rem.check_exits(
                active.position,
                bar,
                data_handler=self._data_handler,
                prior_bar=self._previous_bar,
                bar_minutes=self._bar_minutes,
            )
            if not result:
                continue
            reason = str(result.get("reason") or "").lower().replace("-", "_")
            if reason not in self._VALID_REASONS:
                raise ValueError(f"REM returned unsupported reason '{reason}'.")
            price = float(result["exit_price"])
            if events is None:
                events = []
            events.append(
                RiskExitEvent(
                    timestamp=frame.open_time,
                    price=price,
                    reason=reason,  # type: ignore[arg-type]
                    decision=active.decision,
                    details=result,
                )
            )
        self._previous_bar = bar
        return events or []

    @staticmethod
    def _coerce_series(
        series: pd.Series | None, *, fallback: pd.Series | None
    ) -> pd.Series | None:
        if isinstance(series, pd.Series):
            return series
        return fallback
