from __future__ import annotations

from collections.abc import Collection
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal, Sequence

from trading_platform.backtester.clock import ClockFrame
from trading_platform.backtester.models import (
    DecisionSnapshot,
    ExecutionIntent,
    FillEvent,
)
from trading_platform.core.costs import CostModel
from trading_platform.portfolio.position import Position
from trading_platform.portfolio.trade import Trade


class PortfolioStateError(ValueError):
    """Raised when intents, fills, or state transitions are invalid."""


@dataclass(frozen=True)
class ActivePosition:
    position_id: str
    decision: DecisionSnapshot
    position: Position
    entry_cost: float
    entry_cost_breakdown: dict[str, float]


@dataclass
class PositionState:
    position_id: str
    decision: DecisionSnapshot
    state: Literal["ENTRY_PENDING", "OPEN", "EXIT_PENDING"]
    entry_cost: float = 0.0
    entry_cost_breakdown: dict[str, float] = field(default_factory=dict)
    entry_mid_price: float | None = None
    position: Position | None = None
    expiry_bar: int | None = None
    active_view: ActivePosition | None = None


class PortfolioManager:
    """Stateful portfolio manager built around explicit intents and fills."""

    def __init__(
        self,
        *,
        instrument: dict[str, Any] | None = None,
        cost_model: dict[str, Any] | None = None,
        default_position_size: float = 1.0,
        entry_window_bars: int = 1,
        max_positions_per_side: int = 1,
    ) -> None:
        if default_position_size <= 0:
            raise PortfolioStateError("default_position_size must be positive.")
        if entry_window_bars < 1:
            raise PortfolioStateError("entry_window_bars must be >= 1.")
        if max_positions_per_side < 1:
            raise PortfolioStateError("max_positions_per_side must be >= 1.")
        self._instrument = instrument or {}
        self._symbol = str(self._instrument.get("symbol", "UNKNOWN"))
        self._cost_model = CostModel.from_dict(cost_model)
        self._default_size = float(default_position_size)
        self._entry_window_bars = int(entry_window_bars)
        self._max_positions_per_side = int(max_positions_per_side)
        self._positions: dict[str, PositionState] = {}
        self._intent_lookup: dict[int, str] = {}
        self._decision_lookup: dict[tuple[Any, ...], str] = {}
        self._open_views: dict[str, ActivePosition] = {}
        self._position_seq = 0
        self._bar_counter = 0
        self.trades: list[Trade] = []

    # ------------------------------------------------------------------ #
    # Public lifecycle
    # ------------------------------------------------------------------ #
    def on_clock_tick(self, frame: ClockFrame) -> None:
        """Advance bar counter and expire pending entries past their window."""
        del frame  # frame used to keep signature consistent; reserved for future use
        self._bar_counter += 1
        expired: list[str] = []
        for position_id, state in self._positions.items():
            if (
                state.state == "ENTRY_PENDING"
                and state.expiry_bar is not None
                and state.expiry_bar < self._bar_counter
            ):
                expired.append(position_id)
        for position_id in expired:
            state = self._positions.pop(position_id)
            self._decision_lookup.pop(self._decision_key(state.decision), None)
            self._remove_intent_mapping(position_id)

    def authorize_intents(
        self, intents: Sequence[ExecutionIntent] | None
    ) -> list[ExecutionIntent]:
        """Validate and size intents before they reach the execution engine."""
        if not intents:
            return []
        accepted: list[ExecutionIntent] = []
        for intent in intents:
            if intent.intent_type in {"enter_long", "enter_short"}:
                accepted.append(self._prepare_entry_intent(intent))
            elif intent.intent_type == "exit":
                accepted.extend(self._prepare_exit_intent(intent))
            else:
                raise PortfolioStateError(
                    f"Unsupported intent_type {intent.intent_type}"
                )
        return accepted

    def apply_fill(self, fill: FillEvent) -> Trade | None:
        """Consume a FillEvent and update state or record a completed trade."""
        if fill.reason == "entry":
            self._handle_entry_fill(fill)
            return None
        if fill.reason in {
            "strategy_exit",
            "stop_loss",
            "take_profit",
            "trailing_stop",
        }:
            exit_reason = (
                "strategy_exit" if fill.reason == "strategy_exit" else fill.reason
            )
            return self._handle_exit_fill(fill, exit_reason)
        raise PortfolioStateError(f"Unsupported fill reason '{fill.reason}'.")

    @property
    def active_positions(self) -> list[ActivePosition]:
        return list(self._open_views.values())

    def active_position_views(self) -> Collection[ActivePosition]:
        return self._open_views.values()

    @property
    def pending_entry_count(self) -> int:
        return sum(
            1 for state in self._positions.values() if state.state == "ENTRY_PENDING"
        )

    def serialize_state(self) -> dict[str, Any]:
        payload: list[dict[str, Any]] = []
        for state in self._positions.values():
            payload.append(
                {
                    "position_id": state.position_id,
                    "state": state.state,
                    "decision": asdict(state.decision),
                    "entry_cost": state.entry_cost,
                    "entry_cost_breakdown": dict(state.entry_cost_breakdown),
                    "entry_mid_price": state.entry_mid_price,
                    "expiry_bar": state.expiry_bar,
                    "position": asdict(state.position) if state.position else None,
                }
            )
        return {
            "bar_counter": self._bar_counter,
            "positions": payload,
            "trades": [asdict(trade) for trade in self.trades],
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._positions.clear()
        self._intent_lookup.clear()
        self._decision_lookup.clear()
        self._open_views = {}
        self.trades = []
        self._bar_counter = int(state.get("bar_counter", 0))
        for raw in state.get("positions", []):
            decision = DecisionSnapshot(**raw["decision"])
            position = Position(**raw["position"]) if raw.get("position") else None
            restored = PositionState(
                position_id=str(raw["position_id"]),
                decision=decision,
                state=raw["state"],
                entry_cost=float(raw.get("entry_cost", 0.0)),
                entry_cost_breakdown=dict(raw.get("entry_cost_breakdown", {})),
                entry_mid_price=raw.get("entry_mid_price"),
                position=position,
                expiry_bar=raw.get("expiry_bar"),
            )
            if restored.state == "OPEN" and restored.position is not None:
                restored.active_view = ActivePosition(
                    position_id=restored.position_id,
                    decision=restored.decision,
                    position=restored.position,
                    entry_cost=restored.entry_cost,
                    entry_cost_breakdown=dict(restored.entry_cost_breakdown),
                )
                self._open_views[restored.position_id] = restored.active_view
            self._positions[restored.position_id] = restored
            self._decision_lookup[self._decision_key(decision)] = restored.position_id
        for trade in state.get("trades", []):
            self.trades.append(Trade(**trade))

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _prepare_entry_intent(self, intent: ExecutionIntent) -> ExecutionIntent:
        decision = intent.decision
        if decision.bar_index is None:
            raise PortfolioStateError("ExecutionIntent decision missing bar_index.")
        side = decision.side
        if self._side_usage(side) >= self._max_positions_per_side:
            raise PortfolioStateError(f"Exceeded position cap for side '{side}'.")
        sized_decision = self._with_size(decision)
        sized_intent = replace(intent, decision=sized_decision)
        position_id = self._allocate_position_id(side)
        expiry_bar = self._bar_counter + self._entry_window_bars
        state = PositionState(
            position_id=position_id,
            decision=sized_decision,
            state="ENTRY_PENDING",
            entry_cost=0.0,
            entry_cost_breakdown={"spread": 0.0, "commission": 0.0, "slippage": 0.0},
            expiry_bar=expiry_bar,
        )
        self._positions[position_id] = state
        self._intent_lookup[id(sized_intent)] = position_id
        self._decision_lookup[self._decision_key(sized_decision)] = position_id
        return sized_intent

    def _prepare_exit_intent(self, intent: ExecutionIntent) -> list[ExecutionIntent]:
        decision = intent.decision
        if decision.side not in {"long", "short"}:
            raise PortfolioStateError("Exit intent missing side.")
        accepted: list[ExecutionIntent] = []
        for state in self._positions.values():
            if state.state == "OPEN" and state.decision.side == decision.side:
                exit_intent = replace(intent, decision=state.decision)
                self._intent_lookup[id(exit_intent)] = state.position_id
                state.state = "EXIT_PENDING"
                accepted.append(exit_intent)
        return accepted

    def _handle_entry_fill(self, fill: FillEvent) -> None:
        if fill.intent is None:
            raise PortfolioStateError("Entry fills must include an intent reference.")
        position_id = self._intent_lookup.pop(id(fill.intent), None)
        if position_id is None:
            raise PortfolioStateError("Received fill for unknown intent.")
        state = self._positions.get(position_id)
        if state is None or state.state != "ENTRY_PENDING":
            raise PortfolioStateError("Entry fill received for non-pending position.")
        size = state.decision.size
        entry_mid = float(fill.price)
        entry_price = self._cost_model.get_entry_price(entry_mid, state.decision.side)
        entry_cost, breakdown = self._cost_model.compute_entry_cost(
            size=size, price=entry_mid, instrument=self._instrument
        )
        state.entry_mid_price = entry_mid
        state.entry_cost = entry_cost
        state.entry_cost_breakdown = breakdown
        state.state = "OPEN"
        state.position = Position(
            symbol=self._symbol,
            entry_time=fill.timestamp,
            entry_price=entry_price,
            entry_mid_price=entry_mid,
            side=state.decision.side,
            size=size,
            context_at_entry=state.decision.context,
        )
        state.expiry_bar = None
        state.active_view = ActivePosition(
            position_id=state.position_id,
            decision=state.decision,
            position=state.position,
            entry_cost=entry_cost,
            entry_cost_breakdown=dict(breakdown),
        )
        self._open_views[state.position_id] = state.active_view
        return None

    def _handle_exit_fill(self, fill: FillEvent, reason: str) -> Trade:
        position_id = None
        if fill.intent is not None:
            position_id = self._intent_lookup.pop(id(fill.intent), None)
        if position_id is None and fill.decision is not None:
            position_id = self._decision_lookup.get(self._decision_key(fill.decision))
        if position_id is None:
            raise PortfolioStateError("Exit fill did not match any tracked position.")
        try:
            state = self._positions[position_id]
        except KeyError as err:  # pragma: no cover - defensive
            raise PortfolioStateError("Exit fill matched unknown position.") from err
        if state.position is None:
            raise PortfolioStateError("Exit fill matched invalid position state.")
        size = state.decision.size
        if size <= 0:
            raise PortfolioStateError("Tracked position has invalid size.")
        entry_mid = float(state.entry_mid_price or state.position.entry_mid_price)
        exit_mid = float(fill.price)
        exit_price = self._cost_model.get_exit_price(exit_mid, state.decision.side)
        exit_cost, exit_breakdown = self._cost_model.compute_exit_cost(
            size=size, price=exit_mid, instrument=self._instrument
        )
        spread_cost = self._cost_model.compute_spread_cost(size, self._instrument)
        if state.decision.side == "long":
            gross_mid = (exit_mid - entry_mid) * size
        else:
            gross_mid = (entry_mid - exit_mid) * size
        total_cost = spread_cost + state.entry_cost + exit_cost
        net_pnl = gross_mid - total_cost
        combined_breakdown = {
            "spread": spread_cost,
            "commission": (
                state.entry_cost_breakdown.get("commission", 0.0)
                + exit_breakdown.get("commission", 0.0)
            ),
            "slippage": (
                state.entry_cost_breakdown.get("slippage", 0.0)
                + exit_breakdown.get("slippage", 0.0)
            ),
        }
        trade = Trade(
            symbol=state.position.symbol,
            entry_time=state.position.entry_time,
            exit_time=fill.timestamp,
            entry_price=state.position.entry_price,
            exit_price=exit_price,
            side=state.position.side,
            size=size,
            pnl=net_pnl,
            exit_reason=reason,
            cost_currency=total_cost,
            cost_breakdown=combined_breakdown,
            context_at_entry=state.position.context_at_entry,
            context_at_exit=fill.intent.decision.context if fill.intent else None,
        )
        self.trades.append(trade)
        self._positions.pop(position_id, None)
        self._decision_lookup.pop(self._decision_key(state.decision), None)
        self._open_views.pop(position_id, None)
        return trade

    def _allocate_position_id(self, side: str) -> str:
        self._position_seq += 1
        return f"{side}-{self._position_seq}"

    def _with_size(self, decision: DecisionSnapshot) -> DecisionSnapshot:
        return replace(decision, size=self._default_size)

    def _decision_key(self, decision: DecisionSnapshot) -> tuple[Any, ...]:
        return (
            decision.bar_index,
            decision.timestamp,
            decision.side,
            decision.price,
        )

    def _side_usage(self, side: str) -> int:
        return sum(
            1
            for state in self._positions.values()
            if state.decision.side == side and state.state in {"ENTRY_PENDING", "OPEN"}
        )

    def _remove_intent_mapping(self, position_id: str) -> None:
        for key, value in list(self._intent_lookup.items()):
            if value == position_id:
                self._intent_lookup.pop(key, None)
