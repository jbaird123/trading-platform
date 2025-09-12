from __future__ import annotations

import numpy as np
import pandas as pd


def generate_ema_crossover_signals(
    data: pd.DataFrame, fast_period: int, slow_period: int
) -> pd.Series:
    """
    Generates trading signals based on the crossover of two Exponential
    Moving Averages (EMAs).

    Args:
        data: DataFrame with market data. Must contain 'ema_fast' and 'ema_slow' columns
              which are pre-calculated.
        fast_period: The window for the fast EMA (for metadata , not calculation).
        slow_period: The window for the slow EMA (for metadata , not calculation).

    Returns:
        A pandas Series with signals ('long', 'short', 'flat').
    """
    # To detect a crossover, we need to compare the current bar's state
    # with the previous bar's state. We use .shift(1) to get the previous values.
    prev_ema_fast = data["ema_fast"].shift(1)
    prev_ema_slow = data["ema_slow"].shift(1)

    # Condition for a bullish crossover (fast EMA crosses above slow EMA)
    long_signal = (prev_ema_fast < prev_ema_slow) & (
        data["ema_fast"] > data["ema_slow"]
    )

    # Condition for a bearish crossover (fast EMA crosses below slow EMA)
    short_signal = (prev_ema_fast > prev_ema_slow) & (
        data["ema_fast"] < data["ema_slow"]
    )

    # Use numpy.select to apply the conditions and generate signals.
    # The order matters: check for long, then short, otherwise default to 'flat'.
    signals = np.select(
        condlist=[long_signal, short_signal],
        choicelist=["long", "short"],
        default="flat",
    )

    # Return the signals as a pandas Series with the correct index and name.
    return pd.Series(signals, index=data.index, name="signal")
