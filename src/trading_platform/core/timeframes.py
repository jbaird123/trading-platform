"""Timeframe comparison utilities."""

# Mapping of timeframe strings to integer ranks (in minutes)
TIMEFRAME_RANKS = {
    "1min": 1,
    "5min": 5,
    "15min": 15,
    "30min": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
    "1H": 60,
    "4H": 240,
    "1D": 1440,
    "1W": 10080,
}


def compare_timeframes(tf1: str, tf2: str) -> int:
    """Compare two timeframes.

    Args:
        tf1: First timeframe string
        tf2: Second timeframe string

    Returns:
        Negative if tf1 < tf2, positive if tf1 > tf2, zero if equal

    Raises:
        ValueError: If either timeframe is not recognized
    """
    if tf1 not in TIMEFRAME_RANKS:
        raise ValueError(f"Unrecognized timeframe: {tf1}")
    if tf2 not in TIMEFRAME_RANKS:
        raise ValueError(f"Unrecognized timeframe: {tf2}")

    return TIMEFRAME_RANKS[tf1] - TIMEFRAME_RANKS[tf2]
