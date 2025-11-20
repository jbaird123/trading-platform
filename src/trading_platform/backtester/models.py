from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class DecisionSnapshot:
    """Immutable capture of a strategy decision at bar close."""

    timestamp: datetime
    price: float
    side: Literal["long", "short"]
    size: float
    bar_index: int | None = None
    strategy_features: dict[str, float | None] = field(default_factory=dict)
    global_features: dict[str, float | None] = field(default_factory=dict)
    regime: dict[str, Any] | None = None
    risk: dict[str, Any] = field(default_factory=dict)
    gating: dict[str, Any] | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionIntent:
    """Instruction from the strategy describing the desired action."""

    decision: DecisionSnapshot
    intent_type: Literal["enter_long", "enter_short", "exit", "hold"]
    execution_model: Literal["next_bar_open"]
    risk_overrides: dict[str, Any] | None = None
    notes: str | None = None


@dataclass(frozen=True)
class RiskExitEvent:
    """Signal from the REM indicating a stop/TP trigger."""

    timestamp: datetime
    price: float
    reason: Literal["stop_loss", "take_profit", "trailing_stop"]
    decision: DecisionSnapshot
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class FillEvent:
    """Concrete execution produced by the execution engine."""

    intent: ExecutionIntent | None
    timestamp: datetime
    price: float
    size: float
    costs: dict[str, float]
    reason: Literal[
        "entry",
        "strategy_exit",
        "stop_loss",
        "take_profit",
        "trailing_stop",
    ]
