"""REM Indicator Registry.

This module defines the registry of indicators that are permitted for use in
Risk and Exit Manager (REM) stop-loss and take-profit calculations.

Only indicators explicitly registered here may be specified in REM configs.
This prevents silent failures from typos or unimplemented indicators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd


@dataclass
class REMIndicatorSpec:
    """Specification for an indicator usable in REM.

    Attributes:
        name: Unique identifier (e.g., "atr", "bollinger")
        description: Human-readable description
        required_params: Dict mapping param names to expected types
        optional_params: Dict mapping names to (type, default) tuples
        stop_calculator: Function that calculates stop price
    """

    name: str
    description: str
    required_params: dict[str, type]
    optional_params: dict[str, tuple[type, Any]]  # (type, default)
    stop_calculator: Callable[[float, str, pd.Series, dict], float]


def _calculate_atr_stop(
    entry_price: float,
    side: str,
    current_bar: pd.Series,
    params: dict,
) -> float:
    """Calculate stop price based on ATR indicator.

    For long positions: stop = entry_price - (ATR * multiplier)
    For short positions: stop = entry_price + (ATR * multiplier)

    Args:
        entry_price: The entry price of the position
        side: Position side, either "long" or "short"
        current_bar: Pandas Series containing current bar data with ATR values
        params: Dictionary containing:
            - multiplier (float, required): Multiplier applied to ATR
            - length (int, optional): ATR period, defaults to 14

    Returns:
        Stop price level

    Raises:
        KeyError: If ATR indicator not found in current_bar
        ValueError: If multiplier is missing or invalid
    """
    length = params.get("length", 14)
    multiplier = params["multiplier"]

    # Look for ATR value in current bar
    # Try both atr_{length} and generic "atr" column names
    atr_col = f"atr_{length}"
    if atr_col in current_bar:
        atr_value = current_bar[atr_col]
    elif "atr" in current_bar:
        atr_value = current_bar["atr"]
    else:
        raise KeyError(
            f"ATR indicator not found in bar data. Expected column '{atr_col}' or 'atr'"
        )

    distance = float(atr_value) * float(multiplier)

    if side == "long":
        return entry_price - distance
    elif side == "short":
        return entry_price + distance
    else:
        raise ValueError(f"Invalid side '{side}', must be 'long' or 'short'")


# Registry of indicators permitted for REM stop/TP calculations
REM_INDICATORS_REGISTRY: dict[str, REMIndicatorSpec] = {
    "atr": REMIndicatorSpec(
        name="atr",
        description="Average True Range - single value volatility measure",
        required_params={"multiplier": float},
        optional_params={"length": (int, 14)},
        stop_calculator=_calculate_atr_stop,
    ),
}


__all__ = ["REM_INDICATORS_REGISTRY", "REMIndicatorSpec"]
