from __future__ import annotations

import logging
from typing import Any, cast

import pandas as pd

import trading_platform.risk_manager.rem_indicators as rem_indicators
from trading_platform.core.signal import Signal
from trading_platform.core.types import BarData
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.exit_utils import (
    is_fixed_stops_ambiguous,
    is_trailing_stop_ambiguous,
)
from trading_platform.risk_manager.models import (
    AbsoluteLevelRule,
    FixedPipsRule,
    IndicatorRule,
    PriceOffsetRule,
    ReferenceRule,
    REMConfig,
    TrailingStopRule,
)
from trading_platform.risk_manager.trailing_stop_utils import (
    process_1min_bars_for_fixed_stops,
    process_1min_bars_for_trailing_stop,
)

logger = logging.getLogger(__name__)


class _ContextBarView:
    def __init__(self, base: BarData, context: dict[str, Any]) -> None:
        self._base = base
        sections: list[dict[str, Any]] = []
        for key in ("strategy_features", "global_features"):
            payload = context.get(key)
            if isinstance(payload, dict):
                sections.append(payload)
        self._sections = sections

    @property
    def name(self) -> Any:
        return getattr(self._base, "name", None)

    def __contains__(self, key: str) -> bool:
        if key in self._base:
            return True
        for section in self._sections:
            if key in section:
                return True
        return False

    def __getitem__(self, key: str) -> Any:
        if key in self._base:
            return self._base[key]
        for section in self._sections:
            if key in section:
                return section[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


class RiskExitManager:
    """
    Manages risk and exit conditions for open positions.

    This class is responsible for loading and interpreting a risk configuration
    and determining if a position should be closed based on stop-loss or
    take-profit rules.
    """

    def __init__(
        self,
        config: REMConfig | dict[str, Any] | None = None,
        instrument: dict | None = None,
        exit_tie_break: str = "stop_then_tp",
    ):
        """
        Initializes the RiskExitManager with a validated risk configuration.

        Args:
            config: A validated REMConfig instance or dict. If dict is provided,
                    it will be validated against REMConfig schema (extra fields
                    forbidden, only whitelisted indicators). Legacy dict format
                    with advanced features (reference_price, trailing_stop) bypass
                    validation for backward compatibility during migration.
            instrument: A dictionary with instrument-specific metadata.
            exit_tie_break: Policy for when both SL and TP are hit on same bar.
                          "stop_then_tp" (default): Check stop-loss first
                          "tp_then_stop": Check take-profit first
        """
        if config is None:
            self.config: REMConfig | None = None
        elif isinstance(config, REMConfig):
            self.config = config
        elif isinstance(config, dict):
            if not config:
                self.config = None
            else:
                self.config = REMConfig(**config)
        else:
            raise TypeError(
                f"config must be REMConfig, dict, or None, got {type(config)}"
            )

        self.instrument = instrument or {}
        self.exit_tie_break = exit_tie_break

    def _pip_size(self) -> float:
        """Retrieve pip size from instrument metadata."""
        pip_location = self.instrument.get("pip_location")
        if pip_location is None:
            raise ValueError(
                "pip_location missing from instrument definition. "
                "Cannot calculate pip-based offsets for non-Forex instruments."
            )
        return float(pip_location)

    def _distance_value(self, rule: PriceOffsetRule | FixedPipsRule) -> float:
        """Resolve a distance rule into canonical price units."""
        if isinstance(rule, PriceOffsetRule):
            return float(rule.price_offset)
        if isinstance(rule, FixedPipsRule):
            return float(rule.pips) * self._pip_size()
        raise TypeError(f"Unsupported distance rule type: {type(rule)}")

    def _context_value(
        self, reference_point: str, signal_context: dict[str, Any]
    ) -> float | None:
        """Extract a contextual value using dot notation."""
        if not reference_point.startswith("context."):
            return None
        key = reference_point.replace("context.", "", 1)
        if "strategy_features" in signal_context:
            val = signal_context["strategy_features"].get(key)
            if val is not None:
                return float(val)
        val = signal_context.get(key)
        return float(val) if val is not None else None

    def _indicator_price(
        self,
        rule: IndicatorRule,
        position: Position,
        current_bar: BarData,
        signal_context: dict[str, Any],
        prior_bar: BarData | None = None,
    ) -> float:
        """Compute price level using an indicator-driven stop calculator.

        Args:
            rule: Indicator rule configuration
            position: Current position
            current_bar: Bar being checked for exits
            prior_bar: Bar whose close set the stop level (for indicator calculation)

        Returns:
            Stop price level
        """
        spec = rem_indicators.REM_INDICATORS_REGISTRY.get(rule.indicator)
        if spec is None:
            raise ValueError(f"Indicator '{rule.indicator}' not registered")

        if spec.requires_prior_bar and prior_bar is None:
            raise ValueError(
                f"Indicator '{rule.indicator}' requires prior bar data but "
                "no prior_bar was provided."
            )

        base_bar = prior_bar if prior_bar is not None else current_bar
        needs_overlay = any(
            isinstance(signal_context.get(key), dict) and signal_context.get(key)
            for key in ("strategy_features", "global_features")
        )
        calculation_bar: BarData | _ContextBarView
        if needs_overlay:
            calculation_bar = _ContextBarView(base_bar, signal_context)
        else:
            calculation_bar = base_bar

        params = dict(rule.params)
        calc_input: Any = calculation_bar
        price = float(
            spec.stop_calculator(
                float(position.entry_price),
                position.side,
                calc_input,
                params,
            )
        )

        logger.debug(
            "indicator_stop_calculated",
            extra={
                "symbol": position.symbol,
                "indicator": rule.indicator,
                "side": position.side,
                "calc_bar_time": str(getattr(calculation_bar, "name", "")),
                "price": price,
                "params": params,
            },
        )

        return price

    def _resolve_stop_rule(
        self,
        rule: (
            AbsoluteLevelRule
            | PriceOffsetRule
            | FixedPipsRule
            | IndicatorRule
            | ReferenceRule
        ),
        position: Position,
        current_bar: BarData,
        signal_context: dict[str, Any],
        *,
        is_stop: bool,
        prior_bar: BarData | None = None,
    ) -> float | None:
        """Convert a stop rule into a concrete price level."""
        entry = float(position.entry_price)
        side = position.side

        if isinstance(rule, AbsoluteLevelRule):
            return float(rule.price)

        if isinstance(rule, PriceOffsetRule):
            distance = self._distance_value(rule)
        elif isinstance(rule, FixedPipsRule):
            distance = self._distance_value(rule)
        elif isinstance(rule, IndicatorRule):
            return self._indicator_price(
                rule, position, current_bar, signal_context, prior_bar
            )
        elif isinstance(rule, ReferenceRule):
            base_price = self._context_value(rule.reference_point, signal_context)
            if base_price is None:
                return None
            if rule.offset is None:
                return base_price
            distance = self._distance_value(rule.offset)
            if side == "long":
                return (
                    float(base_price) - distance
                    if is_stop
                    else float(base_price) + distance
                )
            return (
                float(base_price) + distance
                if is_stop
                else float(base_price) - distance
            )
        else:
            raise TypeError(f"Unsupported stop rule type: {type(rule)}")

        if side == "long":
            return entry - distance if is_stop else entry + distance
        return entry + distance if is_stop else entry - distance

    @staticmethod
    def _trailing_stop_updates_intrabar(
        trailing_rule: TrailingStopRule | None,
    ) -> bool:
        """Return True when trailing stop needs intrabar sequencing."""
        if trailing_rule is None:
            return False
        update_mode = trailing_rule.update or "tick"
        return update_mode == "tick"

    def calculate_initial_stop_price(
        self,
        entry_price: float,
        side: str,
        entry_bar: BarData,
        signal_context: dict[str, Any],
        prior_bar: BarData | None = None,
    ) -> float | None:
        """
        Calculate the initial stop loss price at position entry time.

        This method is called BEFORE creating a position to determine the initial
        risk for r_multiple calculation.

        Args:
            entry_price: The entry price for the position
            side: "long" or "short"
            entry_bar: The bar on which entry occurs
            signal_context: Signal context dict with strategy_features, etc.
            prior_bar: The bar immediately before entry_bar (for indicator stops)

        Returns:
            Initial stop loss price, or None if no stop loss configured
        """
        if self.config is None or self.config.stop_loss is None:
            return None

        # Create a minimal Position-like object for _resolve_stop_rule
        # We only need the fields that _resolve_stop_rule actually uses
        from types import SimpleNamespace

        temp_position = SimpleNamespace(
            entry_price=entry_price,
            side=side,
            symbol="",  # Not used in _resolve_stop_rule
            size=1.0,  # Not used in _resolve_stop_rule
        )

        return self._resolve_stop_rule(
            self.config.stop_loss,
            temp_position,  # type: ignore[arg-type]
            entry_bar,
            signal_context,
            is_stop=True,
            prior_bar=prior_bar,
        )

    def calculate_initial_take_profit_price(
        self,
        entry_price: float,
        side: str,
        entry_bar: BarData,
        signal_context: dict[str, Any],
        prior_bar: BarData | None = None,
    ) -> float | None:
        """
        Calculate the initial take profit price at position entry time.

        Args:
            entry_price: The entry price for the position
            side: "long" or "short"
            entry_bar: The bar on which entry occurs
            signal_context: Signal context dict with strategy_features, etc.
            prior_bar: The bar immediately before entry_bar (for indicator stops)

        Returns:
            Initial take profit price, or None if no take profit configured
        """
        if self.config is None or self.config.take_profit is None:
            return None

        # Create a minimal Position-like object for _resolve_stop_rule
        from types import SimpleNamespace

        temp_position = SimpleNamespace(
            entry_price=entry_price,
            side=side,
            symbol="",  # Not used in _resolve_stop_rule
            size=1.0,  # Not used in _resolve_stop_rule
        )

        return self._resolve_stop_rule(
            self.config.take_profit,
            temp_position,  # type: ignore[arg-type]
            entry_bar,
            signal_context,
            is_stop=False,
            prior_bar=prior_bar,
        )

    def check_exits(
        self,
        position: Position,
        current_bar: BarData,
        signal: Any = None,
        data_handler: Any = None,
        prior_bar: BarData | None = None,
        *,
        bar_minutes: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Checks if any exit conditions are met for the given position.

        Args:
            position: The current position to check exits for
            current_bar: The current market bar data (bar being checked for exits)
            signal: Optional Signal object with context data
            data_handler: Optional DataHandler for 1-minute resolution zoom
            prior_bar: The completed bar immediately before current_bar.
                      Used for indicator-based stops which are calculated using
                      the prior bar's closing data (close, ATR, etc.). This matches
                      live trading where stops are set when a bar closes based on
                      that bar's data, then active for the next bar.

        Returns:
            A dictionary with the exit details if an exit is triggered,
            otherwise None.
        """
        if self.config is None:
            return None

        stop_rule = self.config.stop_loss
        take_profit_rule = self.config.take_profit
        trailing_rule = self.config.trailing_stop
        trailing_updates_intrabar = self._trailing_stop_updates_intrabar(trailing_rule)

        # Extract signal context if available
        # Prefer position's entry context (persisted), fallback to current signal
        signal_context = {}
        if position.context_at_entry:
            signal_context = position.context_at_entry
        elif signal is not None and isinstance(signal, Signal):
            signal_context = signal.context or {}

        sl_price = self._resolve_stop_rule(
            stop_rule,
            position,
            current_bar,
            signal_context,
            is_stop=True,
            prior_bar=prior_bar,
        )
        tp_price = (
            self._resolve_stop_rule(
                take_profit_rule,
                position,
                current_bar,
                signal_context,
                is_stop=False,
                prior_bar=prior_bar,
            )
            if take_profit_rule is not None
            else None
        )

        # Trailing stop based on MFE; derived from Position.mfe_currency and size
        trail_price: float | None = None
        if trailing_rule is not None:
            dist_t = self._distance_value(trailing_rule.distance)
            if dist_t is not None:
                size = float(position.size) if position.size else 1.0
                mfe = float(position.mfe_currency or 0.0) / size
                if position.side == "long":
                    peak = float(max(position.entry_price, position.entry_price + mfe))
                    initial = position.entry_price - dist_t
                    trail_price = max(initial, peak - dist_t)
                else:
                    trough = float(
                        min(position.entry_price, position.entry_price - mfe)
                    )
                    initial = position.entry_price + dist_t
                    trail_price = min(initial, trough + dist_t)

                # Calculate potential trailing stop if current bar's favorable move
                # updates the peak/trough. This is needed to detect ambiguity correctly
                # because the current bar might both move the stop AND hit it.
                potential_trail_price = trail_price
                if position.side == "long":
                    # Check if current bar's high would update the peak
                    potential_peak = max(peak, float(current_bar["high"]))
                    potential_trail_price = max(initial, potential_peak - dist_t)
                else:
                    # Check if current bar's low would update the trough
                    potential_trough = min(trough, float(current_bar["low"]))
                    potential_trail_price = min(initial, potential_trough + dist_t)

                # Check for trailing stop ambiguity, zoom to 1-min if needed
                # Check BOTH trail_price (prior) AND potential_trail_price
                # (current bar) to detect intra-bar ambiguity
                ambiguous = False
                if trailing_updates_intrabar and trail_price is not None:
                    ambiguous = is_trailing_stop_ambiguous(current_bar, trail_price)
                    ambiguous = ambiguous or is_trailing_stop_ambiguous(
                        current_bar, potential_trail_price
                    )

                if (
                    trailing_updates_intrabar
                    and trail_price is not None
                    and ambiguous
                    and data_handler is not None
                ):
                    bar_timestamp = cast(pd.Timestamp, current_bar.name)
                    window_minutes = max(1, int(bar_minutes or 60))
                    # Cover the entire bar (open->close) using minute closes
                    start = bar_timestamp - pd.Timedelta(minutes=window_minutes - 1)
                    end = bar_timestamp
                    bars_1min = data_handler.get_data(
                        timeframe="1min", start=start, end=end
                    )

                    # Process 1-minute bars
                    # CRITICAL: Pass current peak/trough to preserve trailing stop state
                    current_peak_or_trough = peak if position.side == "long" else trough
                    result = process_1min_bars_for_trailing_stop(
                        bars_1min=bars_1min,
                        entry_price=position.entry_price,
                        side=position.side,
                        trailing_stop_offset=dist_t,
                        take_profit_price=tp_price,
                        tie_break_policy=self.exit_tie_break,
                        current_peak_or_trough=current_peak_or_trough,
                    )

                    # If exit occurred, return it
                    if result["exit_occurred"]:
                        return {
                            "exit_price": result["exit_price"],
                            "reason": result["exit_reason"],
                            "intrabar": True,
                        }
                    # If no exit in 1-minute data, return None (no exit)
                    # Don't fall through to OHLC checking - we've resolved the ambiguity
                    return None

        # Check for fixed stop + TP ambiguity and zoom to 1-minute if needed
        # This handles the case where BOTH fixed stop AND TP are in the bar's range
        if (
            sl_price is not None
            and tp_price is not None
            and trail_price is None  # Only for fixed stops (no trailing)
            and is_fixed_stops_ambiguous(current_bar, sl_price, tp_price)
        ):
            # Ambiguity detected - 1-minute data is REQUIRED
            if data_handler is None:
                bar_timestamp = cast(pd.Timestamp, current_bar.name)
                raise ValueError(
                    f"Fixed stop-loss and take-profit both in bar range at "
                    f"{bar_timestamp}, but no data_handler provided for 1-minute "
                    f"resolution. This ambiguity cannot be resolved without "
                    f"intrabar data. Either provide 1-minute data or adjust "
                    f"strategy to avoid this scenario."
                )

            # data_handler is available - zoom to 1-minute resolution
            bar_timestamp = cast(pd.Timestamp, current_bar.name)
            window_minutes = max(1, int(bar_minutes or 60))
            start = bar_timestamp - pd.Timedelta(minutes=window_minutes - 1)
            end = bar_timestamp
            bars_1min = data_handler.get_data(timeframe="1min", start=start, end=end)

            # Process 1-minute bars
            result = process_1min_bars_for_fixed_stops(
                bars_1min=bars_1min,
                side=position.side,
                stop_loss_level=sl_price,
                take_profit_level=tp_price,
                tie_break_policy=self.exit_tie_break,
            )

            # If exit occurred, return it
            if result["exit_occurred"]:
                return {
                    "exit_price": result["exit_price"],
                    "reason": result["exit_reason"],
                    "intrabar": True,
                }
            # If no exit in 1-minute data, return None
            return None

        # For longs, the effective stop is the highest of (sl, trail) below price;
        # for shorts, the lowest of (sl, trail) above price.
        if position.side == "long":
            eff_sl: float | None = None
            for v in (sl_price, trail_price):
                if v is None:
                    continue
                if eff_sl is None:
                    eff_sl = v
                else:
                    eff_sl = max(eff_sl, v)

            # Check if both SL and TP are hit on same bar
            sl_hit = eff_sl is not None and current_bar["low"] <= eff_sl
            tp_hit = tp_price is not None and current_bar["high"] >= tp_price

            # Apply exit_tie_break policy
            if self.exit_tie_break == "stop_then_tp":
                # Check stop-loss first (default behavior)
                if sl_hit:
                    return {"exit_price": eff_sl, "reason": "stop-loss"}
                if tp_hit:
                    return {"exit_price": tp_price, "reason": "take-profit"}
            else:  # "tp_then_stop"
                # Check take-profit first
                if tp_hit:
                    return {"exit_price": tp_price, "reason": "take-profit"}
                if sl_hit:
                    return {"exit_price": eff_sl, "reason": "stop-loss"}
        else:
            eff_sl = None
            for v in (sl_price, trail_price):
                if v is None:
                    continue
                if eff_sl is None:
                    eff_sl = v
                else:
                    eff_sl = min(eff_sl, v)

            # Check if both SL and TP are hit on same bar
            sl_hit = eff_sl is not None and current_bar["high"] >= eff_sl
            tp_hit = tp_price is not None and current_bar["low"] <= tp_price

            # Apply exit_tie_break policy
            if self.exit_tie_break == "stop_then_tp":
                # Check stop-loss first (default behavior)
                if sl_hit:
                    return {"exit_price": eff_sl, "reason": "stop-loss"}
                if tp_hit:
                    return {"exit_price": tp_price, "reason": "take-profit"}
            else:  # "tp_then_stop"
                # Check take-profit first
                if tp_hit:
                    return {"exit_price": tp_price, "reason": "take-profit"}
                if sl_hit:
                    return {"exit_price": eff_sl, "reason": "stop-loss"}

        return None

    def check_exits_intrabar(
        self,
        position: Position,
        current_bar: BarData,
        data_handler: Any = None,
        prior_bar: BarData | None = None,
        *,
        bar_minutes: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Check if position should exit based on intrabar price action.

        Returns action descriptor with exit price if stop/TP triggered,
        None otherwise. This is a wrapper around check_exits() that formats
        the result as an action descriptor for the execution model refactor.

        Args:
            position: Current open position
            current_bar: Bar with OHLC data
            data_handler: Optional DataHandler for 1-minute resolution zoom

        Returns:
            Action descriptor dict or None
        """
        # Call existing check_exits method
        exit_details = self.check_exits(
            position,
            current_bar,
            data_handler=data_handler,
            prior_bar=prior_bar,
            bar_minutes=bar_minutes,
        )

        if exit_details is None:
            return None

        # Format as action descriptor
        return {
            "action": "should_close",
            "reason": exit_details["reason"],
            "exit_price": exit_details["exit_price"],
        }
