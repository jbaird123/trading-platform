# Batch 11: Level Indicators Export Instructions

## Overview
Batch 11 adds validation for 6 level indicators that have direct PineScript equivalents.

## Indicators to Export (7 columns + 5 OHLCV = 12 total)

1. **HHV 20** - Highest High Value (20-period rolling maximum)
2. **LLV 20** - Lowest Low Value (20-period rolling minimum)
3. **DC Upper** - Donchian Channel Upper Band
4. **DC Lower** - Donchian Channel Lower Band
5. **Swing High** - Pivot High detection (10 left bars, 10 right bars)
6. **Swing Low** - Pivot Low detection (10 left bars, 10 right bars)
7. **ATR Percentile** - Percentile rank of ATR(14) over 20-period lookback

## TradingView Export Steps

1. **Open TradingView Chart**
   - Symbol: EURUSD
   - Broker: OANDA
   - Timeframe: 1 hour

2. **Load PineScript**
   - Open Pine Editor
   - Copy contents of `batch11_levels.pine`
   - Click "Add to Chart"

3. **Verify Date Range**
   - Start: March 4, 2022 09:00:00 EST
   - End: October 10, 2025 16:00:00 EDT
   - Should have 22,447 bars

4. **Export Data**
   - Right-click on chart
   - Select "Export chart data..."
   - Save as: `batch11_levels_eurusd_1h.csv`

5. **Verify Export**
   - Check column count: 12 columns (time, open, high, low, close, hhv 20, llv 20, dc upper, dc lower, swing high, swing low, atr percentile)
   - Check row count: 22,447 rows (+ 1 header row)
   - Check column names match metadata.json expectations

6. **Add to DVC**
   ```bash
   # Move CSV to data directory
   mv ~/Downloads/batch11_levels_eurusd_1h.csv data/dvc/golden/indicators/comprehensive/

   # Add to DVC tracking
   dvc add data/dvc/golden/indicators/comprehensive/batch11_levels_eurusd_1h.csv

   # Commit DVC pointer
   git add data/dvc/golden/indicators/comprehensive/batch11_levels_eurusd_1h.csv.dvc
   git commit -m "data: Add batch11 level indicators golden dataset"

   # Update metadata
   # Edit metadata.json: change batches_pending from [11] to []
   # Edit metadata.json: change batches_exported from 10 to 11
   git add data/dvc/golden/indicators/comprehensive/metadata.json
   git commit -m "data: Mark batch11 as exported"

   # Push data to remote
   dvc push
   ```

7. **Run Tests**
   ```bash
   SKIP=block-pandas-ta-import poetry run pytest tests/validation/test_indicator_validation.py::test_indicator_matches_tradingview_comprehensive -v
   ```

## Expected Results

After export and DVC setup, the validation tests should:
- Add 7 new passing test cases (HHV, LLV, DC_upper, DC_lower, SWING_HIGH, SWING_LOW, ATRPercentile)
- Increase total passing tests from 33 to 40
- Increase indicator coverage from 52.8% (19/36) to 69.4% (25/36)

## Notes

- **Swing High/Low**: These indicators return NaN for most bars, only showing values when a pivot point is detected
- **ATR Percentile**: Returns a value between 0-100 representing the percentile rank
- **DC Channels**: Should match HHV/LLV exactly for the given period
- All indicators use standard TradingView functions (no custom calculations)
