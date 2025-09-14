from __future__ import annotations

from datetime import datetime
from typing import cast

import pandas as pd
from trading_platform.core.costs import CostModel
from trading_platform.core.precision import FloatEngine, PrecisionEngine
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
        # Optional instrument snapshot (scaffold; not used for PnL yet)
        self.instrument: dict | None = instrument
        self._cost_model = CostModel.from_dict(cost_model)
        # Default to float engine (BT); live can pass DecimalEngine for money math.
        self._engine: PrecisionEngine = cast(
            PrecisionEngine,
            precision_engine if precision_engine is not None else FloatEngine(),
        )

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
        stop_loss: float | None = None,
        take_profit: float | None = None,
        instrument: dict | None = None,
    ) -> None:
        """Creates and holds a new open position."""
        if self._open_position:
            # For simplicity, we don't handle multiple open positions for now.
            return
        # Interpret provided stop_loss/take_profit as offsets from entry_price
        sl_level = None
        tp_level = None
        if stop_loss is not None:
            sl_level = (
                entry_price - stop_loss if side == "long" else entry_price + stop_loss
            )
        if take_profit is not None:
            tp_level = (
                entry_price + take_profit
                if side == "long"
                else entry_price - take_profit
            )

        if instrument is not None:
            # Update current instrument snapshot for this position lifecycle
            self.instrument = instrument

        self._open_position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            entry_time=entry_time,
            stop_loss=sl_level,
            take_profit=tp_level,
        )

    def on_bar(
        self,
        current_bar: pd.Series,
        current_signal: str,
        allow_flip_on_bar: bool = False,
    ) -> None:
        """
        Processes a new bar of data, updating positions based on the signal.
        This will become the primary interface for the backtester.
        """
        # 1) Exit triggers (SL/TP)
        if self._open_position:
            should_exit, price, reason = self._check_exit_triggers(current_bar)
            if should_exit:
                self.close_position(
                    exit_price=price,
                    exit_time=cast(datetime, current_bar.name),
                    exit_reason=reason,
                )
                return

        # 2) Signal reversal handling
        if self.current_position and current_signal != self.current_position.side:
            self._handle_signal_change(current_bar, allow_flip_on_bar)

        # 3) Entry is orchestrated by Backtester; no action here.

    def _check_exit_triggers(
        self, current_bar: pd.Series
    ) -> tuple[bool, float, str | None]:
        position = self._open_position
        assert position is not None
        # Initialize
        exit_triggered = False
        exit_price = 0.0
        exit_reason: str | None = None

        if position.side == "long":
            # Stop first
            if (
                position.stop_loss is not None
                and current_bar["low"] <= position.stop_loss
            ):
                exit_triggered = True
                exit_price = position.stop_loss
                exit_reason = "stop-loss"
            # Then TP
            if (
                not exit_triggered
                and position.take_profit is not None
                and current_bar["high"] >= position.take_profit
            ):
                exit_triggered = True
                exit_price = position.take_profit
                exit_reason = "take-profit"
        else:  # short
            # Stop first
            if (
                position.stop_loss is not None
                and current_bar["high"] >= position.stop_loss
            ):
                exit_triggered = True
                exit_price = position.stop_loss
                exit_reason = "stop-loss"
            # Then TP
            if (
                not exit_triggered
                and position.take_profit is not None
                and current_bar["low"] <= position.take_profit
            ):
                exit_triggered = True
                exit_price = position.take_profit
                exit_reason = "take-profit"
        return exit_triggered, exit_price, exit_reason

    def _handle_signal_change(
        self, current_bar: pd.Series, allow_flip_on_bar: bool
    ) -> None:
        self.close_position(
            exit_price=current_bar["close"],
            exit_time=cast(datetime, current_bar.name),
            exit_reason="signal",
        )
        if not allow_flip_on_bar:
            # Exit early if flips are not allowed
            return  # pragma: no cover

    def close_position(
        self, exit_price: float, exit_time: datetime, exit_reason: str | None = None
    ) -> None:
        """Closes the current open position and records it as a Trade."""
        if not self._open_position:
            return

        # Use precision engine for PnL arithmetic to segregate float (BT)
        # vs decimal (EL) and reduce rounding issues
        if self._open_position.side == "long":
            diff = self._engine.sub(exit_price, self._open_position.entry_price)
        else:
            diff = self._engine.sub(self._open_position.entry_price, exit_price)
        pnl_gross = self._engine.to_float(
            self._engine.mul(diff, self._open_position.size)
        )
        cost_entry, breakdown_entry = self._cost_model.compute_entry_cost(
            self._open_position.size,
            price=self._open_position.entry_price,
            instrument=self.instrument,
        )  # noqa: E501
        cost_exit, breakdown_exit = self._cost_model.compute_exit_cost(
            self._open_position.size,
            price=exit_price,
            instrument=self.instrument,
        )  # noqa: E501
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

        # Compute initial risk for r-multiple if stop_loss was defined at entry
        initial_risk_ccy = None
        if self._open_position.stop_loss is not None:
            if self._open_position.side == "long":
                initial_risk_ccy = max(
                    0.0,
                    (self._open_position.entry_price - self._open_position.stop_loss)
                    * self._open_position.size,
                )
            else:
                initial_risk_ccy = max(
                    0.0,
                    (self._open_position.stop_loss - self._open_position.entry_price)
                    * self._open_position.size,
                )
        r_multiple = None
        if initial_risk_ccy and initial_risk_ccy > 0:
            r_multiple = pnl / initial_risk_ccy

        trade = Trade(
            **self._open_position.__dict__,
            exit_price=exit_price,
            exit_time=exit_time,
            pnl=pnl,
            exit_reason=exit_reason,
            cost_currency=total_cost,
            cost_breakdown=cost_breakdown,
            r_multiple=r_multiple,
        )
        self.trades.append(trade)
        self.cash += pnl
        self._open_position = None
