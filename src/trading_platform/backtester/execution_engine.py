from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Iterable

from trading_platform.backtester.models import (
    DecisionSnapshot,
    ExecutionIntent,
    FillEvent,
    RiskExitEvent,
)


class ExecutionEngineError(ValueError):
    """Raised when invalid instructions or bar data are supplied."""


class NextBarExecutionEngine:
    """Execution engine that fills intents on the next bar open."""

    def __init__(self) -> None:
        self._pending_entries: deque[dict[str, Any]] = deque()
        self._pending_risk_events: deque[RiskExitEvent] = deque()
        self._last_clock_time: datetime | None = None

    def submit_intent(self, intent: ExecutionIntent) -> None:
        self._validate_intent(intent)
        self._pending_entries.append({"intent": intent, "ready": False})

    def submit_risk_event(self, event: RiskExitEvent) -> None:
        self._validate_risk_event(event)
        self._pending_risk_events.append(event)

    def advance_clock(self, bar: dict[str, Any]) -> Iterable[FillEvent]:
        bar_open_time = self._coerce_datetime(bar.get("open_time"))
        bar_close_time = self._coerce_datetime(bar.get("close_time"))
        if bar_open_time is None or bar_close_time is None:
            raise ExecutionEngineError("Bar must include open_time and close_time.")
        if self._last_clock_time and bar_open_time <= self._last_clock_time:
            raise ExecutionEngineError("Bars must be supplied in ascending order.")
        if "open" not in bar:
            raise ExecutionEngineError("Bar missing 'open' price required for fills.")

        fills: list[FillEvent] = []

        # Risk exits fire immediately on the same bar.
        while self._pending_risk_events:
            event = self._pending_risk_events.popleft()
            fills.append(
                FillEvent(
                    intent=None,
                    timestamp=event.timestamp,
                    price=float(event.price),
                    size=float(event.decision.size),
                    decision=event.decision,
                    costs={},
                    reason=event.reason,
                )
            )

        # Next-bar-open intents fill once they've survived one bar advance.
        new_queue: deque[dict[str, Any]] = deque()
        while self._pending_entries:
            entry = self._pending_entries.popleft()
            if entry["ready"]:
                intent = entry["intent"]
                fills.append(
                    FillEvent(
                        intent=intent,
                        timestamp=bar_open_time,
                        price=float(bar["open"]),
                        size=float(intent.decision.size),
                        decision=intent.decision,
                        costs={},
                        reason="entry"
                        if intent.intent_type in {"enter_long", "enter_short"}
                        else "strategy_exit",
                    )
                )
            else:
                entry["ready"] = True
                new_queue.append(entry)
        self._pending_entries = new_queue
        self._last_clock_time = bar_open_time
        return fills

    @staticmethod
    def _validate_intent(intent: ExecutionIntent) -> None:
        if not isinstance(intent.decision, DecisionSnapshot):
            raise ExecutionEngineError(
                "ExecutionIntent missing valid DecisionSnapshot."
            )
        if intent.execution_model != "next_bar_open":
            raise ExecutionEngineError(
                f"Unsupported execution_model '{intent.execution_model}'."
            )
        if intent.intent_type not in {"enter_long", "enter_short", "exit"}:
            raise ExecutionEngineError(
                f"Unsupported intent_type '{intent.intent_type}'."
            )

    @staticmethod
    def _validate_risk_event(event: RiskExitEvent) -> None:
        if not isinstance(event.decision, DecisionSnapshot):
            raise ExecutionEngineError("RiskExitEvent must include DecisionSnapshot.")

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            from pandas import Timestamp

            if isinstance(value, Timestamp):
                return value.to_pydatetime()
        except ImportError:
            pass
        raise ExecutionEngineError(f"Unable to interpret datetime value: {value}")
