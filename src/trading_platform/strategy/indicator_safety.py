"""
Indicator safety classification and validation system.

This module provides a registry-based safety classification for
indicators to prevent look-ahead bias. Indicators are classified
by their safety level, and untrusted indicators are automatically
tested before use.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class SafetyLevel(Enum):
    """Safety classification for indicators."""

    SAFE = "safe"
    # Proven safe through testing or review.
    # Built-in pandas-ta indicators with known safe implementations.

    VALIDATED = "validated"
    # Custom indicators that have been manually reviewed
    # and validated to be free from look-ahead bias.

    REQUIRES_TEST = "requires_test"
    # New or untrusted indicators that must pass automated
    # bias detection before being used.

    ALLOW_LOOKAHEAD = "allow_lookahead"
    # Explicitly marked as intentionally using future data
    # (for research purposes only). Will trigger warnings.


# Safety classification registry
INDICATOR_SAFETY: dict[str, SafetyLevel] = {
    # ========================================
    # SAFE: Built-in pandas-ta indicators
    # ========================================
    # Moving Averages
    "SMA": SafetyLevel.SAFE,
    "EMA": SafetyLevel.SAFE,
    "WMA": SafetyLevel.SAFE,
    # Oscillators
    "MACD": SafetyLevel.SAFE,
    "PSAR": SafetyLevel.SAFE,
    "ADX": SafetyLevel.SAFE,
    "RSI": SafetyLevel.SAFE,
    "STOCH": SafetyLevel.SAFE,
    "CCI": SafetyLevel.SAFE,
    "ROC": SafetyLevel.SAFE,
    "CHOP": SafetyLevel.SAFE,
    # Volatility
    "BB": SafetyLevel.SAFE,
    "ATR": SafetyLevel.SAFE,
    "KC": SafetyLevel.SAFE,
    # Volume
    "OBV": SafetyLevel.SAFE,
    "CMF": SafetyLevel.SAFE,
    # Trend
    "ICHIMOKU": SafetyLevel.SAFE,
    "SUPERTREND": SafetyLevel.SAFE,
    "VWAP": SafetyLevel.SAFE,
    # Candlestick patterns
    "CDL_DOJI": SafetyLevel.SAFE,
    "CDL_HAMMER": SafetyLevel.SAFE,
    "CDL_ENGULFING": SafetyLevel.SAFE,
    "CDL_MORNINGSTAR": SafetyLevel.SAFE,
    "CDL_EVENINGSTAR": SafetyLevel.SAFE,
    "CDL_HARAMI": SafetyLevel.SAFE,
    # ========================================
    # VALIDATED: Custom implementations
    # ========================================
    "EMASlope": SafetyLevel.VALIDATED,
    # Custom EMA slope calculation, reviewed and validated
    "BBWidth": SafetyLevel.VALIDATED,
    # Custom BB width calculation, reviewed and validated
    "SWING_HIGH": SafetyLevel.VALIDATED,
    # Fixed to remove look-ahead bias (was using center=True)
    "SWING_LOW": SafetyLevel.VALIDATED,
    # Fixed to remove look-ahead bias (was using center=True)
    "HHV": SafetyLevel.VALIDATED,
    # Custom rolling max, uses safe_rolling_max helper
    "LLV": SafetyLevel.VALIDATED,
    # Custom rolling min, uses safe_rolling_min helper
    "DC": SafetyLevel.VALIDATED,
    # Donchian Channels, uses safe helpers
    # ========================================
    # REQUIRES_TEST: Unclassified
    # ========================================
    # FIB is TBD - requires testing when implemented
    "FIB": SafetyLevel.REQUIRES_TEST,
}


def get_safety_level(indicator_type: str) -> SafetyLevel:
    """
    Get the safety level for an indicator type.

    Args:
        indicator_type: Indicator type name (e.g., 'EMA', 'SWING_HIGH')

    Returns:
        SafetyLevel for the indicator

    Example:
        >>> get_safety_level('EMA')
        SafetyLevel.SAFE
        >>> get_safety_level('SWING_HIGH')
        SafetyLevel.VALIDATED
    """
    return INDICATOR_SAFETY.get(indicator_type, SafetyLevel.REQUIRES_TEST)


def is_indicator_safe(indicator_type: str) -> bool:
    """
    Check if an indicator is safe to use without testing.

    Args:
        indicator_type: Indicator type name

    Returns:
        True if indicator is SAFE or VALIDATED

    Example:
        >>> is_indicator_safe('EMA')
        True
        >>> is_indicator_safe('UNKNOWN_INDICATOR')
        False
    """
    level = get_safety_level(indicator_type)
    return level in (SafetyLevel.SAFE, SafetyLevel.VALIDATED)


def requires_bias_test(indicator_type: str) -> bool:
    """
    Check if indicator requires bias detection testing.

    Args:
        indicator_type: Indicator type name

    Returns:
        True if indicator requires testing before use

    Example:
        >>> requires_bias_test('EMA')
        False
        >>> requires_bias_test('FIB')
        True
    """
    level = get_safety_level(indicator_type)
    return level == SafetyLevel.REQUIRES_TEST


def is_lookahead_allowed(indicator_type: str) -> bool:
    """
    Check if indicator is explicitly marked as lookahead-allowed.

    Args:
        indicator_type: Indicator type name

    Returns:
        True if lookahead is explicitly allowed (research only)

    Example:
        >>> is_lookahead_allowed('EMA')
        False
    """
    level = get_safety_level(indicator_type)
    return level == SafetyLevel.ALLOW_LOOKAHEAD


class LookAheadBiasError(Exception):
    """Raised when an indicator fails bias detection."""

    pass


def validate_indicator_safety(
    indicator_type: str,
    test_data: pd.DataFrame | None = None,
) -> None:
    """
    Validate that an indicator is safe to use.

    Args:
        indicator_type: Indicator type name
        test_data: Optional test data for bias detection
                   (required if indicator REQUIRES_TEST)

    Raises:
        LookAheadBiasError: If indicator requires testing but fails

    Example:
        >>> validate_indicator_safety('EMA')  # Safe, no error
        >>> validate_indicator_safety('UNKNOWN', test_data)  # May raise
    """
    level = get_safety_level(indicator_type)

    if level in (SafetyLevel.SAFE, SafetyLevel.VALIDATED):
        # Already verified safe
        return

    if level == SafetyLevel.ALLOW_LOOKAHEAD:
        # Explicitly allowed (will warn elsewhere)
        return

    if level == SafetyLevel.REQUIRES_TEST:
        # Need to run bias detection
        if test_data is None:
            raise LookAheadBiasError(
                f"Indicator '{indicator_type}' requires bias "
                f"detection testing but no test data provided. "
                f"Either:\n"
                f"1. Add it to INDICATOR_SAFETY as SAFE/VALIDATED\n"
                f"2. Provide test_data for automatic validation\n"
                f"3. Run tests in tests/strategy/"
                f"test_indicator_bias_detection.py"
            )

        # Import here to avoid circular dependency

        # This would need the actual indicator function
        # For now, we raise an error indicating manual testing needed
        raise LookAheadBiasError(
            f"Indicator '{indicator_type}' is not classified as safe. "
            f"Please run bias detection tests in "
            f"tests/strategy/test_indicator_bias_detection.py "
            f"and update INDICATOR_SAFETY if it passes."
        )


def get_safety_summary() -> dict[str, list[str]]:
    """
    Get a summary of all indicators by safety level.

    Returns:
        Dict mapping safety level names to lists of indicators

    Example:
        >>> summary = get_safety_summary()
        >>> print(f"Safe: {len(summary['safe'])} indicators")
    """
    summary: dict[str, list[str]] = {
        "safe": [],
        "validated": [],
        "requires_test": [],
        "allow_lookahead": [],
    }

    for indicator, level in INDICATOR_SAFETY.items():
        summary[level.value].append(indicator)

    return summary
