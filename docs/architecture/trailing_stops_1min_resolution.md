# 1-Minute Resolution for Trailing Stops

## Overview

This document describes the 1-minute resolution feature for resolving intra-bar ambiguity in trailing stop and fixed stop exit detection.

## Problem Statement

### Intra-Bar Ambiguity

When using OHLC (Open-High-Low-Close) data, we only know the price range within each bar, not the chronological order of price movements. This creates ambiguity in several scenarios:

1. **Trailing Stop Ambiguity**: When a trailing stop level falls within a bar's high-low range, we cannot determine from OHLC data alone whether the stop was actually hit, or if the price stayed above/below the stop throughout the bar.

2. **Fixed Stop + TP Ambiguity**: When both a fixed stop-loss AND take-profit level are within a bar's range, we cannot determine which was hit first.

### Example

Consider a long position at 1.0600 with a 20-pip trailing stop:
- Hourly bar: Open=1.0600, High=1.0605, Low=1.0575, Close=1.0590
- Trailing stop: 1.0580 (entry - 20 pips)
- **Ambiguity**: The low (1.0575) is below the stop (1.0580), but did price actually hit 1.0580?

From OHLC alone, we know:
- Price reached 1.0575 at some point
- Price reached 1.0605 at some point
- But we don't know the ORDER

Possible scenarios:
1. Price went up first (1.0605), then down (1.0575) → stop WAS hit
2. Price went down first (1.0575), then up (1.0605) → stop was NOT hit (if it bottomed at 1.0585)

## Solution: 1-Minute Resolution Zoom

When ambiguity is detected on the primary timeframe (e.g., hourly), the system "zooms in" to 1-minute resolution to process the bar chronologically.

### Key Design Decisions

1. **Opt-In via DataHandler Parameter**
   - 1-minute zoom is enabled by passing a `data_handler` to `check_exits()`
   - If no `data_handler` is provided, falls back to OHLC-based checking
   - This allows for backward compatibility and performance tuning

2. **Ambiguity Detection First**
   - Only zoom to 1-minute when ambiguity is detected
   - For non-ambiguous bars, use fast OHLC checking
   - Minimizes performance impact

3. **Separate Processors for Different Exit Types**
   - `process_1min_bars_for_trailing_stop()`: Handles trailing stops with peak/trough tracking
   - `process_1min_bars_for_fixed_stops()`: Handles fixed stops (simpler, no trailing logic)

4. **Early Return After 1-Minute Processing**
   - Once 1-minute resolution is used, return immediately (don't fall through to OHLC logic)
   - This prevents double-checking and ensures consistency

## Ambiguity Detection Criteria

### Trailing Stop Ambiguity

A trailing stop is ambiguous when the stop level falls within the bar's high-low range:

```python
def is_trailing_stop_ambiguous(bar: pd.Series, trailing_stop_level: float) -> bool:
    return bar["low"] <= trailing_stop_level <= bar["high"]
```

### Fixed Stop + TP Ambiguity

Fixed stops are ambiguous when BOTH the stop AND take-profit are within the bar's range:

```python
def is_fixed_stops_ambiguous(
    bar: pd.Series, stop_loss_level: float, take_profit_level: float
) -> bool:
    stop_in_range = bar["low"] <= stop_loss_level <= bar["high"]
    tp_in_range = bar["low"] <= take_profit_level <= bar["high"]
    return stop_in_range and tp_in_range
```

## Processing Logic

### Trailing Stops

1. Initialize peak/trough at entry price
2. Initialize stop level at entry ± trailing_stop_offset
3. For each 1-minute bar (chronologically):
   a. Check if current stop level was hit
   b. Check if take-profit was hit
   c. If both hit on same bar, apply tie-breaker policy
   d. If exit detected, return immediately
   e. Otherwise, update peak/trough and stop level for next bar
4. If no exit in any bar, return None

### Fixed Stops

1. For each 1-minute bar (chronologically):
   a. Check if stop was hit
   b. Check if take-profit was hit
   c. If both hit on same bar, apply tie-breaker policy
   d. If exit detected, return immediately
2. If no exit in any bar, return None

## Performance Characteristics

### When 1-Minute Zoom Occurs

- **Best Case**: No ambiguity → no zoom → O(1) per bar
- **Worst Case**: Ambiguity on every bar → zoom every bar → O(60) per bar

### Optimization Strategies

1. **Ambiguity Detection is Fast**: Simple comparison, done before fetching 1-minute data
2. **DataHandler Caching**: 1-minute data is pre-loaded and cached at initialization
3. **Early Exit**: Return as soon as exit is detected (don't process remaining 1-minute bars)

### Typical Performance

For a backtest with:
- 1000 hourly bars
- 10% ambiguous bars (100 bars)
- Average exit at minute 30/60

Expected overhead:
- 900 bars: O(1) each = 900 operations
- 100 bars: O(30) each = 3000 operations
- Total: ~4x overhead compared to OHLC-only

This is acceptable for most backtests, as accuracy is more important than speed.

## Examples

### Example 1: Trailing Stop Hit (Ambiguous)

**Primary Timeframe (Hourly)**:
- Bar: Open=1.0600, High=1.0605, Low=1.0575, Close=1.0590
- Position: Long at 1.0600, trailing stop at 1.0580
- Detection: Ambiguous (stop is between low and high)

**1-Minute Resolution**:
- Minutes 0-29: Price stays at 1.0600
- Minute 30: Price drops to 1.0575 → **stop hit at 1.0580**
- Result: Exit at 1.0580, reason="stop-loss"

### Example 2: Trailing Stop NOT Hit (Ambiguous)

**Primary Timeframe (Hourly)**:
- Bar: Open=1.0600, High=1.0605, Low=1.0575, Close=1.0590
- Position: Long at 1.0600, trailing stop at 1.0580
- Detection: Ambiguous

**1-Minute Resolution**:
- Minutes 0-59: Price stays between 1.0585-1.0605 (never touches 1.0580)
- Result: No exit (return None)

### Example 3: Non-Ambiguous (No Zoom)

**Primary Timeframe (Hourly)**:
- Bar: Open=1.0600, High=1.0610, Low=1.0590, Close=1.0605
- Position: Long at 1.0600, trailing stop at 1.0580
- Detection: NOT ambiguous (low=1.0590 is above stop=1.0580)

**Resolution**:
- No 1-minute zoom needed
- Fast OHLC checking: No exit
- Result: No exit (return None)

## Integration Points

### RiskExitManager

The 1-minute zoom logic is integrated into `RiskExitManager.check_exits()`:

1. Calculate trailing stop level (if applicable)
2. Check for trailing stop ambiguity
3. If ambiguous, zoom to 1-minute and process
4. Calculate fixed stop and TP levels
5. Check for fixed stop ambiguity
6. If ambiguous, zoom to 1-minute and process
7. Otherwise, use standard OHLC exit checking

### DataHandler

The `DataHandler` provides the 1-minute data:

```python
def get_1min_bars_for_hour(self, timestamp: pd.Timestamp) -> pd.DataFrame:
    """Get 1-minute bars for the hour containing the given timestamp."""
    # Returns 60 bars (one per minute) for the specified hour
```

**Note**: The DataHandler already caches all 1-minute data at initialization, so no additional data loading is required.

## Configuration

### Enabling 1-Minute Resolution

Pass a `data_handler` to `check_exits()`:

```python
rem = RiskExitManager(config=config, instrument=instrument)
result = rem.check_exits(position, current_bar, data_handler=data_handler)
```

### Disabling 1-Minute Resolution

Omit the `data_handler` parameter:

```python
rem = RiskExitManager(config=config, instrument=instrument)
result = rem.check_exits(position, current_bar)  # No data_handler
```

## Testing

### Unit Tests

- `tests/risk_manager/test_trailing_stop_ambiguity.py`: Ambiguity detection logic (16 tests)
- `tests/risk_manager/test_1min_trailing_stop.py`: 1-minute processor logic (9 tests)
- `tests/risk_manager/test_rem_1min_zoom.py`: REM integration (7 tests)

### Coverage

- 100% coverage of all new code
- Comprehensive test cases covering:
  - Long and short positions
  - Trailing stops with favorable movement
  - Fixed stops with take-profit
  - Tie-breaker scenarios
  - Non-ambiguous scenarios (no zoom)

## Known Limitations

1. **Requires 1-Minute Data**: The DataHandler must have 1-minute data available
2. **Hourly Bars Only**: Currently implemented for hourly primary timeframe
3. **No Intra-Minute Ambiguity**: If 1-minute bars themselves are ambiguous, falls back to tie-breaker policy

## Future Enhancements

1. Support for other primary timeframes (4-hour, daily)
2. Recursive zooming (if 1-minute is still ambiguous, zoom to ticks)
3. Performance optimizations (e.g., skip minutes that cannot possibly contain the exit)
4. Configuration for zoom timeframe (e.g., use 5-minute instead of 1-minute)

## References

- Implementation Plan: `docs/code_tasks/implement_1min_resolution_for_trailing_stops.md`
- Validation: `tests/validation/trailing_stop_discrepancy_analyzer.py`
- Validation Criteria: [BT-7.8], [SE-3.5.3]
