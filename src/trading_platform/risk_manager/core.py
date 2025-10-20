from __future__ import annotations

from typing import Any, cast

import pandas as pd

from trading_platform.core.signal import Signal
from trading_platform.portfolio.position import Position
from trading_platform.risk_manager.exit_utils import (
    is_fixed_stops_ambiguous,
    is_trailing_stop_ambiguous,
)
from trading_platform.risk_manager.models import REMConfig
from trading_platform.risk_manager.trailing_stop_utils import (
    process_1min_bars_for_fixed_stops,
    process_1min_bars_for_trailing_stop,
)


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
            self.config = {}
        elif isinstance(config, REMConfig):
            self.config = config.model_dump()
        elif isinstance(config, dict):
            # Legacy dict path: check if it uses old format or advanced features
            # Old format: {"stop_loss": {"pips": 50}} (no "type" field)
            # New format: {"stop_loss": {"type": "fixed_pips", "pips": 50}}
            # Advanced features: trailing_stop, reference_price
            has_legacy_format = self._is_legacy_format(config)
            has_advanced_features = (
                "trailing_stop" in config
                or self._has_reference_price(config)
            )
            if not has_legacy_format and not has_advanced_features and config:
                # New format - validate through Pydantic
                validated = REMConfig(**config)
                self.config = validated.model_dump()
            else:
                # Legacy format or advanced features - bypass validation
                self.config = config
        else:
            raise TypeError(
                f"config must be REMConfig, dict, or None, got {type(config)}"
            )

        self.instrument = instrument or {}
        self.exit_tie_break = exit_tie_break

    @staticmethod
    def _is_legacy_format(config: dict) -> bool:
        """Check if config uses legacy format (no 'type' discriminator).

        Legacy: {"stop_loss": {"pips": 50}} or {"atr_multiple": 2.0}
        New: {"stop_loss": {"type": "fixed_pips", "pips": 50}}
        Also treats None values as legacy (for edge case testing).
        """
        for key in ["stop_loss", "take_profit"]:
            rules = config.get(key)
            if rules is None:
                # None values are legacy edge cases
                return True
            if isinstance(rules, list):
                for rule in rules:
                    if isinstance(rule, dict) and "type" not in rule:
                        # Legacy format if rule has no 'type' field
                        return True
            elif isinstance(rules, dict) and "type" not in rules:
                # Legacy format if rule has no 'type' field
                return True
        return False

    @staticmethod
    def _has_reference_price(config: dict) -> bool:
        """Check if config uses reference_price feature."""
        for key in ["stop_loss", "take_profit"]:
            rules = config.get(key)
            if isinstance(rules, list):
                for rule in rules:
                    if isinstance(rule, dict) and rule.get("type") == "reference_price":
                        return True
            elif isinstance(rules, dict) and rules.get("type") == "reference_price":
                return True
        return False

    def check_exits(
        self,
        position: Position,
        current_bar: pd.Series,
        signal: Any = None,
        data_handler: Any = None,
    ) -> dict[str, Any] | None:
        """
        Checks if any exit conditions are met for the given position.

        Args:
            position: The current position to check exits for
            current_bar: The current market bar data
            signal: Optional Signal object with context data
            data_handler: Optional DataHandler for 1-minute resolution zoom

        Returns:
            A dictionary with the exit details if an exit is triggered,
            otherwise None.
        """
        stop_loss = self.config.get("stop_loss", {}) or {}
        take_profit = self.config.get("take_profit", {}) or {}
        trailing = self.config.get("trailing_stop", {}) or {}

        # Extract signal context if available
        # Prefer position's entry context (persisted), fallback to current signal
        signal_context = {}
        if position.context_at_entry:
            signal_context = position.context_at_entry
        elif signal is not None and isinstance(signal, Signal):
            signal_context = signal.context or {}

        def _pip_size() -> float:
            """Get pip size from instrument. Fail loudly if missing."""
            pip_location = self.instrument.get("pip_location")
            if pip_location is None:
                raise ValueError(
                    "pip_location missing from instrument definition. "
                    "Cannot calculate pip-based offsets for non-Forex instruments."
                )
            return float(pip_location)

        def _atr_value(length: int | None) -> float | None:
            # Try to get ATR from current_bar if it exists as a computed feature
            atr_col = f"atr_{length}" if length else "atr"
            if atr_col in current_bar.index:
                return float(current_bar[atr_col])
            # Fallback: check for generic 'atr' column
            if "atr" in current_bar.index:
                return float(current_bar["atr"])
            return None

        def _distance(rule: dict) -> float | None:
            if "price_offset" in rule:
                return float(rule["price_offset"])
            if "pips" in rule:
                return float(rule["pips"]) * _pip_size()
            if "atr_multiple" in rule:
                length = int(rule.get("atr_length", 14))
                atr = _atr_value(length)
                return float(rule["atr_multiple"]) * float(atr) if atr else None
            return None

        def _get_context_value(reference_point: str) -> float | None:
            """Extract value from signal context using dot notation."""
            if not reference_point.startswith("context."):
                return None
            key = reference_point.replace("context.", "")
            # Support nested strategy_features structure
            if "strategy_features" in signal_context:
                val = signal_context["strategy_features"].get(key)
                return float(val) if val is not None else None
            # Fall back to flat structure for backward compatibility
            val = signal_context.get(key)
            return float(val) if val is not None else None

        def _level_price(
            side: str, entry: float, rule: dict, is_stop: bool
        ) -> float | None:
            # Handle reference_price type (contextual rules)
            if rule.get("type") == "reference_price":
                ref_point = rule.get("reference_point", "")
                base_price = _get_context_value(ref_point)
                if base_price is None:
                    return None

                # Get offset from the rule
                offset_config = rule.get("offset", {})
                offset = _distance(offset_config)
                if offset is None:
                    return float(base_price)

                # Apply offset (negative offset for stop below, positive for TP above)
                return float(base_price) + offset

            # Legacy absolute_price rules
            if "absolute_price" in rule:
                return float(rule["absolute_price"])

            # Legacy distance-based rules
            dist = _distance(rule)
            if dist is None:
                return None
            if side == "long":
                return entry - dist if is_stop else entry + dist
            return entry + dist if is_stop else entry - dist

        def _process_rule_list(rules: Any, is_stop: bool) -> float | None:
            """Process a rule or list of rules, return first valid price."""
            if isinstance(rules, list):
                for rule in rules:
                    price = _level_price(
                        position.side, position.entry_price, rule, is_stop
                    )
                    if price is not None:
                        return price
                return None
            return _level_price(position.side, position.entry_price, rules, is_stop)

        sl_price = _process_rule_list(stop_loss, True)
        tp_price = _process_rule_list(take_profit, False)

        # Trailing stop based on MFE; derived from Position.mfe_currency and size
        trail_price: float | None = None
        if trailing:
            dist_t = _distance(trailing)
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
                if (
                    trail_price is not None
                    and data_handler is not None
                    and (
                        is_trailing_stop_ambiguous(current_bar, trail_price)
                        or is_trailing_stop_ambiguous(
                            current_bar, potential_trail_price
                        )
                    )
                ):
                    # Zoom to 1-minute resolution to resolve ambiguity
                    bar_timestamp = cast(pd.Timestamp, current_bar.name)
                    hour_start = bar_timestamp.floor("h")
                    hour_end = (
                        hour_start + pd.Timedelta(hours=1) - pd.Timedelta(1, unit="ns")
                    )
                    bars_1min = data_handler.get_data(
                        timeframe="1min", start=hour_start, end=hour_end
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
            # Zoom to 1-minute resolution
            bar_timestamp = cast(pd.Timestamp, current_bar.name)
            hour_start = bar_timestamp.floor("h")
            hour_end = hour_start + pd.Timedelta(hours=1) - pd.Timedelta(1, unit="ns")
            bars_1min = data_handler.get_data(
                timeframe="1min", start=hour_start, end=hour_end
            )

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
        self, position: Position, current_bar: pd.Series, data_handler: Any = None
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
            position, current_bar, data_handler=data_handler
        )

        if exit_details is None:
            return None

        # Format as action descriptor
        return {
            "action": "should_close",
            "reason": exit_details["reason"],
            "exit_price": exit_details["exit_price"],
        }
