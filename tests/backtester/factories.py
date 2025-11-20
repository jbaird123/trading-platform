from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, cast

from trading_platform.backtester.models import (
    DecisionSnapshot,
    ExecutionIntent,
    FillEvent,
    RiskExitEvent,
)


def snapshot_factory(
    *,
    side: Literal["long", "short"] = "long",
    price: float = 1.0,
    size: float = 1.0,
    minute_offset: int = 0,
    bar_index: int | None = 0,
) -> DecisionSnapshot:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute_offset)
    literal_side = cast(Literal["long", "short"], side)
    return DecisionSnapshot(
        timestamp=ts,
        price=price,
        side=literal_side,
        size=size,
        bar_index=bar_index,
    )


def intent_factory(
    *,
    side: Literal["long", "short"] = "long",
    execution_model: str = "next_bar_open",
    bar_index: int | None = 0,
) -> ExecutionIntent:
    decision = snapshot_factory(side=side, bar_index=bar_index)
    intent_type = cast(
        Literal["enter_long", "enter_short"],
        "enter_long" if side == "long" else "enter_short",
    )
    exec_model = cast(Literal["next_bar_open"], execution_model)
    return ExecutionIntent(
        decision=decision,
        intent_type=intent_type,
        execution_model=exec_model,
    )


def risk_event_factory(
    *,
    reason: Literal["stop_loss", "take_profit", "trailing_stop"] = "stop_loss",
    price: float = 0.99,
    minute_offset: int = 0,
    decision: DecisionSnapshot | None = None,
) -> RiskExitEvent:
    decision = decision or snapshot_factory(minute_offset=minute_offset)
    return RiskExitEvent(
        timestamp=decision.timestamp,
        price=price,
        reason=reason,
        decision=decision,
    )


def fill_factory(
    *,
    intent: ExecutionIntent | None = None,
    decision: DecisionSnapshot | None = None,
    price: float = 1.0,
    reason: Literal[
        "entry",
        "strategy_exit",
        "stop_loss",
        "take_profit",
        "trailing_stop",
    ] = "entry",
    minute_offset: int = 1,
) -> FillEvent:
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(
        minutes=minute_offset
    )
    size = intent.decision.size if intent else 1.0
    decision_snapshot = decision or (intent.decision if intent else None)
    return FillEvent(
        intent=intent,
        timestamp=timestamp,
        price=price,
        size=size,
        costs={},
        decision=decision_snapshot,
        reason=reason,
    )
