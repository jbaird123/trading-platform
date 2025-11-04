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
    optional_params: dict[str, tuple[type, Any]]
    stop_calculator: Callable[[float, str, pd.Series, dict], float]
    requires_prior_bar: bool = False
    requires_intrabar_zoom: bool = False


def _calculate_atr_stop(
    entry_price: float,
    side: str,
    current_bar: pd.Series,
    params: dict,
) -> float:
    """Calculate stop price based on ATR indicator.

    This implements a DYNAMIC ATR stop that recalculates each bar based on the
    bar's close price and ATR value. This matches live trading behavior where:
    - When bar N closes, calculate: stop = close(N) +/- ATR(N) * multiplier
    - That stop level is active for bar N+1
    - When bar N+1 closes, recalculate using bar N+1's data

    For long positions: stop = close - (ATR * multiplier)
    For short positions: stop = close + (ATR * multiplier)

    Args:
        entry_price: The entry price of the position (not used for dynamic stops)
        side: Position side, either "long" or "short"
        current_bar: Pandas Series containing the bar data used for calculation.
                    In practice, this should be the PRIOR bar (the bar that just
                    closed), as stops are set when a bar closes based on that
                    bar's close price and ATR.
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

    # Use the bar's close price as the base for the stop calculation
    # This creates a dynamic stop that moves with price
    close_price = float(current_bar["close"])
    distance = float(atr_value) * float(multiplier)

    if side == "long":
        return close_price - distance
    elif side == "short":
        return close_price + distance
    else:
        raise ValueError(f"Invalid side '{side}', must be 'long' or 'short'")


def _calculate_chandelier_stop(
    entry_price: float,
    side: str,
    current_bar: pd.Series | dict[str, Any],
    params: dict,
) -> float:
    """Calculate Chandelier Stop price.

    The Chandelier Stop is a volatility-based trailing stop created by
    Chuck LeBeau. It hangs from the highest high (long) or lowest low
    (short) by a multiple of ATR, like a chandelier hangs from a ceiling.

    For long positions: stop = HHV(high, period) - (ATR * multiplier)
    For short positions: stop = LLV(low, period) + (ATR * multiplier)

    This creates a trailing stop that:
    - Moves only in favorable direction (up for longs, down for shorts)
    - Adapts to volatility via ATR
    - Provides wider stops in volatile markets, tighter in calm markets

    Args:
        entry_price: Entry price (not used - chandelier uses HHV/LLV)
        side: Position side, either "long" or "short"
        current_bar: Bar containing HHV, LLV, and ATR columns
        params: Dictionary containing:
            - multiplier (float, optional): ATR multiplier, default 3.0
            - length (int, optional): HHV/LLV lookback period, default 22
            - atr_length (int, optional): ATR period, default 14

    Returns:
        Stop price level

    Raises:
        KeyError: If required indicator columns not found in current_bar
        ValueError: If side is invalid

    Example:
        Long trade with 22-period chandelier, 3.0 ATR multiplier:
        - HHV(22) = 1.3450
        - ATR(14) = 0.0015
        - Stop = 1.3450 - (3.0 * 0.0015) = 1.3405

        As price rises and makes new highs, the stop trails upward.
        If volatility increases, the stop gives more room.
    """
    multiplier = params.get("multiplier", 3.0)
    length = params.get("length", 22)
    atr_length = params.get("atr_length", 14)

    if side not in {"long", "short"}:
        raise ValueError(f"Invalid side '{side}', must be 'long' or 'short'")

    # Get ATR value - try specific length column first, then generic
    atr_col = f"atr_{atr_length}"
    if isinstance(current_bar, dict):
        atr_value = current_bar.get(atr_col)
        if atr_value is None:
            atr_value = current_bar.get("atr")
    else:
        if atr_col in current_bar:
            atr_value = current_bar[atr_col]
        elif "atr" in current_bar:
            atr_value = current_bar["atr"]
        else:
            atr_value = None
    if atr_value is None:
        raise KeyError(
            f"ATR indicator not found. Expected column '{atr_col}' or "
            "'atr'. Add ATR feature to strategy with matching length."
        )

    if side == "long":
        # For longs: hang from highest high
        # Try multiple column naming conventions
        hhv_candidates = [
            f"hhv_{length}",
            f"HHV_{length}",
            "hhv",
            "HHV",
            f"highest_high_{length}",
        ]
        hhv_value = None
        for candidate in hhv_candidates:
            if isinstance(current_bar, dict):
                if candidate in current_bar:
                    hhv_value = current_bar[candidate]
                    break
            else:
                if candidate in current_bar:
                    hhv_value = current_bar[candidate]
                    break

        if hhv_value is None:
            tried = ", ".join(hhv_candidates)
            raise KeyError(
                f"HHV indicator not found. Tried columns: {tried}. "
                f"Add HHV feature to strategy: "
                f"{{name: hhv_{length}, type: HHV, "
                f"params: {{length: {length}}}, source: high}}"
            )

        highest_high = float(hhv_value)
        distance = float(atr_value) * float(multiplier)
        return highest_high - distance

    else:  # short
        # For shorts: hang from lowest low
        llv_candidates = [
            f"llv_{length}",
            f"LLV_{length}",
            "llv",
            "LLV",
            f"lowest_low_{length}",
        ]
        llv_value = None
        for candidate in llv_candidates:
            if isinstance(current_bar, dict):
                if candidate in current_bar:
                    llv_value = current_bar[candidate]
                    break
            else:
                if candidate in current_bar:
                    llv_value = current_bar[candidate]
                    break

        if llv_value is None:
            tried = ", ".join(llv_candidates)
            raise KeyError(
                f"LLV indicator not found. Tried columns: {tried}. "
                f"Add LLV feature to strategy: "
                f"{{name: llv_{length}, type: LLV, "
                f"params: {{length: {length}}}, source: low}}"
            )

        lowest_low = float(llv_value)
        distance = float(atr_value) * float(multiplier)
        return lowest_low + distance


def _calculate_bollinger_stop(
    entry_price: float,
    side: str,
    current_bar: pd.Series,
    params: dict,
) -> float:
    """Calculate stop price using Bollinger Band levels.

    This calculator expects pre-computed Bollinger Band columns to be present in
    ``current_bar``. Column discovery is tolerant of different naming schemes
    produced by the strategy pipeline (``bb_lower``, ``bollinger_lower``, etc.).

    Args:
        entry_price: The entry price (unused; included for parity with ATR).
        side: Position side, either ``"long"`` or ``"short"``.
        current_bar: Prior bar used to derive the band-based stop.
        params: Dictionary containing:
            - band (str, optional): ``"auto"`` (default), ``"lower"``,
              ``"upper"``, or ``"middle"``.
            - length (int, optional): Included for traceability. Defaults to 20.
            - std (float, optional): Standard-deviation multiplier. Defaults 2.0.
            - offset (float, optional): Canonical distance to widen the band.
            - column_prefix (str, optional): Column prefix. Defaults to ``"bb"``.

    Returns:
        Stop price level derived from the requested band plus optional offset.

    Raises:
        KeyError: If no matching Bollinger column is found.
        ValueError: If ``side`` or ``band`` is invalid.
    """
    band_raw = params.get("band", "auto")
    band = str(band_raw).lower()

    if side not in {"long", "short"}:
        raise ValueError(f"Invalid side '{side}', must be 'long' or 'short'")

    if band == "auto":
        band = "lower" if side == "long" else "upper"

    if band not in {"upper", "lower", "middle"}:
        raise ValueError(
            f"Invalid Bollinger band '{band_raw}'. "
            "Expected 'upper', 'lower', 'middle', or 'auto'."
        )

    prefix = str(params.get("column_prefix", "bb")).strip()
    length = params.get("length")
    std = params.get("std")

    candidates: list[str] = []

    def _extend(names: list[str]) -> None:
        for name in names:
            if name and name not in candidates:
                candidates.append(name)

    base_names = [
        f"{prefix}_{band}",
        f"{prefix}{band}",
        f"bollinger_{band}",
    ]
    _extend(base_names)

    if length is not None:
        length_suffix = str(length)
        _extend([f"{prefix}_{band}_{length_suffix}"])
        _extend([f"bollinger_{band}_{length_suffix}"])

    if length is not None and std is not None:
        std_suffix = f"{float(std):g}".replace(".", "_")
        _extend([f"{prefix}_{band}_{length}_{std_suffix}"])

    for candidate in candidates:
        if candidate in current_bar:
            band_value = float(current_bar[candidate])
            break
    else:
        searched = ", ".join(candidates)
        raise KeyError(
            "Bollinger indicator not found in bar data. " f"Tried columns: {searched}"
        )

    offset = float(params.get("offset", 0.0))
    if side == "long":
        return band_value - offset
    return band_value + offset


# Registry of indicators permitted for REM stop/TP calculations
REM_INDICATORS_REGISTRY: dict[str, REMIndicatorSpec] = {
    "atr": REMIndicatorSpec(
        name="atr",
        description="Average True Range - single value volatility measure",
        required_params={"multiplier": float},
        optional_params={"length": (int, 14)},
        stop_calculator=_calculate_atr_stop,
        requires_prior_bar=True,
        requires_intrabar_zoom=False,
    ),
    "bollinger": REMIndicatorSpec(
        name="bollinger",
        description="Bollinger Band derived stop level",
        required_params={},
        optional_params={
            "band": (str, "auto"),
            "length": (int, 20),
            "std": (float, 2.0),
            "offset": (float, 0.0),
            "column_prefix": (str, "bb"),
        },
        stop_calculator=_calculate_bollinger_stop,
        requires_prior_bar=True,
        requires_intrabar_zoom=False,
    ),
    "chandelier": REMIndicatorSpec(
        name="chandelier",
        description=("Chandelier Stop - volatility trailing stop from HHV/LLV"),
        required_params={},
        optional_params={
            "multiplier": (float, 3.0),
            "length": (int, 22),
            "atr_length": (int, 14),
        },
        stop_calculator=_calculate_chandelier_stop,
        requires_prior_bar=True,
        requires_intrabar_zoom=False,
    ),
}


__all__ = ["REM_INDICATORS_REGISTRY", "REMIndicatorSpec"]
