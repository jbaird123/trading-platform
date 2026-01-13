"""Position sizing strategies for the trading platform.

This module implements various position sizing algorithms including:
- FixedSizePositionSizer: Returns a constant position size (current behavior)
- FixedRatioPositionSizer: Ryan Jones's Fixed Ratio method from "The Trading Game"

The Fixed Ratio method uses the formula:
    N = 0.5 × [(1 + 8 × P / delta)^0.5 + 1]

Where:
    N = number of contracts to trade
    P = accumulated profit since starting
    delta = profit required to add one contract

The actual position size in units is: N × contract_size
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PositionSizeResult:
    """Result of a position sizing calculation."""

    units: float  # Actual position size in broker units
    contracts: float  # Number of "contracts" (for Fixed Ratio tracking)
    method: str  # Name of the sizing method used


class PositionSizer(ABC):
    """Abstract base class for position sizing strategies."""

    @abstractmethod
    def calculate_size(
        self,
        current_equity: float,
        initial_equity: float,
        contract_size: float,
    ) -> PositionSizeResult:
        """Calculate the position size for a new trade.

        Args:
            current_equity: Current account equity
            initial_equity: Starting account equity
            contract_size: Units per "contract" from instrument definition

        Returns:
            PositionSizeResult with units, contracts, and method name
        """
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize the position sizer configuration for briefs."""
        pass

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> PositionSizer:
        """Factory method to create a PositionSizer from configuration.

        Args:
            config: Dictionary with 'method' key and method-specific parameters

        Returns:
            Appropriate PositionSizer subclass instance

        Raises:
            ValueError: If method is unknown or parameters are invalid
        """
        method = config.get("method", "fixed")

        if method == "fixed":
            return FixedSizePositionSizer(
                size=config.get("size", 1.0),
            )
        elif method == "fixed_ratio":
            delta = config.get("delta")
            if delta is None:
                raise ValueError("fixed_ratio method requires 'delta' parameter")
            return FixedRatioPositionSizer(
                delta=delta,
                initial_contracts=config.get("initial_contracts", 1),
                delta_fraction=config.get("delta_fraction"),
            )
        else:
            raise ValueError(f"Unknown position sizing method: {method}")


class FixedSizePositionSizer(PositionSizer):
    """Fixed position size - always returns the same number of contracts.

    This is the current default behavior of the platform.
    """

    def __init__(self, size: float = 1.0) -> None:
        """Initialize with a fixed contract size.

        Args:
            size: Number of contracts to trade (default: 1.0)
        """
        if size <= 0:
            raise ValueError("Position size must be positive")
        self._size = float(size)

    def calculate_size(
        self,
        current_equity: float,
        initial_equity: float,
        contract_size: float,
    ) -> PositionSizeResult:
        """Return fixed position size regardless of equity.

        Args:
            current_equity: Current account equity (ignored)
            initial_equity: Starting account equity (ignored)
            contract_size: Units per contract from instrument definition

        Returns:
            PositionSizeResult with fixed number of contracts
        """
        del current_equity, initial_equity  # Not used in fixed sizing
        return PositionSizeResult(
            units=self._size * contract_size,
            contracts=self._size,
            method="fixed",
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration."""
        return {
            "method": "fixed",
            "size": self._size,
        }


class FixedRatioPositionSizer(PositionSizer):
    """Ryan Jones's Fixed Ratio position sizing from "The Trading Game".

    The Fixed Ratio method calculates the number of contracts based on
    accumulated profit using the formula:

        N = 0.5 × [(1 + 8 × P / delta)^0.5 + 1]

    Where:
        N = number of contracts to trade
        P = accumulated profit (current_equity - initial_equity)
        delta = profit required to add one contract

    Key properties:
    - Faster growth for small accounts (aggressive scaling up)
    - Built-in protection for large accounts (slower scaling)
    - Symmetric scale-down during drawdowns (using delta_fraction)

    Args:
        delta: Profit required to add one contract (must be positive)
        initial_contracts: Starting number of contracts (default: 1)
        delta_fraction: Fraction of delta for scale-down during drawdowns.
                       If None, uses same delta for both directions.
                       Lower values = faster scale down during losses.
    """

    def __init__(
        self,
        delta: float,
        initial_contracts: int = 1,
        delta_fraction: float | None = None,
    ) -> None:
        if delta <= 0:
            raise ValueError("Delta must be positive")
        if initial_contracts < 1:
            raise ValueError("initial_contracts must be at least 1")
        if delta_fraction is not None and (delta_fraction <= 0 or delta_fraction > 1):
            raise ValueError("delta_fraction must be between 0 (exclusive) and 1")

        self._delta = float(delta)
        self._initial_contracts = int(initial_contracts)
        self._delta_fraction = delta_fraction
        # Track high water mark for drawdown-based scaling
        self._high_water_contracts: float = float(initial_contracts)

    def calculate_size(
        self,
        current_equity: float,
        initial_equity: float,
        contract_size: float,
    ) -> PositionSizeResult:
        """Calculate position size using Fixed Ratio formula.

        Args:
            current_equity: Current account equity
            initial_equity: Starting account equity
            contract_size: Units per contract from instrument definition

        Returns:
            PositionSizeResult with calculated contracts and units
        """
        profit = current_equity - initial_equity

        if profit >= 0:
            # Scale up using standard Fixed Ratio formula
            contracts = self._calculate_contracts_for_profit(profit, self._delta)
            # Update high water mark
            self._high_water_contracts = max(self._high_water_contracts, contracts)
        else:
            # During drawdown: use delta_fraction for faster scale-down
            effective_delta = self._delta
            if self._delta_fraction is not None:
                effective_delta = self._delta * self._delta_fraction

            # Calculate what contracts would be at current (negative) profit level
            # Using the inverse: find N where profit = delta * N * (N-1) / 2
            # For negative profits, we scale down from high water mark
            contracts = self._calculate_contracts_for_drawdown(
                profit, effective_delta, self._high_water_contracts
            )

        # Ensure minimum of initial_contracts
        contracts = max(float(self._initial_contracts), contracts)

        return PositionSizeResult(
            units=contracts * contract_size,
            contracts=contracts,
            method="fixed_ratio",
        )

    def _calculate_contracts_for_profit(self, profit: float, delta: float) -> float:
        """Calculate number of contracts for given profit level.

        Uses the Fixed Ratio formula:
            N = 0.5 × [(1 + 8 × P / delta)^0.5 + 1]

        Args:
            profit: Accumulated profit
            delta: Profit required per contract

        Returns:
            Number of contracts (can be fractional)
        """
        if profit <= 0:
            return float(self._initial_contracts)

        # Fixed Ratio formula
        discriminant = 1 + (8 * profit / delta)
        n = 0.5 * (math.sqrt(discriminant) + 1)

        return n

    def _calculate_contracts_for_drawdown(
        self, profit: float, effective_delta: float, high_water: float
    ) -> float:
        """Calculate contracts during a drawdown period.

        When in drawdown (negative profit), we need to scale down from the
        high water mark. This uses the same formula but inverted.

        Args:
            profit: Current profit (negative during drawdown)
            effective_delta: Delta to use (may be reduced by delta_fraction)
            high_water: Highest contract count achieved

        Returns:
            Number of contracts for current drawdown level
        """
        # profit is negative here
        # We calculate what profit level would give us certain contract counts
        # and work backwards

        # The profit required to reach N contracts is: P = delta * N * (N-1) / 2
        # So at high water, the profit was: P_hw = delta * hw * (hw-1) / 2
        # Current profit relative to high water: P_current = P_hw + profit

        # Calculate the profit at high water mark (using original delta)
        profit_at_high_water = self._delta * high_water * (high_water - 1) / 2

        # Current effective profit level
        effective_profit = profit_at_high_water + profit

        if effective_profit <= 0:
            return float(self._initial_contracts)

        # Use effective_delta for the scale-down calculation
        discriminant = 1 + (8 * effective_profit / effective_delta)
        n = 0.5 * (math.sqrt(discriminant) + 1)

        return max(float(self._initial_contracts), n)

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration."""
        result: dict[str, Any] = {
            "method": "fixed_ratio",
            "delta": self._delta,
            "initial_contracts": self._initial_contracts,
        }
        if self._delta_fraction is not None:
            result["delta_fraction"] = self._delta_fraction
        return result

    def reset_high_water_mark(self) -> None:
        """Reset the high water mark to initial contracts.

        Call this when starting a new backtest run or resetting state.
        """
        self._high_water_contracts = float(self._initial_contracts)
