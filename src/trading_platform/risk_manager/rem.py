from __future__ import annotations

from pathlib import Path
from typing import Any, TextIO

import yaml  # type: ignore


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
        self, position_side: str, entry_price: float, current_price: float, atr: float
    ) -> tuple[float | None, float | None]:
        """Checks if any exit conditions are met for a position.

        Returns:
            A tuple of (stop_loss_price, take_profit_price).
        """
        stop_loss = self._config.get("stop_loss")
        take_profit = self._config.get("take_profit")

        sl_price = None
        tp_price = None

        if stop_loss:
            sl_price = self._calculate_exit_price(
                position_side, entry_price, stop_loss, atr, is_stop=True
            )

        if take_profit:
            tp_price = self._calculate_exit_price(
                position_side, entry_price, take_profit, atr, is_stop=False
            )

        return sl_price, tp_price

    def _calculate_exit_price(
        self,
        side: str,
        entry: float,
        rule: dict,
        atr: float,
        is_stop: bool,
    ) -> float | None:
        """Calculates a specific exit price based on a rule."""
        rule_type = rule.get("type")
        if not rule_type:
            return None

        side_multiplier = -1 if side == "long" else 1

        if rule_type == "static":
            offset = float(rule.get("price_offset", 0.0))
            # Note: A proper pip calculation requires instrument context.
            # This is a simplified placeholder.
            if "pips" in rule:
                offset = float(rule["pips"]) * 0.0001  # Placeholder for EUR/USD

        elif rule_type == "dynamic":
            offset = float(rule["atr_multiplier"]) * atr
        else:
            raise ValueError(f"Unknown REM rule type: {rule_type}")

        # For a stop, the offset is against the entry price.
        # For a take-profit, the offset is with the entry price.
        if is_stop:
            return entry + (offset * side_multiplier)
        else:
            return entry - (offset * side_multiplier)
