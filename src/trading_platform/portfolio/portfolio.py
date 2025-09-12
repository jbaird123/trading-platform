from __future__ import annotations

from datetime import datetime

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

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        size: float,
        entry_time: datetime,
    ) -> None:
        """Creates and holds a new open position."""
        if self._open_position:
            # For simplicity, we don't handle multiple open positions for now.
            return
        self._open_position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            size=size,
            entry_time=entry_time,
        )

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
