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
) -> DecisionSnapshot:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute_offset)
    literal_side = cast(Literal["long", "short"], side)
    return DecisionSnapshot(timestamp=ts, price=price, side=literal_side, size=size)


def intent_factory(
    *,
    side: Literal["long", "short"] = "long",
    execution_model: str = "next_bar_open",
) -> ExecutionIntent:
    decision = snapshot_factory(side=side)
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
) -> RiskExitEvent:
    decision = snapshot_factory(minute_offset=minute_offset)
    return RiskExitEvent(
        timestamp=decision.timestamp,
        price=price,
        reason=reason,
        decision=decision,
    )


def fill_factory(
    *,
    intent: ExecutionIntent | None = None,
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
    return FillEvent(
        intent=intent,
        timestamp=timestamp,
        price=1.0,
        size=size,
        costs={},
        reason=reason,
    )
