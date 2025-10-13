from __future__ import annotations

from pathlib import Path
from typing import Any, TextIO

import pandas as pd
import yaml

from trading_platform.portfolio.position import Position


class RiskExitManager:
    """Manages position exit logic based on a defined configuration."""

    def __init__(self, config_path: str | Path | TextIO):
        """Initializes the RiskExitManager from a config file path or stream."""
        self._config: dict[str, Any]
        if isinstance(config_path, (str, Path)):
            with open(config_path) as f:
                self._config = yaml.safe_load(f)
        else:  # Assumes a file-like object
            self._config = yaml.safe_load(config_path)

    @property
    def config(self) -> dict[str, Any]:
        """Returns the loaded REM configuration."""
        return self._config

    def check_exits(
        self,
        position_side: str,
        entry_price: float,
        *,
        price: float | None = None,
        atr: float | None = None,
    ) -> tuple[float | None, float | None]:
        """Calculates target stop/tp prices from config.

        Returns a tuple (stop_loss_price, take_profit_price).
        """
        sl = self._level_price(
            position_side, entry_price, self._config.get("stop_loss"), atr
        )
        tp = self._level_price(
            position_side,
            entry_price,
            self._config.get("take_profit"),
            atr,
            is_stop=False,
        )
        return sl, tp

    def _pip_size(self) -> float:
        # Simplified heuristic; real implementation should use instrument meta.
        return 0.0001

    def _distance(self, rule: dict | None, atr: float | None) -> float | None:
        if not isinstance(rule, dict):
            return None
        if "price_offset" in rule:
            return float(rule["price_offset"])
        if "pips" in rule:
            return float(rule["pips"]) * self._pip_size()
        if "atr_multiple" in rule and atr is not None:
            return float(rule["atr_multiple"]) * float(atr)
        return None

    def _level_price(
        self,
        side: str,
        entry: float,
        rule: dict | None,
        atr: float | None,
        is_stop: bool = True,
    ) -> float | None:
        if not isinstance(rule, dict):
            return None
        if "absolute_price" in rule:
            return float(rule["absolute_price"])
        dist = self._distance(rule, atr)
        if dist is None:
            return None
        if side == "long":
            return entry - dist if is_stop else entry + dist
        return entry + dist if is_stop else entry - dist

    def check_exits_intrabar(
        self, position: Position, current_bar: pd.Series
    ) -> dict[str, Any] | None:
        """
        Check if position should exit based on intrabar price action.

        Returns action descriptor with exit price if stop/TP triggered,
        None otherwise. This allows Backtester to control execution timing.

        Args:
            position: Current open position
            current_bar: Bar with OHLC data

        Returns:
            Action descriptor dict or None
        """
        # Get stop-loss and take-profit prices
        stop_loss_price, take_profit_price = self.check_exits(
            position.side, position.entry_price
        )

        # Check stop-loss trigger
        if stop_loss_price is not None:
            if position.side == "long":
                # Long: stop triggers if low <= stop price
                if current_bar["low"] <= stop_loss_price:
                    return {
                        "action": "should_close",
                        "reason": "stop_loss",
                        "exit_price": stop_loss_price,
                    }
            else:  # short
                # Short: stop triggers if high >= stop price
                if current_bar["high"] >= stop_loss_price:
                    return {
                        "action": "should_close",
                        "reason": "stop_loss",
                        "exit_price": stop_loss_price,
                    }

        # Check take-profit trigger
        if take_profit_price is not None:
            if position.side == "long":
                # Long: TP triggers if high >= TP price
                if current_bar["high"] >= take_profit_price:
                    return {
                        "action": "should_close",
                        "reason": "take_profit",
                        "exit_price": take_profit_price,
                    }
            else:  # short
                # Short: TP triggers if low <= TP price
                if current_bar["low"] <= take_profit_price:
                    return {
                        "action": "should_close",
                        "reason": "take_profit",
                        "exit_price": take_profit_price,
                    }

        # Neither stop nor TP triggered
        return None
