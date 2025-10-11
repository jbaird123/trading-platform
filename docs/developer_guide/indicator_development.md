# Indicator Development Guide

## Overview

This guide explains how to develop custom indicators for the trading
platform while avoiding look-ahead bias - a critical bug that can cause
false confidence in unprofitable strategies.

## What is Look-Ahead Bias?

Look-ahead bias occurs when an indicator uses future data that wouldn't
be available at the time of trading. This makes backtest results
unrealistically good, leading to strategies that fail in live trading.

### Real Example: Swing Points

**Before fix (with bias):**
- Return: +1,446%
- Win Rate: 77.9%
- **Problem**: Used `center=True` in rolling windows

**After fix (no bias):**
- Return: -100%
- Win Rate: 35.9%
- **Solution**: Proper lag applied to wait for confirmation

## Indicator Safety Levels

All indicators are classified into safety levels:

| Level | Description | Examples |
|-------|-------------|----------|
| **safe** | Built-in pandas-ta with known implementations | EMA, RSI, ATR, ADX |
| **validated** | Custom indicators, manually reviewed & tested | SWING_HIGH, HHV, LLV |
| **requires_test** | New/untrusted, must pass bias detection | FIB (TBD) |

## How to Write Safe Indicators

### Rule 1: Use Safe Helper Functions

The platform provides bias-free helpers in
[safe_indicators.py](../../src/trading_platform/strategy/safe_indicators.py):

```python
from trading_platform.strategy.safe_indicators import (
    safe_rolling_max,
    safe_rolling_min,
    safe_rolling_mean,
    hhv,
    llv,
    donchian_channels,
)

# ✅ SAFE: Uses helper function
def my_indicator(df: pd.DataFrame) -> pd.Series:
    return safe_rolling_max(df['high'], window=20)

# ❌ UNSAFE: Could introduce bias
def my_indicator(df: pd.DataFrame) -> pd.Series:
    return df['high'].rolling(window=20, center=True).max()
```

### Rule 2: Never Use `center=True`

```python
# ❌ WRONG: Looks ahead by window/2 bars
df['close'].rolling(20, center=True).mean()

# ✅ CORRECT: Only uses historical data
df['close'].rolling(20, center=False).mean()
```

### Rule 3: Never Use Negative Shifts

```python
# ❌ WRONG: Looks ahead 1 bar
df['close'].shift(-1)

# ✅ CORRECT: Looks back 1 bar (creates lag)
df['close'].shift(1)
```

### Rule 4: Apply Proper Lag for Confirmation

For indicators that need future confirmation (like swing points):

```python
def find_swing_high(highs, left_bars=10, right_bars=10):
    """
    Detects swing highs WITHOUT look-ahead bias.

    Key insight: Signal is emitted at bar i+right_bars,
    after we've confirmed no higher high occurred.
    """
    swing_high = pd.Series(0.0, index=highs.index)

    for i in range(left_bars, len(highs) - right_bars):
        window = highs.iloc[i-left_bars:i+right_bars+1]

        if highs.iloc[i] == window.max():
            # Emit signal AFTER confirmation period
            swing_high.iloc[i + right_bars] = 1.0

    return swing_high
```

## Testing Your Indicator

### Step 1: Write a Bias Detection Test

Add test to
[test_indicator_bias_detection.py](../../tests/strategy/test_indicator_bias_detection.py):

```python
def test_my_indicator_no_bias(test_ohlcv_data: pd.DataFrame) -> None:
    """My custom indicator should have no look-ahead bias."""

    def indicator(df: pd.DataFrame) -> pd.Series:
        return my_custom_indicator(df)

    result = detect_lookahead_bias(indicator, test_ohlcv_data)
    assert not result.has_bias, str(result)
```

### Step 2: Run the Test

```bash
poetry run pytest tests/strategy/test_indicator_bias_detection.py -v
```

If the test passes, your indicator is bias-free! ✅

### Step 3: Update Safety Registry

If test passes, add to
[indicator_safety.py](../../src/trading_platform/strategy/indicator_safety.py):

```python
INDICATOR_SAFETY: dict[str, SafetyLevel] = {
    # ... existing entries ...
    "MY_INDICATOR": SafetyLevel.VALIDATED,
}
```

And to
[indicators_registry.py](../../src/trading_platform/strategy/indicators_registry.py):

```python
INDICATORS: dict[str, dict] = {
    # ... existing entries ...
    "MY_INDICATOR": {
        "display": "My Custom Indicator",
        "category": "trend",
        "description": "Does something useful.",
        "params": [{"name": "length", "type": "int", "default": 20}],
        "safety": "validated",  # Add this field
        "ta": {"module": "", "class": ""},
    },
}
```

## Common Pitfalls

### ❌ Using pandas operations without understanding behavior

```python
# This MIGHT be safe, but are you sure?
df['close'].expanding().max()  # Safe: only uses historical data
df['close'].rolling(20).max()  # Safe if center=False (default)
df['close'].rolling(20, center=True).max()  # UNSAFE!
```

### ❌ Forgetting confirmation lag

```python
# WRONG: Detects pattern using future bars
def detect_pattern(df):
    for i in range(len(df)):
        # Looks at bars i-5 to i+5 (uses future!)
        if pattern_found(df.iloc[i-5:i+6]):
            signal.iloc[i] = 1.0  # Signal NOW, but used future data

# RIGHT: Applies proper lag
def detect_pattern(df):
    for i in range(len(df) - 5):  # Stop 5 bars early
        # Looks at bars i-5 to i+5
        if pattern_found(df.iloc[i-5:i+6]):
            signal.iloc[i + 5] = 1.0  # Signal AFTER confirmation
```

### ❌ Trusting "it looks fine" without testing

Always run bias detection tests. Visual inspection is not enough.

## How Bias Detection Works

The framework compares two computation methods:

1. **Vectorized**: Compute on full dataset (what you write)
2. **Bar-by-bar**: Compute incrementally (what actually happens)

If results differ, you have look-ahead bias.

```python
# Vectorized computation
signals_vectorized = my_indicator(full_dataset)

# Bar-by-bar computation (simulates real-time)
for i in range(len(dataset)):
    historical_only = dataset.iloc[:i+1]  # Only past + current
    signal_at_bar_i = my_indicator(historical_only).iloc[-1]

# Compare: should be identical
if signals_vectorized != signals_incremental:
    # BIAS DETECTED!
```

## Checklist for New Indicators

- [ ] Uses safe helper functions OR manually verified
- [ ] No `center=True` in rolling windows
- [ ] No negative shifts
- [ ] Proper confirmation lag applied if needed
- [ ] Bias detection test written and passing
- [ ] Added to `INDICATOR_SAFETY` registry
- [ ] Added "safety" field to `INDICATORS` registry
- [ ] Documented in this guide

## References

- [Bias Detection Implementation](../code_tasks/prevent_look_ahead_bias_in_indicators.md)
- [Safe Indicator Helpers](../../src/trading_platform/strategy/safe_indicators.py)
- [Bias Detection Tests](../../tests/strategy/test_indicator_bias_detection.py)
- [Indicator Safety Module](../../src/trading_platform/strategy/indicator_safety.py)

## Getting Help

If you're unsure whether your indicator is safe:

1. Write a bias detection test
2. Run it and check the results
3. Ask for code review before merging

**Remember**: A biased indicator is worse than no indicator.
It gives false confidence in losing strategies.
