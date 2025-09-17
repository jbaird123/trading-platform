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
        stop_loss = self.config.get("stop_loss", {})
        take_profit = self.config.get("take_profit", {})

        sl_val = stop_loss.get("value")
        tp_val = take_profit.get("value")
        sl_type = stop_loss.get("type", "price")
        tp_type = take_profit.get("type", "price")

        if position.side == "long":
            sl_price = None
            tp_price = None
            if sl_val is not None:
                sl_price = (
                    position.entry_price - float(sl_val)
                    if sl_type in ("offset",)
                    else float(sl_val)
                )
            if tp_val is not None:
                tp_price = (
                    position.entry_price + float(tp_val)
                    if tp_type in ("offset",)
                    else float(tp_val)
                )
            if sl_price is not None and current_bar["low"] <= sl_price:
                return {"exit_price": sl_price, "reason": "stop-loss"}
            if tp_price is not None and current_bar["high"] >= tp_price:
                return {"exit_price": tp_price, "reason": "take-profit"}
        elif position.side == "short":
            sl_price = None
            tp_price = None
            if sl_val is not None:
                sl_price = (
                    position.entry_price + float(sl_val)
                    if sl_type in ("offset",)
                    else float(sl_val)
                )
            if tp_val is not None:
                tp_price = (
                    position.entry_price - float(tp_val)
                    if tp_type in ("offset",)
                    else float(tp_val)
                )
            if sl_price is not None and current_bar["high"] >= sl_price:
                return {"exit_price": sl_price, "reason": "stop-loss"}
            if tp_price is not None and current_bar["low"] <= tp_price:
                return {"exit_price": tp_price, "reason": "take-profit"}

        return None
