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

from trading_platform.risk_manager.models import (
    ATRDistanceRule,
    DynamicREMConfig,
    DynamicTrailingStopRule,
    PartialExitRule,
    PriceOffsetRule,
)


class DynamicREM:
    """Dynamic Risk & Exit Manager with advanced position management.

    Features:
    - Breakeven stop trigger at specified R-multiple
    - Partial profit-taking at target levels
    - ATR-based trailing stops
    - Volatility-aware stop adjustments
    """

    def __init__(self, config: DynamicREMConfig | dict[str, Any]):
        """Initialize DynamicREM with configuration.

        Args:
            config: Configuration validated by DynamicREMConfig with:
                - stop_loss: REM stop rule payload (see `StopRule`)
                - take_profit: Optional REM stop rule payload
                - breakeven_threshold: R-multiple to trigger breakeven (optional)
                - partial_exits: Sequence of {r_multiple, fraction}
                - trailing_stop: Distance definition (`offset` or `atr`) with
                  optional `activate_after_partial`
                - volatility_threshold: ADX threshold for tightening (optional)
                - low_volatility_multiplier: Multiplier applied when ADX < threshold
        """
        if isinstance(config, DynamicREMConfig):
            model = config
        elif isinstance(config, dict):
            model = DynamicREMConfig(**config)
        else:
            raise TypeError(
                f"config must be DynamicREMConfig or dict, got {type(config)}"
            )

        self.config = model
        self.breakeven_threshold = model.breakeven_threshold
        self.partial_exits: list[PartialExitRule] = list(model.partial_exits)
        self.trailing_config: DynamicTrailingStopRule | None = model.trailing_stop
        self.volatility_threshold = model.volatility_threshold
        self.low_volatility_multiplier = model.low_volatility_multiplier

        # Task 34: Statistics tracking
        self.stats = {
            "breakeven_triggers": 0,
            "partial_exits_triggered": 0,
            "trailing_stop_activations": 0,
            "volatility_tightenings": 0,
        }

        # Track which partial exits have already been triggered per position
        self._triggered_partial_exits: dict[str, set[float]] = {}

    def _distance_value(
        self,
        rule: PriceOffsetRule | ATRDistanceRule,
        atr: float | None,
    ) -> float | None:
        """Resolve trailing distance into canonical price units."""

        if isinstance(rule, PriceOffsetRule):
            return float(rule.price_offset)
        if isinstance(rule, ATRDistanceRule):
            if atr is None:
                return None
            return float(rule.multiplier) * float(atr)
        raise TypeError(f"Unsupported distance rule: {type(rule)}")

    def _apply_volatility_multiplier(
        self,
        distance: float,
        context: dict[str, Any] | None,
    ) -> float:
        """Apply low-volatility tightening when ADX falls below threshold."""

        if self.volatility_threshold is None or context is None:
            return distance
        adx = context.get("adx")
        if adx is None or adx >= self.volatility_threshold:
            return distance
        self.stats["volatility_tightenings"] += 1
        return distance * self.low_volatility_multiplier

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

            trailing = self.trailing_config
            if trailing:
                activate_after_partial = trailing.activate_after_partial
                should_activate = True
                if activate_after_partial and not partial_exits_triggered:
                    should_activate = False

                if should_activate:
                    dist_raw = self._distance_value(trailing.distance, atr)
                    if dist_raw is not None:
                        dist_t = self._apply_volatility_multiplier(dist_raw, context)

                        size = float(position.size) if position.size else 1.0
                        mfe = float(position.mfe_currency or 0.0) / size

                        if position.side == "long":
                            peak = float(
                                max(position.entry_price, position.entry_price + mfe)
                            )
                            initial = position.entry_price - dist_t
                            trail_price = max(initial, peak - dist_t)
                            potential_peak = max(peak, float(current_price))
                            potential_trail = max(initial, potential_peak - dist_t)

                            if stop is None or trail_price > stop:
                                stop = trail_price
                                self.stats["trailing_stop_activations"] += 1
                            if stop is not None and potential_trail > stop:
                                stop = potential_trail
                        else:
                            trough = float(
                                min(position.entry_price, position.entry_price - mfe)
                            )
                            initial = position.entry_price + dist_t
                            trail_price = min(initial, trough + dist_t)
                            potential_trough = min(trough, float(current_price))
                            potential_trail = min(initial, potential_trough + dist_t)

                            if stop is None or trail_price < stop:
                                stop = trail_price
                                self.stats["trailing_stop_activations"] += 1
                            if stop is not None and potential_trail < stop:
                                stop = potential_trail

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

        # Type narrowing: initial_risk_ccy is now known to be non-zero float
        initial_risk: float = position.initial_risk_ccy

        # Calculate unrealized PnL
        if position.side == "long":
            pnl = (current_price - position.entry_price) * position.size
        else:  # short
            pnl = (position.entry_price - current_price) * position.size

        # R-multiple = PnL / Risk
        r_multiple: float = pnl / initial_risk
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

        # Get position identifier
        pos_id = f"{position.symbol}_{position.entry_time}"
        if pos_id not in self._triggered_partial_exits:
            self._triggered_partial_exits[pos_id] = set()

        # Check each partial exit target (Task 15)
        for exit_config in self.partial_exits:
            target_r = float(exit_config.r_multiple)
            fraction = float(exit_config.fraction)

            # Use epsilon for floating point comparison
            # Only trigger if not already triggered
            if (
                r_multiple >= (target_r - 1e-10)
                and target_r not in self._triggered_partial_exits[pos_id]
            ):
                orders.append(
                    {
                        "action": "close_partial",
                        "fraction": fraction,
                        "r_multiple": target_r,
                    }
                )
                # Mark this exit as triggered
                self._triggered_partial_exits[pos_id].add(target_r)
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
