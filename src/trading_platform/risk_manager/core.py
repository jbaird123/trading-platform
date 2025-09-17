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

        if position.side == "long":
            if stop_loss.get("value") and current_bar["low"] <= stop_loss["value"]:
                return {"exit_price": stop_loss["value"], "reason": "stop-loss"}
            if take_profit.get("value") and current_bar["high"] >= take_profit["value"]:
                return {"exit_price": take_profit["value"], "reason": "take-profit"}
        elif position.side == "short":
            if stop_loss.get("value") and current_bar["high"] >= stop_loss["value"]:
                return {"exit_price": stop_loss["value"], "reason": "stop-loss"}
            if take_profit.get("value") and current_bar["low"] <= take_profit["value"]:
                return {"exit_price": take_profit["value"], "reason": "take-profit"}

        return None
