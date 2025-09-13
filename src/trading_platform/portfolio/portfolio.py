from __future__ import annotations

from datetime import datetime

import pandas as pd
from trading_platform.portfolio.position import Position
from trading_platform.portfolio.trade import Trade


class PortfolioManager:
    """
    Manages the state of the portfolio, including cash, positions, and trades.

    This class is the single source of truth for the portfolio's state. It is
    used by both the backtester and the live execution layer to ensure
    consistent logic. For the MVP, it handles one position at a time.
    """

    def __init__(self, initial_cash: float = 100000.0):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self._open_position: Position | None = None
        self.trades: list[Trade] = []

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
        # Check for stop-loss or take-profit triggers first
        if self._open_position:
            position = self._open_position
            exit_triggered = False
            exit_price = 0.0
            exit_reason = None

            # Determine trigger prices based on position side
            if position.side == "long":
                # Check Stop Loss for Long Position
                if (
                    position.stop_loss is not None
                    and current_bar["low"] <= position.stop_loss
                ):
                    exit_triggered = True
                    exit_price = position.stop_loss
                    exit_reason = "stop-loss"

                # Check Take Profit for Long Position (only if SL not triggered)
                if (
                    not exit_triggered
                    and position.take_profit is not None
                    and current_bar["high"] >= position.take_profit
                ):
                    exit_triggered = True
                    exit_price = position.take_profit
                    exit_reason = "take-profit"

            elif position.side == "short":
                # Check Stop Loss for Short Position
                if (
                    position.stop_loss is not None
                    and current_bar["high"] >= position.stop_loss
                ):
                    exit_triggered = True
                    exit_price = position.stop_loss
                    exit_reason = "stop-loss"

                # Check Take Profit for Short Position (only if SL not triggered)
                if (
                    not exit_triggered
                    and position.take_profit is not None
                    and current_bar["low"] <= position.take_profit
                ):
                    exit_triggered = True
                    exit_price = position.take_profit
                    exit_reason = "take-profit"

            if exit_triggered:
                self.close_position(
                    exit_price=exit_price,
                    exit_time=current_bar.name,
                    exit_reason=exit_reason,
                )
                return  # Exit early if position was closed by SL/TP

        if self.current_position and current_signal != self.current_position.side:
            self.close_position(
                exit_price=current_bar["close"],
                exit_time=current_bar.name,
                exit_reason="signal",
            )
            if not allow_flip_on_bar:
                return  # Exit early if flips are not allowed

        # Entry decisions are orchestrated by the Backtester; no entry here.

    def close_position(
        self, exit_price: float, exit_time: datetime, exit_reason: str | None = None
    ) -> None:
        """Closes the current open position and records it as a Trade."""
        if not self._open_position:
            return

        pnl = (
            (exit_price - self._open_position.entry_price) * self._open_position.size
            if self._open_position.side == "long"
            else (self._open_position.entry_price - exit_price)
            * self._open_position.size
        )

        trade = Trade(
            **self._open_position.__dict__,
            exit_price=exit_price,
            exit_time=exit_time,
            pnl=pnl,
            exit_reason=exit_reason,
        )
        self.trades.append(trade)
        self.cash += pnl
        self._open_position = None
