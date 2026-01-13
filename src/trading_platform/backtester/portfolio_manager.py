from __future__ import annotations

import logging
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
from trading_platform.portfolio.position_sizing import (
    PositionSizer,
)
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


logger = logging.getLogger(__name__)


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
        currency_converter: Any | None = None,
        position_sizer: PositionSizer | None = None,
        initial_cash: float = 100000.0,
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
        # Currency conversion
        self._currency_converter = currency_converter
        self._quote_ccy = str(self._instrument.get("quote_ccy", "USD"))
        # Position sizing
        # For backward compatibility: if no explicit position_sizer is provided,
        # use _default_size directly as units (legacy behavior).
        # If position_sizer is provided, it handles contract_size multiplication.
        self._position_sizer = position_sizer
        self._use_legacy_sizing = position_sizer is None
        self._initial_cash = float(initial_cash)
        self._current_equity = float(initial_cash)
        self._contract_size = float(self._instrument.get("contract_size", 10000.0))

    # ------------------------------------------------------------------ #
    # Public lifecycle
    # ------------------------------------------------------------------ #
    def on_clock_tick(self, frame: ClockFrame) -> None:
        """Advance bar counter and expire pending entries past their window."""
        del frame  # reserved for future use
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
            "end_of_data",
        }:
            reason_map = {
                "strategy_exit": "opposite_signal",
                "stop_loss": "stop-loss",
                "take_profit": "take-profit",
                "trailing_stop": "stop-loss",
                "end_of_data": "end_of_data",
            }
            exit_reason = reason_map.get(fill.reason, fill.reason)
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
        logger.debug(
            "entry_fill position_id=%s side=%s", position_id, state.decision.side
        )
        size = state.decision.size
        entry_mid = float(fill.price)
        entry_price = self._cost_model.get_entry_price(entry_mid, state.decision.side)
        entry_cost, breakdown = self._cost_model.compute_entry_cost(
            size=size, price=entry_mid, instrument=self._instrument
        )

        # Calculate initial risk for R-multiple tracking
        initial_risk_ccy = None
        stop_loss_price = None
        if state.decision.risk:
            stop_loss_price = state.decision.risk.get("entry_stop_loss")
            if stop_loss_price is not None:
                if state.decision.side == "long":
                    risk_distance = entry_mid - float(stop_loss_price)
                else:
                    risk_distance = float(stop_loss_price) - entry_mid
                # Convert to currency using size
                initial_risk_ccy = abs(risk_distance * size)

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
            initial_risk_ccy=initial_risk_ccy,
            stop_loss=stop_loss_price,
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

    def _handle_exit_fill(self, fill: FillEvent, reason: str) -> Trade | None:
        position_id = None
        if fill.intent is not None:
            position_id = self._intent_lookup.pop(id(fill.intent), None)
        if position_id is None and fill.decision is not None:
            position_id = self._decision_lookup.get(self._decision_key(fill.decision))
        if position_id is None:
            logger.debug(
                "exit_fill unmatched intent=%s decision=%s reason=%s",
                bool(fill.intent),
                bool(fill.decision),
                reason,
            )
            return None
        state = self._positions.get(position_id)
        if state is None:
            logger.debug(
                "exit_fill stale position_id=%s reason=%s",
                position_id,
                reason,
            )
            self._remove_intent_mapping(position_id)
            self._decision_lookup.pop(
                self._decision_key(fill.decision) if fill.decision else (), None
            )
            return None
        if state.position is None:
            raise PortfolioStateError("Exit fill matched invalid position state.")
        logger.debug(
            "exit_fill position_id=%s side=%s", position_id, state.decision.side
        )
        size = state.decision.size
        if size <= 0:
            raise PortfolioStateError("Tracked position has invalid size.")
        pos = state.position
        entry_mid = float(state.entry_mid_price or pos.entry_mid_price)
        exit_mid = float(fill.price)
        exit_price = self._cost_model.get_exit_price(exit_mid, pos.side)
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

        # Currency conversion: net_pnl is in native (quote) currency
        pnl_native = net_pnl
        native_currency = self._quote_ccy
        pnl_currency = "USD"

        # Convert P&L to reference currency (USD)
        if self._currency_converter is not None:
            pnl_converted = self._currency_converter.convert(
                amount=pnl_native,
                from_ccy=native_currency,
                timestamp=fill.timestamp,
                exit_price=exit_mid,
                symbol=self._symbol,
            )
        elif native_currency != "USD" and self._symbol.startswith("USD"):
            # Fallback for USD/XXX pairs when no converter available
            pnl_converted = pnl_native / exit_mid if exit_mid > 0 else pnl_native
        else:
            # No conversion available or needed
            pnl_converted = pnl_native

        # Calculate R-multiple using converted P&L
        r_multiple = None
        if pos.initial_risk_ccy is not None and pos.initial_risk_ccy > 0:
            r_multiple = pnl_converted / pos.initial_risk_ccy

        trade = Trade(
            symbol=pos.symbol,
            entry_time=pos.entry_time,
            exit_time=fill.timestamp,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            side=pos.side,
            size=size,
            pnl=pnl_converted,
            pnl_native=pnl_native,
            pnl_currency=pnl_currency,
            native_currency=native_currency,
            exit_reason=reason,
            mfe_currency=pos.mfe_currency,
            mae_currency=pos.mae_currency,
            bars_held=pos.bars_held,
            initial_risk_ccy=pos.initial_risk_ccy,
            r_multiple=r_multiple,
            cost_currency=total_cost,
            cost_breakdown=combined_breakdown,
            context_at_entry=pos.context_at_entry,
            context_at_exit=(
                fill.intent.decision.context
                if fill.intent
                else (fill.decision.context if fill.decision else None)
            ),
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
        )
        self.trades.append(trade)
        # Update equity for position sizing calculations
        self._current_equity += pnl_converted
        self._positions.pop(position_id, None)
        self._decision_lookup.pop(self._decision_key(state.decision), None)
        self._open_views.pop(position_id, None)
        self._remove_intent_mapping(position_id)
        return trade

    def _allocate_position_id(self, side: str) -> str:
        self._position_seq += 1
        return f"{side}-{self._position_seq}"

    def _with_size(self, decision: DecisionSnapshot) -> DecisionSnapshot:
        """Apply position sizing to a decision snapshot."""
        if self._use_legacy_sizing or self._position_sizer is None:
            # Legacy mode: use _default_size directly as units
            return replace(decision, size=self._default_size)
        # New mode: use position sizer with contract_size multiplication
        result = self._position_sizer.calculate_size(
            current_equity=self._current_equity,
            initial_equity=self._initial_cash,
            contract_size=self._contract_size,
        )
        return replace(decision, size=result.units)

    def get_current_position_size(self) -> float:
        """Get the current position size in broker units.

        This method is useful for external callers (like the engine)
        that need to know the position size before creating intents.
        """
        if self._use_legacy_sizing or self._position_sizer is None:
            # Legacy mode: return _default_size directly
            return self._default_size
        # New mode: use position sizer
        result = self._position_sizer.calculate_size(
            current_equity=self._current_equity,
            initial_equity=self._initial_cash,
            contract_size=self._contract_size,
        )
        return result.units

    def update_equity(self, equity: float) -> None:
        """Update the current equity for position sizing calculations.

        Call this after each trade closes or when equity changes
        (e.g., due to mark-to-market updates).

        Args:
            equity: Current account equity
        """
        self._current_equity = float(equity)

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

    def finalize_bar(self, bar: Any) -> None:
        self._update_open_positions(bar)

    def _update_open_positions(self, bar: Any) -> None:
        if not self._open_views:
            return
        high = self._extract_price(bar, "high")
        low = self._extract_price(bar, "low")
        close = self._extract_price(bar, "close")
        for state in self._positions.values():
            if state.state != "OPEN" or state.position is None:
                continue
            pos = state.position
            size = float(pos.size)
            entry_price = float(pos.entry_price)
            exit_mid = self._cost_model.get_exit_price(close, pos.side)
            if pos.side == "long":
                favorable = max(0.0, (high - entry_price) * size)
                adverse = max(0.0, (entry_price - low) * size)
                unrealized = (exit_mid - entry_price) * size
            else:
                favorable = max(0.0, (entry_price - low) * size)
                adverse = max(0.0, (high - entry_price) * size)
                unrealized = (entry_price - exit_mid) * size
            updated = Position(
                symbol=pos.symbol,
                entry_time=pos.entry_time,
                entry_price=pos.entry_price,
                entry_mid_price=pos.entry_mid_price,
                side=pos.side,
                size=pos.size,
                initial_risk_ccy=pos.initial_risk_ccy,
                stop_loss=pos.stop_loss,
                take_profit=pos.take_profit,
                bars_held=pos.bars_held + 1,
                mfe_currency=max(pos.mfe_currency, favorable),
                mae_currency=max(pos.mae_currency, adverse),
                unrealized_pnl=unrealized,
                context_at_entry=pos.context_at_entry,
            )
            state.position = updated
            if state.active_view is not None:
                state.active_view = ActivePosition(
                    position_id=state.position_id,
                    decision=state.decision,
                    position=updated,
                    entry_cost=state.entry_cost,
                    entry_cost_breakdown=dict(state.entry_cost_breakdown),
                )
                self._open_views[state.position_id] = state.active_view

    @staticmethod
    def _extract_price(bar: Any, field: str) -> float:
        if bar is None:
            return 0.0
        if isinstance(bar, dict):
            if field in bar and bar[field] is not None:
                return float(bar[field])
            nested = bar.get("bar")
            if nested is not None:
                return PortfolioManager._extract_price(nested, field)
        value = getattr(bar, field, None)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
        if hasattr(bar, "get"):
            value = bar.get(field)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0
