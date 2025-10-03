from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pandas as pd
from trading_platform.core.costs import CostModel
from trading_platform.core.precision import FloatEngine, PrecisionEngine
from trading_platform.core.types import SignalCommand
from trading_platform.portfolio.position import Position
from trading_platform.portfolio.trade import Trade


class PortfolioManager:
    """
    Manages the state of the portfolio, including cash, positions, and trades.

    This class is the single source of truth for the portfolio's state. It is
    used by both the backtester and the live execution layer to ensure
    consistent logic. For the MVP, it handles one position at a time.
    """

    def __init__(
        self,
        initial_cash: float = 100000.0,
        instrument: dict | None = None,
        cost_model: dict | None = None,
        precision_engine: PrecisionEngine | None = None,
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self._open_position: Position | None = None
        self.trades: list[Trade] = []
        self.instrument: dict | None = instrument
        self._cost_model = CostModel.from_dict(cost_model)
        self._engine: PrecisionEngine = cast(
            PrecisionEngine,
            precision_engine if precision_engine is not None else FloatEngine(),
        )

        # Entry window tracking for command-based entry management
        # Format: {side: (window_start_bar_index, last_entered_bar_index)}
        # window_start_bar_index: when entry command was received for this side
        # last_entered_bar_index: last bar where we entered on this command
        # (None if not entered)
        self._entry_windows: dict[str, tuple[int, int | None]] = {
            "long": (-1, None),
            "short": (-1, None),
        }

    @property
    def current_position(self) -> Position | None:
        """Public read-only access to the current open position, if any."""
        return self._open_position

    def create_new_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        entry_time: datetime,
        instrument: dict | None = None,
        context_at_entry: dict | None = None,
        initial_risk_ccy: float | None = None,
    ) -> None:
        """Creates and holds a new open position."""
        if self._open_position:
            return

        if instrument is not None:
            self.instrument = instrument

        # Ensure context_at_entry is a dict (not None) to keep downstream
        # code simpler and avoid AttributeError when accessing keys.
        ctx = context_at_entry or {}
        self._open_position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            entry_time=entry_time,
            context_at_entry=ctx,
            initial_risk_ccy=initial_risk_ccy,
        )

    def process_command(
        self,
        command: SignalCommand,
        bar_index: int,
        warmup_threshold: int,
        entry_window_bars: int,
        allow_flip: bool,
        current_bar: pd.Series,
        context: dict | None = None,
    ) -> dict[str, Any]:
        """
        Process a strategy command and manage portfolio state.

        This is the central method for command-based signal processing,
        implementing [PM-5.8] Entry Window Management.

        Args:
            command: The signal command from strategy
            bar_index: Current bar index
            warmup_threshold: Bar index where warmup ends
            entry_window_bars: Entry window policy (0, N, or -1)
            allow_flip: Whether to allow flipping positions
            current_bar: Current market data bar
            context: Strategy context (regime, indicators, etc.)

        Returns:
            Dictionary with:
            - "action": "entered" | "exited" | "ignored" | "window_opened"
                | "window_active"
            - "side": "long" | "short" | None
            - "reason": str (if ignored)
        """
        # Skip warmup period
        if bar_index < warmup_threshold:
            return {"action": "ignored", "reason": "warmup", "side": None}

        # Handle None/null commands - check for active entry windows
        if command is None:
            return self._check_active_entry_windows(
                bar_index, entry_window_bars, current_bar, context
            )

        # Entry commands
        if command in ["enter_long", "enter_short"]:
            side = "long" if command == "enter_long" else "short"
            return self._handle_entry_command(
                side, bar_index, entry_window_bars, allow_flip, current_bar, context
            )

        # Exit commands
        elif command in ["exit_long", "exit_short"]:
            side = "long" if command == "exit_long" else "short"
            return self._handle_exit_command(side, current_bar, context)

        return {"action": "ignored", "reason": "unknown_command", "side": None}

    def _handle_entry_command(
        self,
        side: str,
        bar_index: int,
        entry_window_bars: int,
        allow_flip: bool,
        current_bar: pd.Series,
        context: dict | None,
    ) -> dict[str, Any]:
        """Handle enter_long or enter_short command."""

        # Already in same-side position
        if self.current_position and self.current_position.side == side:
            return {"action": "ignored", "reason": "already_in_position", "side": side}

        # In opposite position - always close per Decision 1
        if self.current_position and self.current_position.side != side:
            self.close_position(
                exit_price=current_bar["close"],
                exit_time=cast(datetime, current_bar.name),
                exit_reason="opposite_signal",
                context_at_exit=context,
            )
            # After closing, check if we should open entry window
            if not allow_flip:
                # Just exit, don't open entry window
                return {"action": "exited", "side": side, "reason": "opposite_signal"}
            # Fall through to open entry window for flip

        # Flat or just closed - open entry window for this side
        self._entry_windows[side] = (bar_index, None)  # (window_start, last_entered)

        return {"action": "window_opened", "side": side}

    def _handle_exit_command(
        self, side: str, current_bar: pd.Series, context: dict | None
    ) -> dict[str, Any]:
        """Handle exit_long or exit_short command."""

        if self.current_position and self.current_position.side == side:
            self.close_position(
                exit_price=current_bar["close"],
                exit_time=cast(datetime, current_bar.name),
                exit_reason="signal",
                context_at_exit=context,
            )
            return {"action": "exited", "side": side}
        else:
            return {
                "action": "ignored",
                "reason": "no_matching_position",
                "side": side,
            }

    def _check_active_entry_windows(
        self,
        bar_index: int,
        entry_window_bars: int,
        current_bar: pd.Series,
        context: dict | None,
    ) -> dict[str, Any]:
        """Check if we have active entry windows to maintain (for None commands)."""

        # This allows entry windows to stay open across bars with None commands
        # Backtester will check if entry is now possible (e.g., RMM unblocked)

        for side in ["long", "short"]:
            window_start, last_entered = self._entry_windows[side]

            if window_start >= 0 and last_entered is None:  # Window open, not entered
                bars_since_start = bar_index - window_start

                if entry_window_bars == -1 or bars_since_start <= entry_window_bars:
                    return {"action": "window_active", "side": side}

        return {"action": "ignored", "reason": "no_active_command", "side": None}

    def can_attempt_entry(
        self, side: str, bar_index: int, entry_window_bars: int
    ) -> bool:
        """
        Check if we can attempt entry for this side (used by backtester).

        Args:
            side: Position side ("long" or "short")
            bar_index: Current bar index
            entry_window_bars: Entry window policy

        Returns:
            True if entry can be attempted, False otherwise
        """
        window_start, last_entered = self._entry_windows[side]

        if window_start < 0 or last_entered is not None:
            return False  # No window open or already entered

        bars_since_start = bar_index - window_start

        if entry_window_bars == -1:
            return True  # Infinite window

        return bars_since_start <= entry_window_bars

    def _get_point_value(self, entry_price: float, exit_price: float) -> float:
        """
        Calculate the point value for PnL conversion to base currency.

        Implements instrument-agnostic PnL calculation per [SYS-1.3.1].

        For forex pairs where USD is the quote currency (EUR/USD, GBP/USD):
            - point_value = 1.0 (1 pip ≈ $1 per 10k units)
        For forex pairs where USD is the base currency (USD/JPY, USD/CHF):
            - point_value = 1.0 / avg_price (dynamic conversion)
        For stocks:
            - point_value = 1.0 (per share)
        For futures:
            - point_value = contract_multiplier

        Returns:
            float: The conversion factor from price units to base currency
        """
        if not self.instrument:
            # Default fallback: assume 1:1 conversion
            return 1.0

        static_point_value: float = self.instrument.get("point_value", 1.0)
        asset_class: str = self.instrument.get("asset_class", "Unknown")
        symbol: str = self.instrument.get("symbol", "")

        # For Forex USD/XXX pairs, use dynamic conversion
        if asset_class == "Forex" and symbol.startswith("USD"):
            # Use average price for conversion
            avg_price = (entry_price + exit_price) / 2.0
            return static_point_value / avg_price

        # For all other instruments, use static point_value
        return static_point_value

    def hit_daily_loss_cap(self, ts: datetime, cap: float) -> bool:
        """Return True if realized PnL for ts.date() is <= -cap."""
        if cap is None or cap <= 0:
            return False
        d = ts.date()
        day_pnl = sum(float(t.pnl) for t in self.trades if t.exit_time.date() == d)
        return day_pnl <= -float(cap)

    def on_bar(
        self,
        current_bar: pd.Series,
        current_signal: str,
        allow_flip_on_bar: bool = False,
        context: dict | None = None,
    ) -> None:
        """
        Processes a new bar of data, updating positions based on the signal.
        """
        if self._open_position is not None:
            self._update_position_metrics(current_bar)

        if self.current_position and current_signal != self.current_position.side:
            self._handle_signal_change(current_bar, allow_flip_on_bar, context)

    def check_stop_loss(self, current_bar: pd.Series, stop_price: float) -> bool:
        position = self._open_position
        if position is None or stop_price <= 0:
            return False
        if position.side == "long":
            return bool(current_bar["low"] <= stop_price)
        else:  # short
            return bool(current_bar["high"] >= stop_price)

    def check_take_profit(self, current_bar: pd.Series, profit_price: float) -> bool:
        position = self._open_position
        if position is None or profit_price <= 0:
            return False
        if position.side == "long":
            return bool(current_bar["high"] >= profit_price)
        else:  # short
            return bool(current_bar["low"] <= profit_price)

    def _handle_signal_change(
        self, current_bar: pd.Series, allow_flip_on_bar: bool, context: dict | None
    ) -> None:
        self.close_position(
            exit_price=current_bar["close"],
            exit_time=cast(datetime, current_bar.name),
            exit_reason="signal",
            context_at_exit=context,
        )
        if not allow_flip_on_bar:
            return  # pragma: no cover

    def _update_position_metrics(self, current_bar: pd.Series) -> None:
        """Increment bars_held and update MFE/MAE using bar extremes."""
        pos = self._open_position
        assert pos is not None
        size = pos.size
        entry = pos.entry_price
        high = float(current_bar["high"]) if "high" in current_bar else entry
        low = float(current_bar["low"]) if "low" in current_bar else entry

        # Get point_value for MFE/MAE calculation
        pv_high = self._get_point_value(entry, high)
        pv_low = self._get_point_value(entry, low)

        if pos.side == "long":
            favorable = max(0.0, (high - entry) * size * pv_high)
            adverse = max(0.0, (entry - low) * size * pv_low)
        else:
            favorable = max(0.0, (entry - low) * size * pv_low)
            adverse = max(0.0, (high - entry) * size * pv_high)

        self._open_position = Position(
            symbol=pos.symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            size=pos.size,
            entry_time=pos.entry_time,
            bars_held=pos.bars_held + 1,
            mfe_currency=max(pos.mfe_currency, favorable),
            mae_currency=max(pos.mae_currency, adverse),
            initial_risk_ccy=pos.initial_risk_ccy,
            context_at_entry=pos.context_at_entry,  # Preserve the context!
        )

    def close_position(
        self,
        exit_price: float,
        exit_time: datetime,
        exit_reason: str | None = None,
        context_at_exit: dict[str, Any] | None = None,
    ) -> None:
        """Closes the current open position and records it as a Trade."""
        if not self._open_position:
            return

        if self._open_position.side == "long":
            diff = self._engine.sub(exit_price, self._open_position.entry_price)
        else:
            diff = self._engine.sub(self._open_position.entry_price, exit_price)

        # Get point_value from instrument definition for canonical PnL calc
        point_value = self._get_point_value(self._open_position.entry_price, exit_price)

        # Canonical PnL: (price_change * size * point_value)
        pnl_gross = self._engine.to_float(
            self._engine.mul(
                self._engine.mul(diff, self._open_position.size), point_value
            )
        )
        cost_entry, breakdown_entry = self._cost_model.compute_entry_cost(
            self._open_position.size,
            price=self._open_position.entry_price,
            instrument=self.instrument,
        )
        cost_exit, breakdown_exit = self._cost_model.compute_exit_cost(
            self._open_position.size, price=exit_price, instrument=self.instrument
        )
        total_cost = cost_entry + cost_exit
        cost_breakdown = {
            "spread": breakdown_entry.get("spread", 0.0)
            + breakdown_exit.get("spread", 0.0),
            "commission": breakdown_entry.get("commission", 0.0)
            + breakdown_exit.get("commission", 0.0),
            "slippage": breakdown_entry.get("slippage", 0.0)
            + breakdown_exit.get("slippage", 0.0),
        }
        pnl = pnl_gross - total_cost

        initial_risk_ccy = self._open_position.initial_risk_ccy
        r_multiple = None
        if initial_risk_ccy and initial_risk_ccy > 0:
            r_multiple = pnl / initial_risk_ccy

        # Ensure the recorded trade has a non-null context_at_entry for
        # reporting/brief generation convenience. Position.context_at_entry
        # was coerced to a dict at creation, but be defensive here as well.
        pos_dict = dict(self._open_position.__dict__)
        pos_dict["context_at_entry"] = pos_dict.get("context_at_entry") or {}
        trade = Trade(
            **pos_dict,
            exit_price=exit_price,
            exit_time=exit_time,
            pnl=pnl,
            pnl_gross=pnl_gross,
            exit_reason=exit_reason,
            context_at_exit=context_at_exit,
            cost_currency=total_cost,
            cost_breakdown=cost_breakdown,
            r_multiple=r_multiple,
        )
        self.trades.append(trade)
        self.cash += pnl
        self._open_position = None
