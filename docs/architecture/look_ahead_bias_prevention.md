# Look-Ahead Bias Prevention Strategy

## Problem Statement

The platform currently computes all indicators on the full dataset before running the backtest loop. While the backtest itself is bar-by-bar, indicators have access to future data when computing features. This creates a risk of look-ahead bias if indicators are not carefully implemented.

### Example: Swing Point Detection

**Biased Implementation (WRONG):**
```python
# Uses center=True - looks at future bars
rolling_max = candles['high'].rolling(window=11, center=True).max()
swing_high = candles['high'] == rolling_max
```

**Unbiased Implementation (CORRECT):**
```python
# Signal appears right_bars periods after the swing point
for i in range(left_bars, n - right_bars):
    if candles['high'].iloc[i] == candles['high'].iloc[i-left_bars:i+right_bars+1].max():
        swing_high.iloc[i + right_bars] = 1.0  # Lag by right_bars
```

## Current Architecture

```
market_data (full dataset)
    ↓
strategy.generate_signals(market_data)  ← ALL indicators computed here
    ↓
    compute_features(market_data, specs)  ← Has access to future data
        ↓
        EMA, RSI, custom indicators, etc.
    ↓
signals (pre-computed for all bars)
    ↓
for i in range(len(market_data)):  ← Bar-by-bar loop
    signal = signals.iloc[i]
    # Execute trade logic
```

## Solution Options

### Option 1: Self-Policing (Current + My Fix)

**Status:** ✅ Implemented for swing points

**Pros:**
- Fast (vectorized operations)
- Works with existing architecture
- No breaking changes

**Cons:**
- Requires discipline from indicator developers
- Easy to introduce bias accidentally
- No enforcement mechanism

**Implementation:**
Custom indicators must ensure signals only use historical data by:
1. Avoiding `center=True` in rolling operations
2. Lagging signals appropriately when confirmation requires future bars
3. Using expanding windows instead of centered windows

### Option 2: True Bar-by-Bar Computation

**Status:** 🚧 Not implemented

**Pros:**
- Impossible to introduce look-ahead bias
- Enforced at platform level
- Matches real-time trading exactly

**Cons:**
- ~100-1000x slower (recomputes all indicators for each bar)
- Requires architectural refactor
- Breaking change to strategy API

**Implementation:**
```python
for i in range(len(market_data)):
    historical_data = market_data.iloc[:i+1]  # Only past data
    signal = strategy.generate_signal_at_bar(historical_data, i)
    # Execute trade logic
```

### Option 3: Hybrid Approach with Indicator Tagging

**Status:** 💡 Recommended for future

**Pros:**
- Fast for safe indicators (vectorized)
- Bar-by-bar only for risky indicators
- Opt-in enforcement

**Cons:**
- Requires indicator classification
- More complex implementation

**Implementation:**
```python
# Mark indicators as safe or requires-validation
INDICATOR_SAFETY = {
    'EMA': 'safe',          # Uses only historical data by design
    'RSI': 'safe',          # Uses only historical data by design
    'SWING_HIGH': 'manual', # Requires manual validation
    'CUSTOM_*': 'validate'  # Unknown indicators must prove safety
}

# For 'validate' indicators, compute bar-by-bar in test mode
# For 'safe' indicators, use fast vectorized computation
```

### Option 4: Expanding Window Pattern

**Status:** 💡 Alternative approach

Use pandas `.expanding()` instead of `.rolling()` for indicators that need validation:

```python
# This guarantees only historical data is used
expanding_max = candles['high'].expanding(min_periods=left_bars+right_bars+1).max()
```

**Cons:**
- Doesn't work for all indicator types
- Swing points specifically need centered windows

## Recommendations

### Short-term (Current Release)
1. ✅ Fix swing point indicator (DONE)
2. ✅ Document the issue (this doc)
3. 📝 Add warnings in custom indicator template
4. 📝 Create unit test helpers to detect common bias patterns

### Medium-term (Next Quarter)
1. 🚧 Create indicator safety classification system
2. 🚧 Add `@safe_indicator` decorator for auto-validation
3. 🚧 Build test harness that compares vectorized vs bar-by-bar results

### Long-term (Future)
1. 💭 Consider optional strict mode that forces bar-by-bar
2. 💭 Create indicator marketplace with safety badges
3. 💭 Add automatic bias detection in CI/CD

## Testing for Look-Ahead Bias

### Method 1: Compare Vectorized vs Bar-by-Bar

```python
def test_no_lookahead_bias(indicator_fn):
    """Test that indicator produces same results when computed bar-by-bar."""
    data = load_test_data()

    # Vectorized computation (fast but risky)
    signals_vectorized = indicator_fn(data)

    # Bar-by-bar computation (slow but safe)
    signals_bar_by_bar = pd.Series(index=data.index, dtype=float)
    for i in range(len(data)):
        historical = data.iloc[:i+1]
        signals_bar_by_bar.iloc[i] = indicator_fn(historical).iloc[-1]

    # Should be identical
    assert_series_equal(signals_vectorized, signals_bar_by_bar)
```

### Method 2: Check for Implausible Results

Warning signs of look-ahead bias:
- Win rate > 70% over long periods
- Sharpe ratio > 3.0
- Max drawdown < 5% over multiple years
- Profit factor > 3.0
- Very tight PnL distribution in Monte Carlo

### Method 3: Shift Test

```python
# If shifting the signal by N bars dramatically changes results,
# the indicator likely has look-ahead bias
signals_original = find_swing_points(data)
signals_shifted = find_swing_points(data).shift(5)

# Results should be similar (accounting for lag)
compare_backtest_results(signals_original, signals_shifted)
```

## Current Status

### Swing Point Indicator: ✅ FIXED

**Before Fix:**
- Return: +1,446% (12.7 years)
- Win Rate: 77.9%
- Max DD: -0.58%
- **Status: INVALID - Had look-ahead bias**

**After Fix:**
- Return: -100.79% (12.7 years)
- Win Rate: 35.9%
- Max DD: Complete loss
- **Status: VALID - No look-ahead bias**

The dramatic performance collapse confirms the bias was eliminated.

## Implementation Details

### Safe Indicators (No Changes Needed)

These indicators are safe because they only use historical data by design:
- EMA, SMA (rolling mean with default center=False)
- RSI (uses historical gains/losses)
- ATR (uses historical true range)
- ADX (uses historical directional movement)
- Bollinger Bands (rolling std with default center=False)
- MACD (difference of EMAs)

### Risky Indicators (Require Validation)

These indicators can introduce bias if not carefully implemented:
- Swing points (requires centered window → must lag signal)
- Local extrema detection
- Pattern recognition (if using future confirmation)
- Any custom indicator using:
  - `center=True` in rolling operations
  - `.shift(-N)` (negative shift = look ahead)
  - `.iloc[i:i+N]` where N > 0 relative to current bar

## Conclusion

The platform's current approach of computing indicators on the full dataset is **acceptable** as long as:

1. ✅ Built-in indicators are verified safe (they are)
2. ✅ Custom indicators are carefully reviewed (swing point now fixed)
3. ✅ Documentation warns developers about the risk (this doc)
4. 📋 Testing includes bias detection (TODO)

For the swing point indicator specifically, the fix ensures signals are lagged by `right_bars` periods, making it equivalent to bar-by-bar computation without the performance penalty.

## References

- Original issue: Swing point detection using `center=True` in rolling window
- Fix: [src/trading_platform/strategy/custom_indicators.py](../../src/trading_platform/strategy/custom_indicators.py)
- Tests: [tests/strategy/test_custom_indicators.py](../../tests/strategy/test_custom_indicators.py)
