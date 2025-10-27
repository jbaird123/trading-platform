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
    Portfolio Manager - State Tracking and Decision Making

    The Portfolio Manager is responsible for:
    1. Tracking portfolio state (cash, positions, trades)
    2. Making decisions about when positions should be opened or closed
    3. Managing entry window state for command-based strategies

    The Portfolio Manager does NOT execute trades directly. Instead, it returns
    "action descriptors" - dictionaries that tell the caller (Backtester or
    Execution Layer) what action should be taken. The caller is responsible for
    determining WHEN to execute (e.g., current bar close vs next bar open).

    This separation of concerns allows the same Portfolio Manager logic to be
    used in both backtesting (with configurable execution models) and live
    trading (with real-time execution).

    Action Descriptor Examples:
    - {'action': 'open_entry_window', 'side': 'long', 'bar_index': 42}
    - {'action': 'should_close', 'reason': 'signal'}
    - {'action': 'no_action', 'reason': 'already_in_position'}

    See docs/architecture/execution_model.md for complete design details.
    """

    def __init__(
        self,
        base_currency: str,
        initial_cash: float = 100000.0,
        instrument: dict | None = None,
        cost_model: dict | None = None,
        precision_engine: PrecisionEngine | None = None,
    ):
        self.base_currency = base_currency
        assert (
            self.base_currency == "USD"
        ), "MVP only supports USD as the base currency."
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

        # Pending exit flag for execution model refactor
        # Set when close is needed but execution timing controlled by caller
        self._pending_exit: bool = False

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

        # Get the realistic fill price including spread
        fill_price = self._cost_model.get_entry_price(entry_price, side)

        # Ensure context_at_entry is a dict (not None) to keep downstream
        # code simpler and avoid AttributeError when accessing keys.
        ctx = context_at_entry or {}
        self._open_position = Position(
            symbol=symbol,
            side=side,
            entry_price=fill_price,
            entry_mid_price=entry_price,
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
        min_hold_bars: int = 0,
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
            min_hold_bars: Minimum bars to hold before allowing exits

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
                side,
                bar_index,
                entry_window_bars,
                allow_flip,
                current_bar,
                context,
                min_hold_bars,
            )

        # Exit commands
        elif command in ["exit_long", "exit_short"]:
            side = "long" if command == "exit_long" else "short"
            return self._handle_exit_command(side, current_bar, context, min_hold_bars)

        return {"action": "ignored", "reason": "unknown_command", "side": None}

    def _handle_entry_command(
        self,
        side: str,
        bar_index: int,
        entry_window_bars: int,
        allow_flip: bool,
        current_bar: pd.Series,
        context: dict | None,
        min_hold_bars: int = 0,
    ) -> dict[str, Any]:
        """
        Handle enter_long or enter_short command.

        Returns action descriptors instead of executing trades directly.
        The caller (Backtester) is responsible for execution timing.
        """

        # Case 2: Already in same-side position
        if self.current_position and self.current_position.side == side:
            return {
                "action": "no_action",
                "reason": "already_in_position",
                "side": side,
            }

        # Case 3: In opposite position (flip scenario)
        if self.current_position and self.current_position.side != side:
            # Check minimum hold time before allowing opposite_signal exit
            if self.current_position.bars_held < min_hold_bars:
                return {
                    "action": "no_action",
                    "reason": "min_hold_time_not_met",
                    "side": side,
                }

            # Set pending exit flag - exit will be executed by caller
            self._pending_exit = True

            # DO NOT open entry window yet - it will open after exit completes
            # Return should_close descriptor with entry_side for flip handling
            return {
                "action": "should_close",
                "reason": "opposite_signal",
                "entry_side": side,
                "bar_index": bar_index,
            }

        # Case 1: Flat (no position) - open entry window for this side
        self._entry_windows[side] = (bar_index, None)  # (window_start, last_entered)

        return {"action": "open_entry_window", "side": side, "bar_index": bar_index}

    def _handle_exit_command(
        self,
        side: str,
        current_bar: pd.Series,
        context: dict | None,
        min_hold_bars: int = 0,
    ) -> dict[str, Any]:
        """
        Handle exit_long or exit_short command.

        Returns action descriptors instead of executing trades directly.
        The caller (Backtester) is responsible for execution timing.
        """

        # Case 1: No position exists
        if not self.current_position:
            return {"action": "no_action", "reason": "no_position"}

        # Case 3: Exit command for opposite side
        if self.current_position.side != side:
            return {"action": "no_action", "reason": "wrong_side"}

        # Case 2: Exit command matches current position side
        # Check minimum hold time before allowing signal exits
        if self.current_position.bars_held < min_hold_bars:
            return {
                "action": "no_action",
                "reason": "min_hold_time_not_met",
                "side": side,
            }

        # Return should_close descriptor - execution deferred to caller
        return {"action": "should_close", "reason": "signal", "side": side}

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

    def complete_pending_exit_and_open_entry_window(
        self, side: str, bar_index: int
    ) -> dict[str, Any]:
        """
        Complete a pending exit and open entry window for new side.

        Called by Backtester after executing a flip exit. Clears the
        _pending_exit flag and opens entry window for the new side.

        Args:
            side: Side for new entry window ('long' or 'short')
            bar_index: Current bar index

        Returns:
            Action descriptor confirming entry window opened
        """
        # Sanity check: should only be called when pending exit is set
        assert (
            self._pending_exit
        ), "complete_pending_exit_and_open_entry_window called without pending exit"

        # Clear pending exit flag
        self._pending_exit = False

        # Open entry window for new side
        self._entry_windows[side] = (bar_index, None)

        return {"action": "entry_window_opened", "side": side, "bar_index": bar_index}

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
        # Fail loudly if instrument metadata is missing
        if not self.instrument:
            raise ValueError(
                "Instrument metadata is required for PnL calculation. "
                "Portfolio must be initialized with complete instrument definition."
            )

        # Fail loudly if required fields are missing
        if "point_value" not in self.instrument:
            raise ValueError(
                f"Instrument missing required 'point_value' field: {self.instrument}"
            )
        if "asset_class" not in self.instrument:
            raise ValueError(
                f"Instrument missing required 'asset_class' field: {self.instrument}"
            )
        if "symbol" not in self.instrument:
            raise ValueError(
                f"Instrument missing required 'symbol' field: {self.instrument}"
            )

        static_point_value: float = self.instrument["point_value"]
        asset_class: str = self.instrument["asset_class"]
        symbol: str = self.instrument["symbol"]

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
        """
        Increment bars_held and update MFE/MAE using bar extremes.
        Also calculate unrealized PnL using realistic exit price.
        """
        pos = self._open_position
        assert pos is not None
        size = pos.size
        entry = pos.entry_price
        high = float(current_bar["high"]) if "high" in current_bar else entry
        low = float(current_bar["low"]) if "low" in current_bar else entry
        close = float(current_bar["close"])

        # Get point_value for MFE/MAE calculation
        pv_high = self._get_point_value(entry, high)
        pv_low = self._get_point_value(entry, low)

        if pos.side == "long":
            favorable = max(0.0, (high - entry) * size * pv_high)
            adverse = max(0.0, (entry - low) * size * pv_low)
        else:
            favorable = max(0.0, (entry - low) * size * pv_low)
            adverse = max(0.0, (high - entry) * size * pv_high)

        # Calculate unrealized PnL using realistic exit price
        # This mirrors live broker behavior: includes full spread cost
        exit_price = self._cost_model.get_exit_price(close, pos.side)
        pv_close = self._get_point_value(entry, close)

        if pos.side == "long":
            unrealized = (exit_price - entry) * size * pv_close
        else:
            unrealized = (entry - exit_price) * size * pv_close

        self._open_position = Position(
            symbol=pos.symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            entry_mid_price=pos.entry_mid_price,
            size=pos.size,
            entry_time=pos.entry_time,
            bars_held=pos.bars_held + 1,
            mfe_currency=max(pos.mfe_currency, favorable),
            mae_currency=max(pos.mae_currency, adverse),
            unrealized_pnl=unrealized,
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

        # Calculate pnl_movement: pure mid-to-mid price movement
        entry_mid = self._open_position.entry_mid_price
        exit_mid = exit_price  # exit_price parameter is the mid-price

        if self._open_position.side == "long":
            mid_diff = self._engine.sub(exit_mid, entry_mid)
        else:
            mid_diff = self._engine.sub(entry_mid, exit_mid)

        # Get point_value for canonical PnL calculation
        point_value = self._get_point_value(entry_mid, exit_mid)

        # PnL from pure price movement (mid-to-mid)
        pnl_movement = self._engine.to_float(
            self._engine.mul(
                self._engine.mul(mid_diff, self._open_position.size), point_value
            )
        )

        # Calculate all costs
        cost_entry, breakdown_entry = self._cost_model.compute_entry_cost(
            self._open_position.size,
            price=entry_mid,
            instrument=self.instrument,
        )
        cost_exit, breakdown_exit = self._cost_model.compute_exit_cost(
            self._open_position.size, price=exit_mid, instrument=self.instrument
        )
        spread_cost_in_quote_ccy = self._cost_model.compute_spread_cost(
            self._open_position.size, instrument=self.instrument
        )

        # Convert spread cost to base currency if necessary. For pairs like
        # USD/JPY, the cost is in JPY and must be divided by the exit rate.
        spread_cost = spread_cost_in_quote_ccy
        if (
            self.instrument
            and self.instrument.get("asset_class") == "Forex"
            and self.instrument.get("symbol", "").startswith(self.base_currency)
            and exit_mid > 0
        ):
            spread_cost = spread_cost_in_quote_ccy / exit_mid

        commission_and_slippage_cost = cost_entry + cost_exit
        total_cost = commission_and_slippage_cost + spread_cost

        cost_breakdown = {
            "spread": spread_cost,
            "commission": breakdown_entry.get("commission", 0.0)
            + breakdown_exit.get("commission", 0.0),
            "slippage": breakdown_entry.get("slippage", 0.0)
            + breakdown_exit.get("slippage", 0.0),
        }

        # Final PnL = movement - all costs
        pnl = pnl_movement - total_cost

        # Get realistic fill prices for recording (including spread)
        entry_fill = self._cost_model.get_entry_price(
            entry_mid, self._open_position.side
        )
        exit_fill = self._cost_model.get_exit_price(exit_mid, self._open_position.side)

        initial_risk_ccy = self._open_position.initial_risk_ccy
        r_multiple = None
        if initial_risk_ccy is not None:
            try:
                if float(initial_risk_ccy) > 0:
                    r_multiple = pnl / initial_risk_ccy
            except (ValueError, TypeError):
                # Handle arrays, mocks, or invalid types
                pass

        # Ensure the recorded trade has a non-null context_at_entry for
        # reporting/brief generation convenience. Position.context_at_entry
        # was coerced to a dict at creation, but be defensive here as well.
        pos_dict = dict(self._open_position.__dict__)
        pos_dict["context_at_entry"] = pos_dict.get("context_at_entry") or {}

        # Update entry_price to fill price for Trade record
        pos_dict["entry_price"] = entry_fill

        # Remove Position-only fields (not needed in Trade)
        pos_dict.pop("entry_mid_price", None)
        pos_dict.pop("unrealized_pnl", None)

        trade = Trade(
            **pos_dict,
            exit_price=exit_fill,
            exit_time=exit_time,
            pnl=pnl,
            pnl_movement=pnl_movement,
            exit_reason=exit_reason,
            context_at_exit=context_at_exit,
            cost_currency=total_cost,
            cost_breakdown=cost_breakdown,
            r_multiple=r_multiple,
        )
        self.trades.append(trade)
        self.cash += pnl
        self._open_position = None
