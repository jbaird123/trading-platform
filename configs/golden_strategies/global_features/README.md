# Global Feature Pine Scripts

This folder stores the TradingView Pine scripts used to generate the golden
feature exports that back the indicator and warmup regression tests.

## How to use

1. Open the relevant `.pine` file in TradingView’s Pine Editor.
2. Add the script to any chart (the script enforces its own timeframe).
3. Use **Export chart data…** or copy from the Data Window to capture the
   plotted series.
4. Save the CSVs under `data/dvc/golden/features/raw/…` (or your chosen staging
   folder) before running the Python exporter that builds the aligned parquet
   caches.

The scripts in this directory are:

| File                           | Timeframe | Notes                          |
|--------------------------------|-----------|--------------------------------|
| `global_features_1h.pine`      | 1 hour    | Full H1 feature set (EMA50, ADX, RSI, MACD, ATR, BB width, volume SMA, OBV). |
| `global_features_4h.pine`      | 4 hours   | H4 EMA50, RSI14, ATR14.        |
| `global_features_1d.pine`      | 1 day     | D1 EMA24, ATR14, volume SMA20. |

Keep this README updated whenever we add/retire Pine scripts so the golden data
remains reproducible.
