"""
Template for creating new custom indicators.

Copy this file and follow the steps below to create a bias-free indicator.

IMPORTANT: Always use safe helper functions from safe_indicators.py
to avoid look-ahead bias.
"""

from __future__ import annotations

import pandas as pd

# Import safe helpers
from trading_platform.strategy.safe_indicators import (
    safe_rolling_max,
    safe_rolling_mean,
    safe_rolling_min,
)


def my_custom_indicator(
    df: pd.DataFrame,
    param1: int = 20,
    param2: float = 2.0,
) -> pd.Series | pd.DataFrame:
    """
    [REPLACE WITH YOUR DESCRIPTION]

    One-line description of what this indicator does.

    Detailed explanation of the calculation methodology.
    Explain the parameters and expected behavior.

    Args:
        df: Input DataFrame with OHLCV columns
        param1: [DESCRIBE PARAMETER]
        param2: [DESCRIBE PARAMETER]

    Returns:
        Series (or DataFrame for multi-column indicators) containing
        the indicator values

    Example:
        >>> df = load_market_data()
        >>> indicator = my_custom_indicator(df, param1=20, param2=2.0)

    Safety Notes:
        - Uses safe_rolling_mean() to avoid look-ahead bias
        - All rolling windows use center=False (implicit in helpers)
        - No negative shifts used
    """
    # Step 1: Extract required price data
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # Step 2: Compute your indicator using SAFE HELPERS
    # ✅ CORRECT: Use safe helpers
    rolling_avg = safe_rolling_mean(close, window=param1)
    rolling_high = safe_rolling_max(high, window=param1)
    rolling_low = safe_rolling_min(low, window=param1)

    # ❌ WRONG: Don't use raw pandas with center=True
    # rolling_avg = close.rolling(param1, center=True).mean()

    # Step 3: Compute final indicator value
    # Example: Simple normalized distance from mean
    distance_from_mean = (close - rolling_avg) / (rolling_high - rolling_low + 1e-10)

    # Step 4: Return the indicator
    result: pd.Series = distance_from_mean
    return result


# ============================================================================
# TESTING YOUR INDICATOR
# ============================================================================


def test_my_custom_indicator_no_bias() -> None:
    """
    Test that your indicator has no look-ahead bias.

    Add this test to tests/strategy/test_indicator_bias_detection.py
    """
    import numpy as np

    from tests.utils.bias_detection import detect_lookahead_bias

    # Create test data
    np.random.seed(42)
    n = 500
    test_data = pd.DataFrame(
        {
            "open": np.random.uniform(95, 105, n),
            "high": np.random.uniform(100, 110, n),
            "low": np.random.uniform(90, 100, n),
            "close": np.random.uniform(95, 105, n),
            "volume": np.random.uniform(1000, 10000, n),
        },
        index=pd.date_range("2020-01-01", periods=n, freq="1h"),
    )

    # Define wrapper function
    def indicator(df: pd.DataFrame) -> pd.Series:
        result = my_custom_indicator(df, param1=20, param2=2.0)
        # Cast to Series (template always returns Series, not DataFrame)
        assert isinstance(result, pd.Series), "Expected Series from template"
        return result

    # Run bias detection
    result = detect_lookahead_bias(indicator, test_data)

    # Assert no bias
    assert not result.has_bias, str(result)


# ============================================================================
# REGISTRATION CHECKLIST
# ============================================================================
"""
After implementing and testing your indicator:

1. ✅ Add to src/trading_platform/strategy/indicators_registry.py:
   ```python
   "MY_INDICATOR": {
       "display": "My Custom Indicator",
       "category": "trend",  # or "momentum", "volatility", "volume"
       "description": "Brief description of what it does.",
       "params": [
           {"name": "param1", "type": "int", "default": 20},
           {"name": "param2", "type": "float", "default": 2.0},
       ],
       "safety": "validated",  # Mark as validated after testing
       "ta": {"module": "", "class": ""},  # custom implementation
   }
   ```

2. ✅ Add to src/trading_platform/strategy/indicator_safety.py:
   ```python
   INDICATOR_SAFETY: dict[str, SafetyLevel] = {
       # ... existing entries ...
       "MY_INDICATOR": SafetyLevel.VALIDATED,
   }
   ```

3. ✅ Add to src/trading_platform/strategy/features.py:
   ```python
   def my_custom_indicator_wrapper(
       df: pd.DataFrame, param1: int, param2: float
   ) -> pd.Series:
       from .custom_indicators import my_custom_indicator
       return my_custom_indicator(df, param1, param2)
   ```

4. ✅ Add to src/trading_platform/strategy/custom_indicators.py:
   - Move your implementation there from this template

5. ✅ Add test to tests/strategy/test_indicator_bias_detection.py:
   - Copy the test function above

6. ✅ Update docs if needed:
   - Add usage examples to developer guide
   - Update any relevant strategy examples

7. ✅ Run tests:
   ```bash
   poetry run pytest tests/strategy/test_indicator_bias_detection.py -v
   ```

8. ✅ Commit with descriptive message:
   ```bash
   git add .
   git commit -m "feat: Add MY_INDICATOR (bias-free, validated)"
   ```
"""


# ============================================================================
# COMMON PATTERNS
# ============================================================================
"""
Here are some safe patterns for common indicator calculations:

## Pattern 1: Rolling Statistics
```python
# ✅ SAFE
highest = safe_rolling_max(series, window=20)
lowest = safe_rolling_min(series, window=20)
average = safe_rolling_mean(series, window=20)

# ❌ UNSAFE
highest = series.rolling(20, center=True).max()  # Looks ahead!
```

## Pattern 2: Lagged Comparisons
```python
# ✅ SAFE
prev_value = series.shift(1)  # Positive shift = lag
change = series - prev_value

# ❌ UNSAFE
next_value = series.shift(-1)  # Negative shift = look ahead!
```

## Pattern 3: Expanding Windows (All-Time High/Low)
```python
# ✅ SAFE
from safe_indicators import safe_expanding_max
all_time_high = safe_expanding_max(series)

# ❌ POTENTIALLY UNSAFE
all_time_high = series.expanding().max()  # OK, but use helper for clarity
```

## Pattern 4: Confirmation-Based Signals
```python
# ✅ SAFE: Apply lag for confirmation period
def detect_pattern_safe(df, lookback=10, confirm=5):
    signal = pd.Series(0.0, index=df.index)
    for i in range(lookback, len(df) - confirm):
        window = df.iloc[i-lookback:i+confirm+1]
        if pattern_detected(window):
            # Signal AFTER confirmation period
            signal.iloc[i + confirm] = 1.0
    return signal

# ❌ UNSAFE: No confirmation lag
def detect_pattern_unsafe(df, lookback=10, confirm=5):
    signal = pd.Series(0.0, index=df.index)
    for i in range(lookback, len(df)):
        window = df.iloc[i-lookback:i+confirm+1]  # Uses future bars!
        if pattern_detected(window):
            signal.iloc[i] = 1.0  # Signal NOW, but used future
    return signal
```
"""
