# TradingView Golden Validation Indicator Exports

## Purpose

This directory contains PineScript files used to export indicator data from
TradingView for golden validation testing. Golden validation ensures our
platform's indicator calculations match TradingView's reference
implementation.

The exported data serves as the "ground truth" for validating that our
pandas-ta based indicator calculations produce numerically consistent results
with TradingView.

## Why Multiple Batch Files?

TradingView's CSV export has a column limit of approximately 11 total columns
(5 OHLCV + ~6 indicator columns). To export all 32 indicators needed for
comprehensive validation, we split them across 9 separate PineScript files.

Each batch is designed to stay safely under the export limit while maximizing
the number of indicators per export.

## Batch Files Overview

| Batch | File | Indicators | Columns | Description |
|-------|------|------------|---------|-------------|
| 1 | `batch1_moving_averages.pine` | 6 | 11 | SMA, EMA, WMA, RSI, ATR, PSAR |
| 2 | `batch2_oscillators.pine` | 8 | 13 | MACD×3, Stoch×2, CCI, ROC, Chop |
| 3 | `batch3_volume.pine` | 2 | 7 | OBV, VWAP |
| 4 | `batch4_adx.pine` | 3 | 8 | DI+, DI-, ADX |
| 5 | `batch5_bollinger.pine` | 3 | 8 | BB Upper, Middle, Lower |
| 6 | `batch6_supertrend.pine` | 2 | 7 | SuperTrend Value, Direction |
| 7 | `batch7_keltner.pine` | 3 | 8 | KC Upper, Middle, Lower |
| 8 | `batch8_ichimoku.pine` | 5 | 10 | Ich Conversion, Base, SpanA, SpanB, Lagging |
| 9 | `batch9_cmf.pine` | 1 | 6 | Chaikin Money Flow |

**Total: 32 indicator columns**

## How to Use These Files

### Prerequisites

1. TradingView account (free or paid)
2. Access to historical OHLCV data for your instrument
3. Understanding of how to use TradingView's Pine Editor

### Export Process

For each batch file, follow these steps:

#### 1. Load the PineScript

1. Open TradingView (https://www.tradingview.com)
2. Open the Pine Editor (Alt+E or click "Pine Editor" at bottom of screen)
3. Copy the contents of the batch PineScript file
4. Paste into Pine Editor
5. Click "Add to Chart"

#### 2. Configure the Chart

1. **Instrument**: Set to the same instrument you use in your tests
   - Example: `OANDA:EURUSD`
2. **Timeframe**: Match your test timeframe
   - Example: `1 hour` for hourly data
3. **Date Range**: Load maximum available history
   - Scroll back to the earliest available data point
   - Note the start date for metadata

#### 3. Verify Indicators

1. Check that the indicator panel displays in the top-right corner of the
   chart
2. Verify all expected indicators show current values in the table
3. Confirm all indicator plots are visible on the chart

#### 4. Export the Data

1. Click the three dots menu (...) at the top-right of the chart
2. Select "Export chart data..."
3. **CRITICAL**: In the export preview, verify ALL expected columns are
   present:
   - 5 OHLCV columns (time, open, high, low, close)
   - All indicator columns listed in the batch (see table above)
4. If any columns are missing, the export has hit TradingView's limit
5. Click "Export" to download the CSV file

#### 5. Verify the Export

Open the downloaded CSV file and confirm:
- First row contains column headers
- All expected indicator columns are present (compare to table above)
- Data starts from your earliest available date
- No missing or truncated columns
- Row count matches your expectations

#### 6. Store the Export

1. Rename the file to match the pattern:
   `batchN_<description>_<symbol>_<timeframe>.csv`
   - Example: `batch1_moving_averages_eurusd_1h.csv`

2. Move the file to:
   `data/dvc/golden/indicators/comprehensive/`

3. The file will be tracked with DVC (do not commit the CSV to git)

### Example: Exporting Batch 1

```bash
# 1. Open batch1_moving_averages.pine in TradingView Pine Editor
# 2. Add to chart for OANDA:EURUSD, 1 hour timeframe
# 3. Verify table shows: SMA 20, EMA 20, WMA 20, RSI 14, ATR 14, PSAR
# 4. Export chart data
# 5. Verify CSV has 11 columns (5 OHLCV + 6 indicators)
# 6. Rename and move file:

mv ~/Downloads/OANDA_EURUSD,\ 60.csv \
   data/dvc/golden/indicators/comprehensive/batch1_moving_averages_eurusd_1h.csv
```

### Repeat for All Batches

Export each of the 9 batch files following the same process. This will give
you a complete set of 32 indicators for golden validation testing.

## Data Integrity

**IMPORTANT**: Once exported, do NOT modify these CSV files. They represent
the ground truth from TradingView and must remain pristine for validation
to be meaningful.

Any data transformation or merging should be done in-memory during test
execution, never by modifying the source CSV files.

## Indicator Parameters

All indicators use standard parameters documented in each PineScript file.
Key parameters are also recorded in `metadata.json` for reference.

Examples:
- **RSI**: 14-period
- **MACD**: 12, 26, 9 (fast, slow, signal)
- **Bollinger Bands**: 20-period, 2.0 standard deviations
- **Stochastic**: 14-period K, 3-period D (SMA smoothing)

## Troubleshooting

### Issue: Export has fewer columns than expected

**Cause**: TradingView hit its column limit

**Solution**: The batch sizes in this directory have been optimized to avoid
this issue. If you still encounter it:
1. Verify you're using the correct PineScript file
2. Check that all indicators are calculating (not showing errors)
3. Try refreshing the page and re-adding the indicator

### Issue: Indicators not calculating

**Cause**: Insufficient historical data or warmup period

**Solution**: Some indicators (like Ichimoku with 52-period Span B) require
significant historical data. Ensure you've loaded enough data by scrolling
back to the earliest available bars.

### Issue: Column names don't match expectations

**Cause**: TradingView uses plot names for CSV column headers

**Solution**: The column names in the export will match the plot names in
each PineScript file (e.g., "RSI 14", "MACD", "Signal", etc.). These are
documented in the metadata.

### Issue: VWAP shows NaN or missing values

**Cause**: VWAP resets at session boundaries (daily)

**Solution**: This is expected behavior. VWAP will have gaps at the start
of each trading session. The test framework handles this appropriately.

### Issue: Different row counts between batches

**Cause**: Different indicators have different warmup periods

**Solution**: This is normal. The test framework will align all batches by
timestamp during in-memory merging. All batches should have the same date
range, but may differ slightly in the first few rows during warmup.

## Related Documentation

- **Export Guide**: `docs/tradingview_exports/batch_export_guide.md`
  - Detailed step-by-step instructions with screenshots

- **Metadata**: `data/dvc/golden/indicators/comprehensive/metadata.json`
  - Complete documentation of all exported batches
  - Indicator parameters and column mappings

- **Test Implementation**: `tests/data/test_golden_datasets.py`
  - Golden validation test framework
  - Tolerance definitions for each indicator

## Version History

- **2025-10-11**: Initial batch export structure created
  - 9 batches covering 32 indicators
  - PineScript v6
  - Optimized for TradingView's export column limits

## Contributing

If you need to add new indicators to golden validation:

1. Determine which batch has room (target <6 indicator outputs per batch)
2. Add the indicator calculation to the appropriate PineScript file
3. Update the plot and table sections
4. Update the batch number in the indicator title
5. Re-export the batch following the process above
6. Update `metadata.json` to reflect the new indicator

For new indicator families that don't fit in existing batches, create a
new `batchN_<description>.pine` file following the existing patterns.
