# TradingView Batch Export Guide

## Overview

Due to TradingView's CSV export column limit (~13 columns), we've divided
the 19 indicators into 5 batches. Each batch must be exported separately
and then combined.

## Indicator Distribution

### Batch 1: Moving Averages & Basic (8 indicators)
**File:** `batch1_moving_averages.pine`
**Columns:** 5 OHLCV + 8 indicators = 13 total

1. SMA 20
2. EMA 20
3. WMA 20
4. RSI 14
5. ATR 14
6. Parabolic SAR
7. OBV
8. VWAP

### Batch 2: Oscillators (8 indicators)
**File:** `batch2_oscillators.pine`
**Columns:** 5 OHLCV + 8 indicators = 13 total

1. MACD Line
2. MACD Signal
3. MACD Histogram
4. Stochastic K
5. Stochastic D
6. CCI 20
7. ROC 12
8. Choppiness Index

### Batch 3: Trend & Bands (8 indicators)
**File:** `batch3_trend_bands.pine`
**Columns:** 5 OHLCV + 8 indicators = 13 total

1. DI+ (DMI)
2. DI- (DMI)
3. ADX 14
4. BB Upper
5. BB Middle
6. BB Lower
7. SuperTrend Value
8. SuperTrend Direction

### Batch 4: Channels & Ichimoku (8 indicators)
**File:** `batch4_channels_ichimoku.pine`
**Columns:** 5 OHLCV + 8 indicators = 13 total

1. Keltner Channel Upper
2. Keltner Channel Middle
3. Keltner Channel Lower
4. Ichimoku Conversion Line
5. Ichimoku Base Line
6. Ichimoku Span A
7. Ichimoku Span B
8. Ichimoku Lagging Span

### Batch 5: CMF (1 indicator)
**File:** `batch5_cmf.pine`
**Columns:** 5 OHLCV + 1 indicator = 6 total

1. Chaikin Money Flow (20)

## Export Instructions

For **each batch**, perform these steps:

### 1. Load PineScript in TradingView

1. Open TradingView (https://www.tradingview.com)
2. Open Pine Editor (Alt+E or click "Pine Editor" at bottom)
3. Click "Open" → select the batch PineScript file
4. Click "Add to Chart"
5. Verify the indicator values table appears in top-right corner

### 2. Configure Chart Settings

1. **Instrument:** OANDA:EURUSD
2. **Timeframe:** 1 hour
3. **Date Range:** Load maximum available history
   - Scroll to earliest available data point
   - Note the start date
4. **Verify:** Check that indicator plots and table display correctly

### 3. Export Chart Data

1. Click the three dots menu (...) on the chart
2. Select "Export chart data..."
3. **CRITICAL:** Verify the export preview shows ALL expected columns:
   - 5 OHLCV columns (time, open, high, low, close)
   - All indicator columns from the batch
4. Click "Export"
5. Save as: `OANDA_EURUSD_1h_batchN.csv` (where N = batch number)

### 4. Verify Export

Open the CSV and confirm:
- First row contains column headers
- All expected indicator columns are present
- Data starts from earliest available date
- No missing or truncated columns

## Expected Output Files

After completing all 5 batches:
```
OANDA_EURUSD_1h_batch1.csv  (13 columns)
OANDA_EURUSD_1h_batch2.csv  (13 columns)
OANDA_EURUSD_1h_batch3.csv  (13 columns)
OANDA_EURUSD_1h_batch4.csv  (13 columns)
OANDA_EURUSD_1h_batch5.csv  (6 columns)
```

## Next Steps

Once all 5 files are exported:
1. Place files in `/Users/jbaird/Downloads/`
2. Run the merge script to combine into single dataset
3. Verify merged dataset integrity
4. Track with DVC

## Troubleshooting

### Issue: Export has fewer columns than expected
- **Cause:** TradingView hit column limit
- **Solution:** Contact support - this shouldn't happen with our batching

### Issue: Column names don't match indicator names
- **Cause:** TradingView uses plot names for headers
- **Solution:** Check the plot() calls in PineScript for actual names

### Issue: Different number of rows between batches
- **Cause:** Different indicators have different warmup periods
- **Solution:** Normal - merge script will handle alignment by timestamp

### Issue: VWAP shows NaN or missing data
- **Cause:** VWAP resets at session boundaries (daily)
- **Solution:** Normal behavior - will have gaps at session starts
