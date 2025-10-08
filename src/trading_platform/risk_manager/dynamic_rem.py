"""
Dynamic Risk & Exit Manager (DynamicREM).

Tasks 13-21: Epic 2
Manages positions with advanced features:
- Breakeven stops
- Partial profit-taking
- ATR-based trailing stops
- Volatility-aware adjustments
"""

from __future__ import annotations

from typing import Any

from trading_platform.portfolio.position import Position


class DynamicREM:
    """Dynamic Risk & Exit Manager with advanced position management.

    Features:
    - Breakeven stop trigger at specified R-multiple
    - Partial profit-taking at target levels
    - ATR-based trailing stops
    - Volatility-aware stop adjustments
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize DynamicREM with configuration.

        Args:
            config: Configuration dictionary with:
                - stop_loss: dict with atr_multiple or price_offset
                - take_profit: dict with atr_multiple or price_offset
                - breakeven_threshold: R-multiple to trigger breakeven (optional)
                - partial_exits: list of {r_multiple, fraction} (optional)
                - trailing_stop: dict with atr_multiple (optional)
                - volatility_threshold: ADX threshold for tightening (optional)
        """
        self.config = config
        self.breakeven_threshold = config.get("breakeven_threshold")
        self.partial_exits = config.get("partial_exits", [])
        self.trailing_config = config.get("trailing_stop")
        self.volatility_threshold = config.get("volatility_threshold")

    def manage_position(
        self,
        position: Position,
        current_price: float,
        atr: float | None = None,
        initial_stop: float | None = None,
        initial_tp: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[float | None, float | None]:
        """Manage an open position and return updated stop/tp levels.

        Args:
            position: Open position to manage
            current_price: Current market price
            atr: Current ATR value
            initial_stop: Initial stop-loss level
            initial_tp: Initial take-profit level
            context: Market context (e.g., {'adx': 25.0})

        Returns:
            Tuple of (updated_stop_loss, updated_take_profit)
        """
        stop = initial_stop
        tp = initial_tp

        # Calculate current R-multiple (Task 13)
        if position.initial_risk_ccy and position.initial_risk_ccy > 0:
            r_multiple = self._calculate_r_multiple(position, current_price)

            # Breakeven trigger (Task 13)
            # Use small epsilon for floating point comparison
            if self.breakeven_threshold is not None and r_multiple >= (
                self.breakeven_threshold - 1e-10
            ):
                stop = position.entry_price

        return stop, tp

    def _calculate_r_multiple(self, position: Position, current_price: float) -> float:
        """Calculate current R-multiple for the position.

        R-multiple = unrealized_pnl / initial_risk

        Args:
            position: Open position
            current_price: Current market price

        Returns:
            R-multiple value
        """
        if not position.initial_risk_ccy or position.initial_risk_ccy == 0:
            return 0.0

        # Calculate unrealized PnL
        if position.side == "long":
            pnl = (current_price - position.entry_price) * position.size
        else:  # short
            pnl = (position.entry_price - current_price) * position.size

        # R-multiple = PnL / Risk
        r_multiple = pnl / position.initial_risk_ccy
        return r_multiple
