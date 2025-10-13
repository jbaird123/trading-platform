# TradingView Strategy Data Export Guide

## Overview

This guide will walk you through exporting the EMA Crossover strategy data from TradingView to validate our platform's backtesting against TradingView's results.

**Goal:** Export trades, OHLCV data, and metadata so we can validate that our platform produces identical results.

---

## Prerequisites

- [ ] TradingView account (Pro recommended for data export features)
- [ ] Access to EURUSD 1-hour data
- [ ] PineScript file ready: `configs/golden_strategies/ema_crossover/strategy.pine`

---

## Step-by-Step Process

### Step 1: Open TradingView and Load Strategy

1. Go to [TradingView](https://www.tradingview.com/)
2. Open a chart
3. Click the **Pine Editor** button at the bottom
4. Copy the entire contents of: `configs/golden_strategies/ema_crossover/strategy.pine`
5. Paste into the Pine Editor
6. Click **"Add to Chart"** button

### Step 2: Configure Chart Settings

#### Set Symbol and Timeframe
1. In the symbol search box, type: **EURUSD** (or **EUR/USD**)
   - Use OANDA:EURUSD if available (recommended for consistency)
2. Set timeframe: **1H** (1 hour)
3. Set date range:
   - Click on the calendar icon
   - **Start Date**: January 1, 2023
   - **End Date**: December 31, 2024

### Step 3: Configure Strategy Settings

1. Click the **gear icon** on the strategy name in the chart
2. Go to the **Properties** tab:
   - **Initial Capital**: 100000
   - **Base Currency**: USD
   - **Order Size**: Cash, value: 10000
   - **Commission**: 0.0 (zero)
   - **Slippage**: 0 ticks
   - **Pyramiding**: 1 (default)
   - **Verify on Chart**: You should see "$10000" per position

3. Go to the **Inputs** tab:
   - **Fast EMA Length**: 20
   - **Slow EMA Length**: 50

4. Click **OK**

### Step 4: Verify Strategy is Running

1. Look at the **Strategy Tester** tab at the bottom
2. You should see:
   - Total trades count
   - Net profit
   - Percent profitable
   - Equity curve chart

**Take a screenshot** of the Strategy Tester results for reference!

### Step 5: Export Trades Data

1. In the Strategy Tester tab, click **"List of Trades"**
2. You should see a table with all trades
3. Look for an **export** or **download** icon (usually a down arrow or "..." menu)
4. Export to CSV
5. Save the file locally (anywhere on your computer for now)

**Expected columns in trades.csv:**
- Type (Entry/Exit)
- Signal (Long/Short)
- Date/Time
- Price
- Contracts
- Profit/Loss
- Cumulative Profit
- Balance
- Commission
- Drawdown

### Step 6: Export OHLCV Data

1. Right-click anywhere on the chart
2. Select **"Export chart data..."**
3. Make sure the date range matches (2023-01-01 to 2024-12-31)
4. Save as CSV
5. Save the file locally

**Expected columns in ohlcv.csv:**
- time (or Date)
- open
- high
- low
- close
- volume

### Step 7: Export Equity Curve (Optional)

Some TradingView versions allow equity curve export:

1. In Strategy Tester, look for an equity curve chart
2. Try right-clicking on it → Export data
3. If available, save as CSV
4. If not available, we can calculate it from trades

### Step 8: Record Metadata

Before leaving TradingView, record these details:

**Write down or screenshot:**
- TradingView version (e.g., "TradingView Pro 2025.10")
- Exact symbol used (e.g., "OANDA:EURUSD")
- Total number of trades shown
- Final equity/balance
- Net profit
- Today's date (export date)

---

## Step 9: Place Files in Correct Location

Once you have the exported files, move them to:

```bash
# Navigate to the project directory
cd /Users/jbaird/Documents/other/trading-platform

# Create the directory if it doesn't exist (it should already exist)
mkdir -p data/dvc/golden/strategies/ema_crossover

# Move your downloaded files
# (Replace ~/Downloads with wherever your browser saved them)
mv ~/Downloads/trades.csv data/dvc/golden/strategies/ema_crossover/
mv ~/Downloads/ohlcv.csv data/dvc/golden/strategies/ema_crossover/
# If you have equity curve:
mv ~/Downloads/equity_curve.csv data/dvc/golden/strategies/ema_crossover/  # optional
```

---

## Step 10: Create Metadata File

Create: `data/dvc/golden/strategies/ema_crossover/metadata.json`

Use this template (update with YOUR actual values):

```json
{
  "dataset_type": "strategy",
  "strategy_name": "ema_crossover",
  "tradingview_version": "TradingView Pro 2025.10",
  "export_date": "2025-10-12",
  "date_range": {
    "start": "2023-01-01",
    "end": "2024-12-31"
  },
  "instrument": "EURUSD",
  "timeframe": "1H",
  "position_size": 10000.0,
  "commission": 0.0,
  "initial_capital": 100000.0,
  "total_trades": 123,
  "net_profit": 1234.56,
  "notes": "Baseline validation - no stops or commission"
}
```

**Important:** Replace these values with actual data from TradingView:
- `tradingview_version` - your TradingView version
- `export_date` - today's date (2025-10-12)
- `total_trades` - actual trade count from Strategy Tester
- `net_profit` - actual net profit from Strategy Tester

---

## Step 11: Track with DVC and Push

Once all files are in place:

```bash
# Make sure you're in the project root
cd /Users/jbaird/Documents/other/trading-platform

# Check what files you have
ls -la data/dvc/golden/strategies/ema_crossover/

# Should see:
# - trades.csv
# - ohlcv.csv
# - metadata.json
# - (optionally) equity_curve.csv

# Track with DVC
dvc add data/dvc/golden/strategies/ema_crossover/

# Push to S3
dvc push

# Commit the DVC pointer file
git add data/dvc/golden/strategies/ema_crossover.dvc
git add data/dvc/golden/strategies/ema_crossover/.gitignore
git commit -m "data: Add EMA crossover golden validation dataset"
```

---

## Step 12: Run Validation Tests

```bash
# Run the validation test
poetry run pytest tests/validation/test_strategy_validation.py::test_ema_crossover_trade_count_matches_tradingview -v

# Or run all strategy validation tests
poetry run pytest tests/validation/test_strategy_validation.py -v

# Or run with validation marker
poetry run pytest -m validation
```

---

## Troubleshooting

### Issue: Can't find "Export chart data"
**Solution:** Try:
- Right-click directly on a candle
- Look in the chart's "..." menu (top right)
- Check if your TradingView plan supports data export

### Issue: Trades CSV has different columns
**Solution:** That's okay! We'll adapt our test code to handle TradingView's actual format.

### Issue: Can't export equity curve
**Solution:** That's fine - we can calculate it from the trades data. Skip that file.

### Issue: Date range doesn't match exactly
**Solution:** Make sure you're using the date range selector in TradingView's toolbar. The strategy should only show trades within 2023-2024.

### Issue: Trade counts seem wrong
**Solution:**
- Make sure commission is set to 0.0
- Check that position size is exactly $10,000
- Verify EMAs are using length 20 and 50
- Check that you're using 1H timeframe

---

## What Happens Next?

Once the data is exported and tracked with DVC:

1. **I'll update the test code** to load your actual TradingView data
2. **We'll run the validation tests** to compare our platform vs TradingView
3. **We'll tune tolerances** if there are minor differences
4. **Tests should pass** confirming our platform matches TradingView!

Then we can move on to more complex strategies (BB mean reversion, multi-indicator, etc.)

---

## Questions?

If you run into any issues during the export:
1. Take screenshots of what you're seeing
2. Note any error messages
3. Share the files you were able to export
4. I'll help adapt the tests to work with whatever format TradingView gives us

---

## Quick Reference

**Files to export:**
- ✅ `trades.csv` - Required
- ✅ `ohlcv.csv` - Required
- ✅ `metadata.json` - Required (you create this)
- ⚪ `equity_curve.csv` - Optional (can be calculated)

**Settings to verify:**
- Symbol: EURUSD (OANDA:EURUSD)
- Timeframe: 1H
- Date Range: 2023-01-01 to 2024-12-31
- Initial Capital: $100,000
- Position Size: $10,000
- Commission: 0.0
- EMA Fast: 20
- EMA Slow: 50

**Where files go:**
```
data/dvc/golden/strategies/ema_crossover/
├── trades.csv
├── ohlcv.csv
├── metadata.json
└── equity_curve.csv (optional)
```
