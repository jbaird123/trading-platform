# TradingView Indicator Export Guide - UPDATED (Easy Method)

**Purpose**: Instructions for exporting comprehensive indicator dataset using a single PineScript

**Instrument**: EUR/USD
**Timeframe**: 1H
**Date Range**: 2023-01-01 to 2024-12-31

---

## Method: Use Single PineScript (MUCH EASIER!)

Instead of adding 21 indicators manually, use the comprehensive PineScript indicator we created.

---

## Step 1: Open TradingView Pine Editor

1. Go to TradingView
2. Open EUR/USD chart
3. Set timeframe to **1H**
4. Click "Pine Editor" at bottom of screen

---

## Step 2: Load the Comprehensive Indicator Script

1. Copy the entire contents of:
   ```
   configs/golden_strategies/indicators/comprehensive_indicators.pine
   ```

2. Paste into Pine Editor

3. Click **"Add to Chart"**

4. You should see:
   - A chart with multiple oscillators plotted
   - A table in top-right showing all 21 indicator values
   - All indicators now calculated on every bar

---

## Step 3: Set Date Range

1. Click on the chart date range selector
2. Set **Start Date**: January 1, 2023
3. Set **End Date**: December 31, 2024

---

## Step 4: Verify Indicators Are Calculating

Check the table in the top-right corner. You should see current values for:

**Moving Averages (5)**:
- SMA 20, SMA 50
- EMA 20, EMA 50
- WMA 20

**Momentum Oscillators (5)**:
- RSI 14
- MACD
- Stochastic K
- CCI 20
- ROC 12

**Trend Indicators (4)**:
- ADX 14
- ATR 14
- SuperTrend
- (Parabolic SAR calculated but not in table)

**Volatility/Channels (3)**:
- BB Upper, Middle, Lower
- KC Upper (Keltner Channels)
- Ichimoku Base

**Volume (3)**:
- OBV
- CMF 20
- VWAP (if on intraday timeframe)

**Market Condition (1)**:
- Choppiness Index

---

## Step 5: Export Chart Data

1. Right-click anywhere on the chart
2. Select **"Export chart data..."**
3. **CRITICAL**: Make sure "Export visible indicators" is checked
4. Click **"Export"**
5. Save as: `eurusd_1h_full_2023-2024.csv`

---

## Step 6: Verify CSV Contents

Open the CSV file and verify it contains:

**Basic Columns**:
- time (or timestamp)
- open, high, low, close, volume

**Indicator Columns** (names will vary, document actual names):

The export will include columns for all calculated indicators.
TradingView will automatically name them based on the script variables.

Expected column patterns:
- `SMA_20`, `SMA_50`
- `EMA_20`, `EMA_50`
- `WMA_20`
- `RSI_14`
- `MACD_line`, `MACD_signal`, `MACD_hist`
- `Stoch_K`, `Stoch_D`
- `CCI_20`
- `ROC_12`
- `ADX_14`
- `ATR_14`
- `BB_upper`, `BB_middle`, `BB_lower`
- `KC_upper`, `KC_middle`, `KC_lower`
- `Ichimoku_conversion`, `Ichimoku_base`, `Ichimoku_spanA`, etc.
- `SuperTrend`, `SuperTrend_direction`
- `OBV`
- `CMF_20`
- `VWAP`
- `PSAR`
- `Chop`

**IMPORTANT**: Document the actual column names in your metadata.json!

---

## Step 7: Create metadata.json

Create this file and fill in the actual column names from your export:

```json
{
  "dataset_type": "indicator",
  "tradingview_version": "TradingView Pro 2025.10",
  "export_date": "2025-10-11",
  "date_range": {
    "start": "2023-01-01",
    "end": "2024-12-31"
  },
  "instrument": "EURUSD",
  "timeframe": "1H",
  "pinescript_source": "configs/golden_strategies/indicators/comprehensive_indicators.pine",
  "indicators": [
    {
      "name": "SMA_20",
      "tradingview_column": "SMA_20",
      "params": {"length": 20}
    },
    {
      "name": "SMA_50",
      "tradingview_column": "SMA_50",
      "params": {"length": 50}
    },
    {
      "name": "EMA_20",
      "tradingview_column": "EMA_20",
      "params": {"length": 20}
    },
    {
      "name": "EMA_50",
      "tradingview_column": "EMA_50",
      "params": {"length": 50}
    },
    {
      "name": "WMA_20",
      "tradingview_column": "WMA_20",
      "params": {"length": 20}
    },
    {
      "name": "RSI_14",
      "tradingview_column": "RSI_14",
      "params": {"length": 14}
    },
    {
      "name": "MACD",
      "tradingview_column": "MACD_line",
      "params": {"fast": 12, "slow": 26, "signal": 9},
      "additional_columns": ["MACD_signal", "MACD_hist"]
    },
    {
      "name": "Stochastic",
      "tradingview_column": "Stoch_K",
      "params": {"k": 14, "d": 3},
      "additional_columns": ["Stoch_D"]
    },
    {
      "name": "CCI_20",
      "tradingview_column": "CCI_20",
      "params": {"length": 20}
    },
    {
      "name": "ROC_12",
      "tradingview_column": "ROC_12",
      "params": {"length": 12}
    },
    {
      "name": "ADX_14",
      "tradingview_column": "ADX_14",
      "params": {"length": 14}
    },
    {
      "name": "ATR_14",
      "tradingview_column": "ATR_14",
      "params": {"length": 14}
    },
    {
      "name": "BB",
      "tradingview_column": "BB_middle",
      "params": {"length": 20, "std": 2.0},
      "additional_columns": ["BB_upper", "BB_lower"]
    },
    {
      "name": "KC",
      "tradingview_column": "KC_middle",
      "params": {"length": 20, "multiplier": 2.0},
      "additional_columns": ["KC_upper", "KC_lower"]
    },
    {
      "name": "Ichimoku",
      "tradingview_column": "Ichimoku_conversion",
      "params": {"tenkan": 9, "kijun": 26, "senkou": 52},
      "additional_columns": ["Ichimoku_base", "Ichimoku_spanA",
                             "Ichimoku_spanB", "Ichimoku_lagging"]
    },
    {
      "name": "SuperTrend",
      "tradingview_column": "SuperTrend",
      "params": {"length": 7, "multiplier": 3.0},
      "additional_columns": ["SuperTrend_direction"]
    },
    {
      "name": "OBV",
      "tradingview_column": "OBV",
      "params": {}
    },
    {
      "name": "CMF_20",
      "tradingview_column": "CMF_20",
      "params": {"length": 20}
    },
    {
      "name": "VWAP",
      "tradingview_column": "VWAP",
      "params": {}
    },
    {
      "name": "PSAR",
      "tradingview_column": "PSAR",
      "params": {"start": 0.02, "increment": 0.02, "max": 0.2}
    },
    {
      "name": "CHOP",
      "tradingview_column": "Chop",
      "params": {"length": 14}
    }
  ],
  "notes": "All indicators calculated via single PineScript for consistency"
}
```

**IMPORTANT**: Update the `tradingview_column` values to match the actual column names in your exported CSV!

---

## Step 8: Save Files

Save both files to:
```
data/dvc/golden/indicators/
├── eurusd_1h_full_2023-2024.csv
└── metadata.json
```

---

## Step 9: Take Screenshot (Optional but Recommended)

Take a screenshot of:
1. The chart with the indicator loaded
2. The values table showing current indicator values
3. Save as: `data/dvc/golden/indicators/screenshot.png`

This serves as visual proof of the setup.

---

## Verification Checklist

- [ ] PineScript loaded and showing in chart
- [ ] Values table visible in top-right
- [ ] Date range set to 2023-2024
- [ ] CSV exported successfully
- [ ] CSV contains OHLCV columns
- [ ] CSV contains indicator columns (many columns!)
- [ ] metadata.json created
- [ ] Column names in metadata match CSV
- [ ] Files saved to correct directory

---

## Troubleshooting

**Issue**: PineScript won't compile
- **Solution**: Make sure you copied the entire file
- **Solution**: Check for any copy/paste errors
- **Solution**: TradingView Pine version must be v5

**Issue**: Some indicators showing N/A or blank
- **Solution**: This is normal during warmup period
- **Solution**: Export will still include all data after warmup

**Issue**: CSV doesn't include indicator columns
- **Solution**: Make sure "Export visible indicators" was checked
- **Solution**: Try exporting again

**Issue**: Too many indicators, chart is slow
- **Solution**: This is normal with 21 indicators
- **Solution**: Just wait for export to complete

**Issue**: Column names don't match metadata
- **Solution**: Update metadata.json with actual names from CSV
- **Solution**: This is expected - just document the mapping

---

## Time Estimate

- Loading PineScript: 2 minutes
- Verifying calculations: 2 minutes
- Exporting data: 2-3 minutes
- Creating metadata: 10 minutes (mapping column names)
- **Total**: ~15-20 minutes

**Much faster than adding 21 indicators manually!**

---

## Advantages of This Method

✅ **Consistency**: All indicators calculated in one script
✅ **Reusable**: Save the script for future exports
✅ **Verifiable**: Table shows current values
✅ **Faster**: One script vs. 21 manual additions
✅ **Documented**: PineScript is version controlled
✅ **Reproducible**: Anyone can load the same script

---

## Next Steps After Export

1. Move files to `data/dvc/golden/indicators/`
2. Track with DVC: `dvc add data/dvc/golden/indicators/`
3. Create test file to validate indicators
4. Run tests and adjust tolerances as needed
