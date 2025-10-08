# Code Task: Prevent Look-Ahead Bias in Indicators

## Priority
**HIGH** - Affects backtest validity and can lead to false confidence in unprofitable strategies

## Problem Statement

The platform currently computes all indicator features on the full dataset before running the backtest loop. While the backtest executor itself is bar-by-bar, indicators receive the complete dataset and can accidentally introduce look-ahead bias if not carefully implemented.

### Recent Example
The swing point indicator was using `center=True` in rolling windows, giving it access to future bars. This resulted in:
- **Biased results:** +1,446% return, 77.9% win rate (impossible in real trading)
- **Actual results:** -100% return, 35.9% win rate (after fix)

## Root Cause

In [strategy/yaml_strategy.py:154](../../src/trading_platform/strategy/yaml_strategy.py):
```python
def generate_signals(self, df: pd.DataFrame) -> pd.Series:
    df2 = compute_features(df, self.features, self.parameters)  # Gets FULL dataset
    # ...
```

Indicators receive the entire dataset at once and must self-police to avoid using future data.

## Proposed Solutions

### Option 1: Automated Validation (Recommended)

Create a test harness that automatically detects look-ahead bias by comparing vectorized vs bar-by-bar computation.

**Files to create:**
- `tests/utils/bias_detection.py` - Core validation logic
- `tests/strategy/test_indicator_bias_detection.py` - Tests for all indicators

**Implementation:**
```python
def detect_lookahead_bias(
    indicator_fn: Callable,
    test_data: pd.DataFrame,
    tolerance: float = 1e-10
) -> BiasTestResult:
    """
    Tests if an indicator has look-ahead bias by comparing:
    1. Vectorized computation (full dataset at once)
    2. Bar-by-bar computation (only historical data)

    If results differ, indicator has look-ahead bias.
    """
    # Vectorized
    signals_vectorized = indicator_fn(test_data)

    # Bar-by-bar
    signals_incremental = pd.Series(index=test_data.index, dtype=float)
    for i in range(len(test_data)):
        historical_only = test_data.iloc[:i+1]
        result = indicator_fn(historical_only)
        signals_incremental.iloc[i] = result.iloc[-1]

    # Compare
    diff = (signals_vectorized - signals_incremental).abs()
    max_diff = diff.max()

    return BiasTestResult(
        has_bias=max_diff > tolerance,
        max_difference=max_diff,
        biased_bars=diff[diff > tolerance].index.tolist()
    )
```

**Pros:**
- Catches bias automatically
- No architectural changes needed
- Can run in CI/CD
- Educational (shows developers what went wrong)

**Cons:**
- Slow for large datasets (intended for testing only)
- Doesn't prevent bias, only detects it

**Effort:** 2-3 days

---

### Option 2: Safe Indicator Mode (Strict)

Add optional strict mode that forces bar-by-bar computation during backtesting.

**Files to modify:**
- `core/config.py` - Add `strict_mode: bool` flag
- `backtester/core.py` - Conditionally compute signals bar-by-bar
- `strategy/yaml_strategy.py` - Add `generate_signal_at_bar()` method

**Implementation:**
```python
# In RunConfig
class RunConfig(BaseModel):
    strict_mode: bool = False  # Forces bar-by-bar indicator computation

# In backtester/core.py
if config.strict_mode:
    # Bar-by-bar computation (slow but guaranteed safe)
    for i in range(len(market_data)):
        historical_data = market_data.iloc[:i+1]
        signal = strategy.generate_signal_at_bar(historical_data, i)
        # Execute trade logic
else:
    # Current approach (fast but requires indicator discipline)
    signals = strategy.generate_signals(market_data)
    for i in range(len(market_data)):
        signal = signals.iloc[i]
        # Execute trade logic
```

**Pros:**
- Impossible to have look-ahead bias in strict mode
- Opt-in (doesn't break existing code)
- Matches real-time trading exactly

**Cons:**
- 100-1000x slower (recomputes all indicators for each bar)
- Significant architectural changes
- May require refactoring some indicators

**Effort:** 1-2 weeks

---

### Option 3: Indicator Safety Classification

Create a registry that marks indicators as safe/unsafe and validates accordingly.

**Files to create:**
- `strategy/indicator_safety.py` - Safety classification registry
- `strategy/validators.py` - Validation functions

**Files to modify:**
- `strategy/indicators_registry.py` - Add safety metadata
- `strategy/features.py` - Check safety classification

**Implementation:**
```python
# Indicator safety levels
INDICATOR_SAFETY = {
    'EMA': SafetyLevel.SAFE,           # Proven safe (only uses historical data)
    'RSI': SafetyLevel.SAFE,           # Proven safe
    'SMA': SafetyLevel.SAFE,           # Proven safe
    'ATR': SafetyLevel.SAFE,           # Proven safe
    'SWING_HIGH': SafetyLevel.VALIDATED,  # Manually reviewed and validated
    'SWING_LOW': SafetyLevel.VALIDATED,   # Manually reviewed and validated
    'CUSTOM_*': SafetyLevel.REQUIRES_TEST, # Must pass bias detection test
}

# In compute_features()
for spec in specs:
    indicator_type = spec['type']
    safety = get_safety_level(indicator_type)

    if safety == SafetyLevel.REQUIRES_TEST:
        # Run bias detection test before using
        if not passes_bias_test(indicator_type):
            raise LookAheadBiasError(f"{indicator_type} failed bias detection")

    # Compute normally
    compute_indicator(spec)
```

**Pros:**
- Fast for safe indicators (no overhead)
- Automatic validation for untrusted indicators
- Good balance of safety and performance

**Cons:**
- Requires maintaining safety registry
- Initial classification effort
- May slow down development of new indicators

**Effort:** 1 week

---

### Option 4: Expanding Window Helpers

Provide helper functions that make it easy to write bias-free indicators.

**Files to create:**
- `strategy/safe_indicators.py` - Helper functions for common patterns

**Implementation:**
```python
def safe_rolling_max(series: pd.Series, window: int, lag: int = 0) -> pd.Series:
    """
    Computes rolling max without look-ahead bias.

    Args:
        series: Input series
        window: Window size
        lag: Additional lag to apply (default=0)

    Returns:
        Series with rolling max, properly lagged
    """
    # center=False ensures only historical data is used
    rolling = series.rolling(window=window, center=False).max()

    # Apply additional lag if needed
    if lag > 0:
        rolling = rolling.shift(lag)

    return rolling

def safe_swing_detection(
    highs: pd.Series,
    lows: pd.Series,
    left_bars: int,
    right_bars: int
) -> tuple[pd.Series, pd.Series]:
    """
    Detects swing points without look-ahead bias.

    Signal is lagged by right_bars periods to ensure only
    historical data is used for confirmation.
    """
    # Implementation here (current fixed version)
    pass
```

**Pros:**
- Makes writing safe indicators easier
- No performance penalty
- Educational (shows correct patterns)

**Cons:**
- Doesn't prevent misuse of raw pandas operations
- Requires developers to opt-in

**Effort:** 3-4 days

---

## Recommended Implementation Plan

### Phase 1: Immediate (This Sprint)
1. ✅ Fix swing point indicator (DONE)
2. **Create bias detection test harness** (Option 1)
3. **Add safe indicator helpers** (Option 4)
4. Run bias detection on all existing custom indicators

**Deliverables:**
- `tests/utils/bias_detection.py`
- `strategy/safe_indicators.py`
- Test coverage for SWING_HIGH, SWING_LOW, and any other custom indicators

**Time:** 3-5 days

### Phase 2: Short-term (Next Sprint)
1. **Add indicator safety classification** (Option 3)
2. Create documentation/guide for indicator developers
3. Add bias detection to CI/CD pipeline

**Deliverables:**
- `strategy/indicator_safety.py`
- Updated `indicators_registry.py` with safety metadata
- CI/CD job that fails on bias detection

**Time:** 1 week

### Phase 3: Long-term (Future)
1. **Implement strict mode** (Option 2) as optional feature
2. Create indicator testing template
3. Add automatic bias warnings in backtest reports

**Deliverables:**
- Strict mode implementation
- Template for new custom indicators
- Enhanced reporting

**Time:** 2 weeks

---

## Success Criteria

1. ✅ All existing indicators pass bias detection tests
2. ✅ New indicators automatically tested for bias
3. ✅ Documentation clearly explains the risk and how to avoid it
4. ✅ No breaking changes to existing strategies
5. ✅ Performance impact < 5% for normal (non-strict) mode

---

## Testing Strategy

### Unit Tests
```python
def test_ema_no_bias():
    """EMA should have no look-ahead bias."""
    result = detect_lookahead_bias(lambda df: ema(df['close'], 20), test_data)
    assert result.has_bias == False

def test_swing_points_no_bias():
    """Swing points should have no look-ahead bias after fix."""
    result = detect_lookahead_bias(find_swing_points, test_data)
    assert result.has_bias == False
```

### Integration Tests
```python
def test_backtest_results_match_strict_mode():
    """Normal mode should match strict mode for all safe indicators."""
    # Run backtest in normal mode
    signals_normal = strategy.generate_signals(data)

    # Run backtest in strict mode (bar-by-bar)
    signals_strict = run_strict_mode(strategy, data)

    # Should be identical
    assert_series_equal(signals_normal, signals_strict)
```

### Performance Tests
```python
def test_bias_detection_performance():
    """Bias detection should complete in reasonable time."""
    start = time.time()
    detect_lookahead_bias(find_swing_points, large_dataset)
    elapsed = time.time() - start

    # Should complete in < 30 seconds for 10k bars
    assert elapsed < 30.0
```

---

## Migration Path

### For Existing Strategies
1. Run bias detection on all custom indicators
2. Fix any detected bias (like we did for swing points)
3. Mark fixed indicators as validated
4. No changes needed to strategy YAML files

### For New Strategies
1. Use safe indicator helpers where possible
2. Run bias detection test before committing
3. CI/CD will catch any issues

### Breaking Changes
**None** - All changes are additive or opt-in

---

## Open Questions

1. **Q:** Should bias detection be mandatory in CI/CD?
   **A:** Yes for custom indicators, optional for built-in pandas-ta indicators

2. **Q:** What tolerance should we use for floating-point differences?
   **A:** 1e-10 for most indicators, configurable per indicator if needed

3. **Q:** Should we cache bias detection results?
   **A:** Yes, store results in indicator metadata to avoid re-running

4. **Q:** How do we handle indicators that are intentionally forward-looking (for research)?
   **A:** Add explicit `allow_lookahead=True` flag with warnings in reports

---

## Related Files

### Files to Create
- `tests/utils/bias_detection.py` - Core validation logic
- `tests/strategy/test_indicator_bias_detection.py` - Test suite
- `strategy/safe_indicators.py` - Helper functions
- `strategy/indicator_safety.py` - Safety classification (Phase 2)

### Files to Modify
- `strategy/indicators_registry.py` - Add safety metadata (Phase 2)
- `core/config.py` - Add strict_mode flag (Phase 3)
- `backtester/core.py` - Add strict mode logic (Phase 3)
- `strategy/yaml_strategy.py` - Add generate_signal_at_bar() method (Phase 3)

### Files to Document
- `docs/architecture/look_ahead_bias_prevention.md` - ✅ Already created
- `docs/user_guide/custom_indicators.md` - Best practices guide
- `docs/developer_guide/indicator_development.md` - Developer guide

---

## References

- Architecture doc: [docs/architecture/look_ahead_bias_prevention.md](../architecture/look_ahead_bias_prevention.md)
- Fixed indicator: [src/trading_platform/strategy/custom_indicators.py](../../src/trading_platform/strategy/custom_indicators.py)
- Tests: [tests/strategy/test_custom_indicators.py](../../tests/strategy/test_custom_indicators.py)
- Backtest results: Before fix (+1,446%), After fix (-100%)

---

## Estimated Effort

- **Phase 1 (Immediate):** 3-5 days
- **Phase 2 (Short-term):** 1 week
- **Phase 3 (Long-term):** 2 weeks
- **Total:** 3-4 weeks for complete implementation

## Priority Ranking

1. **Critical:** Bias detection test harness (prevents future issues)
2. **High:** Safe indicator helpers (makes correct usage easy)
3. **Medium:** Safety classification system (automation)
4. **Low:** Strict mode (nice-to-have for paranoid validation)
