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
        self.low_volatility_multiplier = config.get("low_volatility_multiplier", 1.0)

        # Task 34: Statistics tracking
        self.stats = {
            "breakeven_triggers": 0,
            "partial_exits_triggered": 0,
            "trailing_stop_activations": 0,
            "volatility_tightenings": 0,
        }

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
        partial_exits_triggered = (
            context.get("partial_exits_triggered", []) if context else []
        )

        # Calculate current R-multiple (Task 13)
        if position.initial_risk_ccy and position.initial_risk_ccy > 0:
            r_multiple = self._calculate_r_multiple(position, current_price)

            # Breakeven trigger (Task 13)
            # Use small epsilon for floating point comparison
            if self.breakeven_threshold is not None and r_multiple >= (
                self.breakeven_threshold - 1e-10
            ):
                stop = position.entry_price
                # Task 34: Track breakeven triggers
                self.stats["breakeven_triggers"] += 1

            # ATR trailing stop after partial exit (Task 17)
            if (
                self.trailing_config
                and atr
                and partial_exits_triggered
                and self.trailing_config.get("activate_after_partial")
            ):
                atr_multiple = self.trailing_config.get("atr_multiple", 1.0)

                # Volatility-aware adjustment (Task 21)
                if self.volatility_threshold and context:
                    adx = context.get("adx")
                    if adx and adx < self.volatility_threshold:
                        # Tighten stop when volatility is low
                        atr_multiple *= self.low_volatility_multiplier
                        # Task 34: Track volatility tightenings
                        self.stats["volatility_tightenings"] += 1

                if position.side == "long":
                    trailing_stop = current_price - (atr_multiple * atr)
                    # Only move stop up, never down
                    if stop is None or trailing_stop > stop:
                        stop = trailing_stop
                        # Task 34: Track trailing stop activations
                        self.stats["trailing_stop_activations"] += 1
                else:  # short
                    trailing_stop = current_price + (atr_multiple * atr)
                    # Only move stop down, never up
                    if stop is None or trailing_stop < stop:
                        stop = trailing_stop
                        # Task 34: Track trailing stop activations
                        self.stats["trailing_stop_activations"] += 1

            # Simple trailing stop without partial exit requirement (Task 21)
            elif self.trailing_config and atr:
                atr_multiple = self.trailing_config.get("atr_multiple", 1.0)

                # Volatility-aware adjustment (Task 21)
                if self.volatility_threshold and context:
                    adx = context.get("adx")
                    if adx and adx < self.volatility_threshold:
                        atr_multiple *= self.low_volatility_multiplier
                        # Task 34: Track volatility tightenings
                        self.stats["volatility_tightenings"] += 1

                if position.side == "long":
                    trailing_stop = current_price - (atr_multiple * atr)
                    if stop is None or trailing_stop > stop:
                        stop = trailing_stop
                        # Task 34: Track trailing stop activations
                        self.stats["trailing_stop_activations"] += 1
                else:  # short
                    trailing_stop = current_price + (atr_multiple * atr)
                    if stop is None or trailing_stop < stop:
                        stop = trailing_stop
                        # Task 34: Track trailing stop activations
                        self.stats["trailing_stop_activations"] += 1

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

    def check_partial_exits(
        self, position: Position, current_price: float
    ) -> list[dict[str, Any]]:
        """Check if any partial exit targets have been reached.

        Args:
            position: Open position to check
            current_price: Current market price

        Returns:
            List of exit orders (dicts with action, fraction, r_multiple)
        """
        orders: list[dict[str, Any]] = []

        if not position.initial_risk_ccy or position.initial_risk_ccy == 0:
            return orders

        r_multiple = self._calculate_r_multiple(position, current_price)

        # Check each partial exit target (Task 15)
        for exit_config in self.partial_exits:
            target_r = exit_config.get("r_multiple", 0)
            fraction = exit_config.get("fraction", 0)

            # Use epsilon for floating point comparison
            if r_multiple >= (target_r - 1e-10):
                orders.append(
                    {
                        "action": "close_partial",
                        "fraction": fraction,
                        "r_multiple": target_r,
                    }
                )
                # Task 34: Track partial exits
                self.stats["partial_exits_triggered"] += 1

        return orders

    def get_stats(self) -> dict[str, int]:
        """Get DynamicREM statistics.

        Returns:
            Dictionary with breakeven_triggers, partial_exits_triggered,
            trailing_stop_activations, and volatility_tightenings counts
        """
        return self.stats.copy()
