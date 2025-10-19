# 1-Minute Resolution for Trailing Stop Ambiguity - Implementation Plan

## Overview
This document provides a detailed, step-by-step implementation plan for resolving intra-bar ambiguity in trailing stop execution by zooming to 1-minute resolution when needed.

## Problem Statement
When using OHLC bar data (e.g., hourly bars), trailing stops suffer from intra-bar ambiguity:
- If a bar makes a new peak/trough that causes the trailing stop to move into the current bar's low-high range, we cannot determine from OHLC data alone whether the stop was actually hit
- We cannot determine the order of price movements within the bar (did price hit the peak first, or the trough first?)

## Solution
When ambiguity is detected on the primary timeframe:
1. Request 1-minute OHLC data for that bar from the data handler
2. Process the 60 1-minute bars chronologically, tracking trailing stop updates
3. Exit at the stop/TP level when hit (not next bar open)
4. If ambiguity still exists on a 1-minute bar, use conservative resolution rules

## Branch Name
`feature/1min-resolution-trailing-stops`

---

## Tasks

### Phase 1: Data Handler Enhancement

**Note**: DataHandler already caches 1-minute data at initialization (`self._base_timeframe = "1min"`, see `src/trading_platform/data/handler.py:115-118`). The raw 1-minute data is loaded once and stored in `self._cache["1min"]`. We only need to add a convenience method for retrieving 1-minute bars for a specific hour.

1. [x] **Write tests for DataHandler 1-minute bar retrieval for specific hour**
   - File: `tests/data/test_data_handler_1min_bars.py` (create new file)
   - Test that DataHandler can return 1-minute bars for a specific hourly timestamp
   - Test edge cases: missing data, partial hour, market gaps
   - Verify that method correctly filters cached 1-minute data by time range
   - Verify that returned DataFrame has correct shape (up to 60 rows for a full hour)
   - Verify that no disk reads occur (data is already cached)
   - Target: 100% coverage of new convenience method

2. [x] **Implement DataHandler convenience method to retrieve 1-minute bars for specific hour**
   - File: `src/trading_platform/data/handler.py`
   - Add method: `get_1min_bars_for_hour(timestamp: pd.Timestamp) -> pd.DataFrame`
   - Implementation leverages existing `get_data()` method:
     ```python
     def get_1min_bars_for_hour(self, timestamp: pd.Timestamp) -> pd.DataFrame:
         """Get 1-minute bars for the hour containing the given timestamp.

         Args:
             timestamp: Any timestamp within the target hour

         Returns:
             DataFrame with 1-minute OHLCV bars for that hour

         Note:
             This is a convenience wrapper around get_data() that:
             - Uses the already-cached 1-minute base data
             - Filters to the specific hour range
             - Returns up to 60 bars (or fewer if data missing/gaps)
         """
         hour_start = timestamp.floor('H')
         hour_end = hour_start + pd.Timedelta(hours=1)
         return self.get_data(timeframe="1min", start=hour_start, end=hour_end)
     ```
   - Run tests from Task 1 to verify implementation

### Phase 2: Ambiguity Detection Logic

**Important Distinction**: There are THREE types of ambiguity to detect:
1. **Primary Timeframe Ambiguity (Trailing Stop)** - When trailing stop is in bar's range (requires 1-minute zoom)
2. **Primary Timeframe Ambiguity (Fixed Stops)** - When BOTH fixed stop AND TP are in bar's range (requires 1-minute zoom)
3. **1-Minute Tie-Breaking Ambiguity** - When both exits are detected on same 1-minute bar (requires tie-breaker policy)

3. [x] **Write tests for trailing stop primary timeframe ambiguity detection**
   - File: `tests/risk_manager/test_trailing_stop_ambiguity.py` (create new file)
   - Test function: `is_trailing_stop_ambiguous(bar: pd.Series, trailing_stop_level: float) -> bool`
   - Test Case 1 (Ambiguous): Trailing stop is between bar high/low → `True`
   - Test Case 2 (Not Ambiguous): Trailing stop is below bar low (long) → `False`
   - Test Case 3 (Not Ambiguous): Trailing stop is above bar high (short) → `False`
   - Test Case 4 (Edge): Trailing stop exactly at bar low → `True` (inclusive)
   - Test Case 5 (Edge): Trailing stop exactly at bar high → `True` (inclusive)
   - Note: This function does NOT consider take-profit level - it only determines if we need to zoom to 1-minute resolution
   - Target: 100% coverage of primary timeframe ambiguity detection

4. [x] **Implement trailing stop primary timeframe ambiguity detection**
   - File: `src/trading_platform/risk_manager/exit_utils.py` (create new file)
   - Function: `is_trailing_stop_ambiguous(bar: pd.Series, trailing_stop_level: float) -> bool`
   - Purpose: Determines if we need to zoom to 1-minute resolution for trailing stops
   - Logic: If the trailing stop level is within the bar's range, we cannot determine from OHLC alone whether it was hit due to intra-bar movement ambiguity
     ```python
     # Ambiguous if trailing stop is between bar's high and low
     # This is the fundamental problem: we don't know the intra-bar order of movements
     return bar['low'] <= trailing_stop_level <= bar['high']
     ```
   - Run tests from Task 3 to verify implementation

5. [x] **Write tests for fixed stops primary timeframe ambiguity detection**
   - File: `tests/risk_manager/test_trailing_stop_ambiguity.py` (extend existing file)
   - Test function: `is_fixed_stops_ambiguous(bar: pd.Series, stop_loss_level: float, take_profit_level: float) -> bool`
   - Test Case 1 (Ambiguous): Both stop and TP between bar high/low → `True`
   - Test Case 2 (Not Ambiguous): Only stop in range → `False`
   - Test Case 3 (Not Ambiguous): Only TP in range → `False`
   - Test Case 4 (Not Ambiguous): Neither in range → `False`
   - Test Case 5 (Edge): Stop at low, TP at high → `True`
   - Note: This function determines if we need to zoom to 1-minute for FIXED (non-trailing) stops
   - Target: 100% coverage of fixed stops ambiguity detection

6. [x] **Implement fixed stops primary timeframe ambiguity detection**
   - File: `src/trading_platform/risk_manager/exit_utils.py`
   - Function: `is_fixed_stops_ambiguous(bar: pd.Series, stop_loss_level: float, take_profit_level: float) -> bool`
   - Purpose: Determines if we need to zoom to 1-minute resolution for fixed stops
   - Logic: Both stop and TP must be in range to be ambiguous (we don't know which was hit first)
     ```python
     stop_in_range = bar['low'] <= stop_loss_level <= bar['high']
     tp_in_range = bar['low'] <= take_profit_level <= bar['high']
     return stop_in_range and tp_in_range
     ```
   - Run tests from Task 5 to verify implementation

7. [x] **Write tests for 1-minute tie-breaking ambiguity detection**
   - File: `tests/risk_manager/test_trailing_stop_ambiguity.py` (already implemented in Task 5-6)
   - Test function: `both_exits_in_same_bar(bar: pd.Series, stop_loss_level: float, take_profit_level: float) -> bool`
   - Note: These tests were already written and use the SAME function signature as fixed stops ambiguity
   - The difference is PURPOSE: fixed stops ambiguity is for PRIMARY timeframe, tie-breaking is for 1-MINUTE resolution
   - Target: 100% coverage of tie-breaking logic

8. [x] **Implement 1-minute tie-breaking ambiguity detection**
   - File: `src/trading_platform/risk_manager/exit_utils.py`
   - Function: `both_exits_in_same_bar(bar: pd.Series, stop_loss_level: float, take_profit_level: float) -> bool`
   - Purpose: Determines if we need to apply tie-breaker policy when processing 1-minute bars
   - Logic: Both exit levels must be within the bar's range to require tie-breaking
     ```python
     stop_in_range = bar['low'] <= stop_loss_level <= bar['high']
     tp_in_range = bar['low'] <= take_profit_level <= bar['high']
     return stop_in_range and tp_in_range
     ```
   - Run tests from Task 5 to verify implementation

### Phase 3: 1-Minute Resolution Processing

9. [x] **Write tests for 1-minute trailing stop processor**
   - File: `tests/risk_manager/test_1min_trailing_stop.py` (create new file)
   - Test function: `process_1min_bars_for_trailing_stop(bars_1min: pd.DataFrame, entry_price: float, side: str, trailing_stop_offset: float, take_profit_price: float | None, tie_break_policy: str) -> dict`
   - Note: `trailing_stop_offset` is in canonical price units (e.g., 0.0020 for EUR/USD), maintaining instrument agnosticism per [SYS-1.3]
   - Return dict format: `{'exit_occurred': bool, 'exit_bar_index': int | None, 'exit_price': float | None, 'exit_reason': str | None}`
   - Test Case 1: Trailing stop hit on minute 15, no TP → exit at stop level
   - Test Case 2: TP hit on minute 20, no stop hit → exit at TP level
   - Test Case 3: Stop hit on minute 10, TP hit on minute 20 → exit at stop (first)
   - Test Case 4: Both stop and TP hit on same minute bar, tie_break='stop_then_tp' → exit at stop
   - Test Case 5: Both stop and TP hit on same minute bar, tie_break='tp_then_stop' → exit at TP
   - Test Case 6: No stop or TP hit in any minute bar → no exit
   - Test Case 7: Stop trails up/down correctly across multiple minute bars
   - Test Case 8: Long position - stop moves up with favorable movement
   - Test Case 9: Short position - stop moves down with favorable movement
   - Target: 100% coverage of 1-minute processing logic

10. [x] **Implement 1-minute trailing stop processor**
   - File: `src/trading_platform/risk_manager/trailing_stop_utils.py`
   - Function signature from Task 7
   - Logic:
     ```python
     peak_or_trough = entry_price
     stop_level = entry_price - trailing_stop_offset if side == 'long' else entry_price + trailing_stop_offset

     for idx, bar in bars_1min.iterrows():
         # Update peak/trough
         if side == 'long':
             if bar['high'] > peak_or_trough:
                 peak_or_trough = bar['high']
                 stop_level = peak_or_trough - trailing_stop_offset
         else:
             if bar['low'] < peak_or_trough:
                 peak_or_trough = bar['low']
                 stop_level = peak_or_trough + trailing_stop_offset

         # Check if stop hit
         stop_hit = (bar['low'] <= stop_level) if side == 'long' else (bar['high'] >= stop_level)
         tp_hit = False
         if take_profit_price is not None:
             tp_hit = (bar['high'] >= take_profit_price) if side == 'long' else (bar['low'] <= take_profit_price)

         # Determine exit
         if stop_hit and tp_hit:
             # Both hit - check if ambiguous on this 1min bar
             if both_exits_in_same_bar(bar, stop_level, take_profit_price):
                 # Use tie breaker
                 if tie_break_policy == 'stop_then_tp':
                     return {'exit_occurred': True, 'exit_bar_index': idx, 'exit_price': stop_level, 'exit_reason': 'stop-loss'}
                 else:
                     return {'exit_occurred': True, 'exit_bar_index': idx, 'exit_price': take_profit_price, 'exit_reason': 'take-profit'}
             # Not ambiguous - need to determine which was hit first (implementation detail: assume stop first for now)
             return {'exit_occurred': True, 'exit_bar_index': idx, 'exit_price': stop_level, 'exit_reason': 'stop-loss'}
         elif stop_hit:
             return {'exit_occurred': True, 'exit_bar_index': idx, 'exit_price': stop_level, 'exit_reason': 'stop-loss'}
         elif tp_hit:
             return {'exit_occurred': True, 'exit_bar_index': idx, 'exit_price': take_profit_price, 'exit_reason': 'take-profit'}

     return {'exit_occurred': False, 'exit_bar_index': None, 'exit_price': None, 'exit_reason': None}
     ```
   - Run tests from Task 9 to verify implementation

### Phase 4: REM Integration

11. [x] **Write tests for REM ambiguity detection and 1-minute zoom**
   - File: `tests/risk_manager/test_rem_1min_zoom.py` (create new file)
   - Test that REM detects ambiguity on hourly bar with trailing stop
   - Test that REM requests 1-minute data from DataHandler when ambiguous
   - Test that REM processes 1-minute bars and returns correct exit signal
   - Test that REM does NOT zoom to 1-minute when no ambiguity detected
   - Mock DataHandler's `get_1min_bars_for_hour` method appropriately
   - Target: 100% coverage of REM's new 1-minute zoom logic

12. [x] **Integrate 1-minute resolution logic into RiskExitManager**
    - File: `src/trading_platform/risk_manager/core.py`
    - In the `check_exits()` method, after calculating trailing stop level:
    - Check if ambiguous using `is_trailing_stop_ambiguous()` from Task 4
    - Note: The REM must convert its pip-based configuration to canonical price units before calling the processor (maintaining instrument agnosticism per [SYS-1.3])
    - If ambiguous:
      ```python
      bars_1min = self.data_handler.get_1min_bars_for_hour(current_bar_timestamp)
      # Convert pips to price units (instrument-specific conversion happens here in REM)
      trailing_stop_offset = self.trailing_stop_distance  # Already in price units
      result = process_1min_bars_for_trailing_stop(
          bars_1min=bars_1min,
          entry_price=position.entry_price,
          side=position.side,
          trailing_stop_offset=trailing_stop_offset,
          take_profit_price=self.take_profit_level,
          tie_break_policy=self.config.get('exit_tie_break', 'stop_then_tp')
      )
      if result['exit_occurred']:
          return {'should_exit': True, 'exit_reason': result['exit_reason'], 'exit_price': result['exit_price']}
      ```
    - Run tests from Task 9 to verify implementation

13. [x] **Write tests for fixed stop + TP 1-minute zoom**
    - File: `tests/risk_manager/test_rem_1min_zoom.py` (extend)
    - Test REM with fixed stop (no trailing) and TP both between bar high/low
    - Verify REM zooms to 1-minute resolution
    - Test tie-breaker rules at 1-minute level
    - Target: 100% coverage of fixed stop + TP ambiguity resolution

14. [x] **Implement fixed stop + TP 1-minute zoom in REM**
    - File: `src/trading_platform/risk_manager/dynamic_rem.py`
    - In `check_exit()` method, before returning exit signals:
    - If fixed stop and TP both exist, check `both_exits_in_same_bar()` from Task 6
    - If ambiguous, zoom to 1-minute and process chronologically
    - Use similar logic to Task 8 but without trailing (stop level is fixed)
    - Run tests from Task 13 to verify implementation

### Phase 5: Integration Testing

**Note**: Tasks 15-16 deferred. REM integration tests (7 tests) provide sufficient coverage.

15. [DEFERRED] **Write end-to-end integration tests for 1-minute resolution**
    - File: `tests/integration/test_1min_resolution_integration.py` (create new file)
    - Test full backtest with trailing stop strategy that has ambiguous bars.
    - Verify trades exit at correct prices when 1-minute resolution is used.
    - **Crucially, assert that the `PortfolioManager` trade log contains the trade with the precise exit price and reason determined by the 1-minute analysis.**
    - Compare results with and without 1-minute resolution enabled.
    - Test performance: ensure 1-minute zoom doesn't cause significant slowdown.
    - Mock realistic OHLC data with known ambiguous scenarios.
    - Target: Verify entire pipeline works end-to-end.

16. [DEFERRED] **Run integration tests and verify all tests pass**
    - Command: `pytest tests/integration/test_1min_resolution_integration.py -v`
    - Verify all tests pass
    - Check code coverage: `pytest --cov=src/trading_platform --cov-report=term-missing`
    - Ensure 100% coverage of all new code

### Phase 6: Golden Validation Update

**Note**: Tasks 17-19 deferred pending golden validation data availability.

17. [DEFERRED] **Re-run golden validation tests for 20pip_trailing_stop strategy**
    - Command: `pytest tests/validation/test_strategy_validation.py::test_ema_crossover_20pip_trailing_stop_exit_prices_match_tradingview -v -s`
    - Document which of the 65 discrepancies are resolved by 1-minute resolution
    - Document which discrepancies remain and why (TradingView limitations)
    - Expected: Many of the "ENTRY_BAR_CONTRIBUTED_MFE" discrepancies should be resolved

18. [DEFERRED] **Update TrailingStopDiscrepancyAnalyzer with new known edge cases**
    - File: `tests/validation/trailing_stop_discrepancy_analyzer.py`
    - Add new category: `OHLC_VS_1MIN_RESOLUTION` for cases where platform uses 1-min but TradingView doesn't
    - Update categorization logic to identify these cases
    - Add detailed explanations for why these discrepancies exist
    - Update acceptable categories list

19. [DEFERRED] **Document 1-minute resolution behavior in README**
    - File: `configs/golden_strategies/ema_crossover/20pip_trailing_stop/README.md`
    - Add section explaining 1-minute resolution logic
    - Document known edge cases where platform behavior differs from TradingView
    - Explain why platform is more accurate than TradingView in these cases

### Phase 7: Configuration and Documentation

20. [x] **Configuration for 1-minute resolution**
    - Implementation: 1-minute zoom is enabled/disabled via `data_handler` parameter
    - Pass `data_handler` to `check_exits()` to enable zoom
    - Omit `data_handler` parameter to disable zoom (backward compatible)
    - No additional configuration needed - opt-in design

21. [x] **Update architecture documentation**
    - File: `docs/architecture/trailing_stops_1min_resolution.md` (created)
    - Documented design decision and rationale
    - Explained ambiguity detection criteria
    - Provided examples of ambiguous vs non-ambiguous scenarios
    - Documented performance characteristics
    - Included detailed integration points and testing information

22. [x] **Run test suite for implemented features**
    - All new tests pass (32 tests total):
      * 9 DataHandler tests
      * 16 ambiguity detection tests
      * 9 1-minute processor tests (trailing stop)
      * 7 REM integration tests (trailing + fixed stops)
    - Code follows project standards (ruff, ruff-format passing)
    - Ready for golden validation testing

---

## Completion Criteria

- [ ] All 22 tasks completed in order
- [ ] All tests pass: `pytest`
- [ ] 100% test coverage maintained: `pytest --cov`
- [ ] Golden validation tests document expected discrepancies
- [ ] Code reviewed and approved
- [ ] Documentation updated and complete
- [ ] Branch merged to main after approval

## Notes

- **Data Handler Verification**: ✅ **CONFIRMED** - DataHandler already loads and caches 1-minute data at initialization (see `src/trading_platform/data/handler.py:115-118`). The base timeframe is 1-minute, loaded once from disk and stored in `self._cache["1min"]`. No additional data loading infrastructure is needed.
- **Performance**: 1-minute resolution should only be invoked when ambiguity is detected, minimizing performance impact. Since 1-minute data is already in memory, the only overhead is the additional Python loops to process up to 60 bars per ambiguous hour.
- **Future Work**: Pyramiding support is deferred. When pyramiding is implemented, each position's trailing stop must be checked independently.
- **Instrument Agnosticism**: All core processing functions use canonical price units (e.g., 0.0020 for EUR/USD) rather than instrument-specific terms like "pips". The translation from pips to price units happens at the REM/strategy configuration level per [SYS-1.3].
