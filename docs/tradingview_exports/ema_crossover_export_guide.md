# TradingView EMA Crossover Strategy Export Guide

**Purpose**: Export EMA Crossover backtest data from TradingView

**Files Needed**:
- ✅ `configs/golden_strategies/ema_crossover/strategy.pine` (ready)

---

## Step 1: Copy PineScript

Open the file:
```
configs/golden_strategies/ema_crossover/strategy.pine
```

Copy the entire contents.

---

## Step 2: Load in TradingView

1. Go to TradingView
2. Open EUR/USD chart
3. Set timeframe to **1H**
4. Click "Pine Editor" at bottom of screen
5. Paste the PineScript code
6. Click "Add to Chart"

---

## Step 3: Configure Strategy Tester

1. Click on strategy name in chart legend
2. Click the gear icon ⚙️ (Settings)
3. Configure **Properties** tab:
   - **Initial Capital**: 100000
   - **Base Currency**: USD
   - **Order Size**: Choose "Cash (in account currency)"
   - **Order Size Value**: 10000
   - **Pyramiding**: 1
   - **Commission**: 0 (for baseline)
   - **Slippage**: 0 ticks

4. Configure **Inputs** tab:
   - **Fast EMA Length**: 20
   - **Slow EMA Length**: 50

5. Click "OK"

---

## Step 4: Set Date Range

1. Click on the chart date range selector
2. Set **Start Date**: January 1, 2023
3. Set **End Date**: December 31, 2024

---

## Step 5: Verify Strategy is Running

Check the Strategy Tester panel at bottom of screen. You should see:
- Net Profit
- Total Trades
- Win Rate
- Equity curve

**Take a screenshot** of this for reference.

---

## Step 6: Export Trade List

1. In Strategy Tester panel, click on **"List of Trades"** tab
2. Click the three dots menu (⋮) or export button
3. Select "Export trades list"
4. Save as: `trades.csv`

**Expected Columns**:
- Entry time
- Entry price
- Exit time
- Exit price
- Trade direction (Long/Short)
- Profit
- Cumulative profit
- Contracts (size)

---

## Step 7: Export OHLCV Data

1. Right-click on chart
2. Select "Export chart data..."
3. Ensure date range is 2023-2024
4. Click "Export"
5. Save as: `ohlcv.csv`

**Expected Columns**:
- time
- open
- high
- low
- close
- volume

---

## Step 8: Export Equity Curve (If Available)

**Note**: This may not be directly exportable from TradingView.

If not available:
- Document that we'll calculate it from trades in our tests
- Mark as "N/A - will calculate from trades"

---

## Step 9: Record Performance Metrics

From the Strategy Tester panel, record these values:

- **Total Closed Trades**: ___________
- **Net Profit**: ___________
- **Percent Profitable**: ___________
- **Profit Factor**: ___________
- **Max Drawdown**: ___________
- **Avg Trade**: ___________
- **Avg # Bars in Trade**: ___________

Save these in the metadata.json for comparison.

---

## Step 10: Create metadata.json

Create this file with the data from your export:

```json
{
  "dataset_type": "strategy",
  "strategy_name": "ema_crossover",
  "tradingview_version": "TradingView Pro 2025.10",
  "export_date": "2025-10-11",
  "date_range": {
    "start": "2023-01-01",
    "end": "2024-12-31"
  },
  "instrument": "EURUSD",
  "timeframe": "1H",
  "position_size": 10000.0,
  "commission": 0.0,
  "slippage": 0.0,
  "initial_capital": 100000.0,
  "strategy_parameters": {
    "ema_fast_length": 20,
    "ema_slow_length": 50
  },
  "performance_metrics": {
    "total_closed_trades": 0,
    "net_profit": 0.0,
    "percent_profitable": 0.0,
    "profit_factor": 0.0,
    "max_drawdown": 0.0,
    "avg_trade": 0.0,
    "avg_bars_in_trade": 0
  },
  "notes": "Baseline validation - no stops or commission"
}
```

**Fill in the actual values from Step 9!**

---

## Step 11: Organize Files

Create this structure:

```
data/dvc/golden/strategies/ema_crossover/
├── ohlcv.csv           (from Step 7)
├── trades.csv          (from Step 6)
├── metadata.json       (from Step 10)
└── screenshot.png      (from Step 5)
```

---

## Verification Checklist

Before leaving TradingView, verify:

- [ ] Strategy shows trades on chart
- [ ] Trade count > 0 (not empty)
- [ ] Equity curve is visible
- [ ] Screenshot saved
- [ ] trades.csv downloaded
- [ ] ohlcv.csv downloaded
- [ ] Performance metrics recorded
- [ ] metadata.json created with actual values

---

## Troubleshooting

**Issue**: No trades showing
- **Check**: Date range is set to 2023-2024
- **Check**: Strategy is "Add to Chart", not just saved
- **Check**: EUR/USD data is loading correctly

**Issue**: Can't export trade list
- **Solution**: Try clicking different areas in Strategy Tester
- **Solution**: Look for export icon (↓) or three-dot menu

**Issue**: Performance metrics differ from expectations
- **This is OK**: Document the actual values
- **Purpose**: We're validating our platform matches these

---

## Time Estimate

- Loading PineScript: 2 minutes
- Configuring strategy: 3 minutes
- Exporting trades: 2 minutes
- Exporting OHLCV: 2 minutes
- Creating metadata: 5 minutes
- **Total**: ~15 minutes

---

## Next Steps After Export

1. Move files to `data/dvc/golden/strategies/ema_crossover/`
2. Track with DVC: `dvc add data/dvc/golden/strategies/ema_crossover/`
3. Run validation tests
4. Compare our platform results with TradingView metrics
