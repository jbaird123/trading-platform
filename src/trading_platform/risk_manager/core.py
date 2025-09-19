from __future__ import annotations

from typing import Any

import pandas as pd

from trading_platform.portfolio.position import Position


class RiskExitManager:
    """
    Manages risk and exit conditions for open positions.

    This class is responsible for loading and interpreting a risk configuration
    and determining if a position should be closed based on stop-loss or
    take-profit rules.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initializes the RiskExitManager with a given risk configuration.

        Args:
            config: A dictionary representing the REM configuration, conforming
                    to the schema defined in the project requirements.
        """
        self.config = config

    def check_exits(
        self, position: Position, current_bar: pd.Series
    ) -> dict[str, Any] | None:
        """
        Checks if any exit conditions are met for the given position.

        Returns:
            A dictionary with the exit details if an exit is triggered,
            otherwise None.
        """
        stop_loss = self.config.get("stop_loss", {}) or {}
        take_profit = self.config.get("take_profit", {}) or {}
        trailing = self.config.get("trailing_stop", {}) or {}

        def _pip_size(sym: str) -> float:
            return 0.01 if "JPY" in sym else 0.0001

        def _atr_value(length: int | None) -> float | None:
            # ATR not present in current_bar; placeholder for integration.
            return None

        def _distance(rule: dict) -> float | None:
            if "price_offset" in rule:
                return float(rule["price_offset"])
            if "pips" in rule:
                return float(rule["pips"]) * _pip_size(position.symbol)
            if "atr_multiple" in rule:
                length = int(rule.get("atr_length", 14))
                atr = _atr_value(length)
                return float(rule["atr_multiple"]) * float(atr) if atr else None
            return None

        def _level_price(
            side: str, entry: float, rule: dict, is_stop: bool
        ) -> float | None:
            if "absolute_price" in rule:
                return float(rule["absolute_price"])
            dist = _distance(rule)
            if dist is None:
                return None
            if side == "long":
                return entry - dist if is_stop else entry + dist
            return entry + dist if is_stop else entry - dist

        sl_price = _level_price(position.side, position.entry_price, stop_loss, True)
        tp_price = _level_price(position.side, position.entry_price, take_profit, False)

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
            if eff_sl is not None and current_bar["low"] <= eff_sl:
                return {"exit_price": eff_sl, "reason": "stop-loss"}
            if tp_price is not None and current_bar["high"] >= tp_price:
                return {"exit_price": tp_price, "reason": "take-profit"}
        else:
            eff_sl = None
            for v in (sl_price, trail_price):
                if v is None:
                    continue
                if eff_sl is None:
                    eff_sl = v
                else:
                    eff_sl = min(eff_sl, v)
            if eff_sl is not None and current_bar["high"] >= eff_sl:
                return {"exit_price": eff_sl, "reason": "stop-loss"}
            if tp_price is not None and current_bar["low"] <= tp_price:
                return {"exit_price": tp_price, "reason": "take-profit"}

        return None
