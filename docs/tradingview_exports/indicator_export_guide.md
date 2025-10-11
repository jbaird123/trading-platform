# TradingView Indicator Export Guide

**Purpose**: Instructions for exporting comprehensive indicator dataset

**Instrument**: EUR/USD
**Timeframe**: 1H
**Date Range**: 2023-01-01 to 2024-12-31

---

## Step 1: Open Chart in TradingView

1. Go to TradingView
2. Open EUR/USD chart
3. Set timeframe to 1H
4. Set date range: Jan 1, 2023 - Dec 31, 2024

---

## Step 2: Add Indicators Manually

**TradingView doesn't allow exporting custom indicator scripts with data.**

Instead, add each indicator individually using TradingView's built-in indicators:

### Moving Averages (Add to Main Chart)

1. **SMA 20**: Click Indicators → "Moving Average" → Set length=20, type=SMA
2. **SMA 50**: Add another MA → Set length=50, type=SMA
3. **EMA 20**: Add another MA → Set length=20, type=EMA
4. **EMA 50**: Add another MA → Set length=50, type=EMA
5. **WMA 20**: Add another MA → Set length=20, type=WMA

### Momentum Oscillators (Add as Separate Panes)

6. **RSI 14**: Click Indicators → "Relative Strength Index" → length=14
7. **MACD**: Click Indicators → "MACD" → fast=12, slow=26, signal=9
8. **Stochastic**: Click Indicators → "Stochastic" → K=14, D=3, smooth=3
9. **CCI 20**: Click Indicators → "Commodity Channel Index" → length=20
10. **ROC 12**: Click Indicators → "Rate of Change" → length=12

### Trend Indicators (Add to Main or Separate Panes)

11. **ADX 14**: Click Indicators → "Average Directional Index" → length=14
12. **ATR 14**: Click Indicators → "Average True Range" → length=14

### Volatility Indicators (Add to Main Chart)

13. **Bollinger Bands**: Click Indicators → "Bollinger Bands" → length=20, std=2.0

### Volume Indicators (Add as Separate Panes)

14. **OBV**: Click Indicators → "On Balance Volume"
15. **CMF 20**: Click Indicators → "Chaikin Money Flow" → length=20

### Other Indicators

16. **Parabolic SAR**: Click Indicators → "Parabolic SAR" → start=0.02, increment=0.02, max=0.2

### Advanced Indicators (Low Priority - Including for Completeness)

17. **Ichimoku Cloud**: Click Indicators → "Ichimoku Cloud" → Conversion=9, Base=26, Lagging Span 2=52
18. **SuperTrend**: Click Indicators → "SuperTrend" → ATR Period=7, Multiplier=3.0
19. **Keltner Channels**: Click Indicators → "Keltner Channels" → length=20, multiplier=2.0
20. **Choppiness Index**: Click Indicators → "Choppiness Index" → length=14

### Additional Useful Indicator

21. **VWAP**: Click Indicators → "Volume Weighted Average Price" (only if intraday data available)

---

## Step 3: Export Chart Data

1. Right-click on chart
2. Select "Export chart data..."
3. **IMPORTANT**: Make sure "Export visible indicators" is checked
4. Click "Export"
5. Save as: `eurusd_1h_full_2023-2024.csv`

---

## Step 4: Verify CSV Contents

Open the CSV and verify it contains these columns:

**OHLCV Columns**:
- time (or timestamp)
- open
- high
- low
- close
- volume

**Indicator Columns** (names may vary):
- SMA_20, SMA_50
- EMA_20, EMA_50
- WMA_20
- RSI_14
- MACD, MACD_signal, MACD_histogram
- Stochastic_K, Stochastic_D
- CCI_20
- ROC_12
- ADX_14
- ATR_14
- BB_upper, BB_basis (middle), BB_lower
- OBV
- CMF_20
- PSAR
- Ichimoku_Conversion, Ichimoku_Base, Ichimoku_LeadingSpanA, Ichimoku_LeadingSpanB, Ichimoku_Lagging
- SuperTrend, SuperTrend_Direction
- KC_upper, KC_middle, KC_lower
- ChopIndex_14
- VWAP (if available)

**Note**: TradingView may use slightly different column names.
Document the actual names in the metadata.json file.

---

## Step 5: Create metadata.json

Save this in the same directory as the CSV:

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
  "indicators": [
    {
      "name": "SMA_20",
      "tradingview_name": "Simple Moving Average",
      "params": {"length": 20}
    },
    {
      "name": "SMA_50",
      "tradingview_name": "Simple Moving Average",
      "params": {"length": 50}
    },
    {
      "name": "EMA_20",
      "tradingview_name": "Exponential Moving Average",
      "params": {"length": 20}
    },
    {
      "name": "EMA_50",
      "tradingview_name": "Exponential Moving Average",
      "params": {"length": 50}
    },
    {
      "name": "WMA_20",
      "tradingview_name": "Weighted Moving Average",
      "params": {"length": 20}
    },
    {
      "name": "RSI_14",
      "tradingview_name": "Relative Strength Index",
      "params": {"length": 14}
    },
    {
      "name": "MACD",
      "tradingview_name": "MACD",
      "params": {"fast": 12, "slow": 26, "signal": 9}
    },
    {
      "name": "Stochastic",
      "tradingview_name": "Stochastic",
      "params": {"k": 14, "d": 3, "smooth": 3}
    },
    {
      "name": "CCI_20",
      "tradingview_name": "Commodity Channel Index",
      "params": {"length": 20}
    },
    {
      "name": "ROC_12",
      "tradingview_name": "Rate of Change",
      "params": {"length": 12}
    },
    {
      "name": "ADX_14",
      "tradingview_name": "Average Directional Index",
      "params": {"length": 14}
    },
    {
      "name": "ATR_14",
      "tradingview_name": "Average True Range",
      "params": {"length": 14}
    },
    {
      "name": "BB",
      "tradingview_name": "Bollinger Bands",
      "params": {"length": 20, "std": 2.0}
    },
    {
      "name": "OBV",
      "tradingview_name": "On Balance Volume",
      "params": {}
    },
    {
      "name": "CMF_20",
      "tradingview_name": "Chaikin Money Flow",
      "params": {"length": 20}
    },
    {
      "name": "PSAR",
      "tradingview_name": "Parabolic SAR",
      "params": {"start": 0.02, "increment": 0.02, "max": 0.2}
    },
    {
      "name": "Ichimoku",
      "tradingview_name": "Ichimoku Cloud",
      "params": {"tenkan": 9, "kijun": 26, "senkou": 52}
    },
    {
      "name": "SuperTrend",
      "tradingview_name": "SuperTrend",
      "params": {"length": 7, "multiplier": 3.0}
    },
    {
      "name": "KC",
      "tradingview_name": "Keltner Channels",
      "params": {"length": 20, "multiplier": 2.0}
    },
    {
      "name": "CHOP",
      "tradingview_name": "Choppiness Index",
      "params": {"length": 14}
    },
    {
      "name": "VWAP",
      "tradingview_name": "Volume Weighted Average Price",
      "params": {}
    }
  ],
  "csv_column_mapping": {
    "note": "Fill in actual column names from TradingView export"
  },
  "notes": "Comprehensive indicator validation dataset"
}
```

---

## Step 6: Save Files

Save both files to:
```
data/dvc/golden/indicators/
├── eurusd_1h_full_2023-2024.csv
└── metadata.json
```

---

## Troubleshooting

**Issue**: Some indicators not exporting
- **Solution**: Make sure indicator is visible on chart
- **Solution**: Try exporting again with fewer indicators at once

**Issue**: Column names don't match expectations
- **Solution**: Document actual names in metadata.json
- **Solution**: We'll handle mapping in test code

**Issue**: Missing data points
- **Solution**: Check date range is set correctly
- **Solution**: Some indicators need warmup period (normal)

---

## Time Estimate

- Adding all indicators (21 total): 15-20 minutes
- Exporting data: 2-3 minutes
- Creating metadata: 5 minutes
- **Total**: ~25 minutes

## Summary

**Total Indicators to Export**: 21

**Categories**:
- Moving Averages: 5 (SMA 20, SMA 50, EMA 20, EMA 50, WMA 20)
- Momentum Oscillators: 5 (RSI, MACD, Stochastic, CCI, ROC)
- Trend Indicators: 4 (ADX, ATR, PSAR, SuperTrend)
- Volatility/Channels: 3 (Bollinger Bands, Keltner Channels, Ichimoku)
- Volume: 3 (OBV, CMF, VWAP)
- Market Condition: 1 (Choppiness Index)

This comprehensive dataset will allow validation of all major indicator categories!
