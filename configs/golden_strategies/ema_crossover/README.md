# EMA Crossover - Golden Validation Strategy

## Overview

This is a simple EMA (20/50) crossover strategy designed for validation
testing against TradingView. The strategy intentionally has **no
stop-loss or take-profit** to ensure we're testing pure signal
generation logic.

## Strategy Details

- **Entry Long**: EMA(20) crosses above EMA(50)
- **Exit Long**: EMA(20) crosses below EMA(50)
- **Entry Short**: EMA(20) crosses below EMA(50)
- **Exit Short**: EMA(20) crosses above EMA(50)

## Parameters

- **Fast EMA**: 20 periods
- **Slow EMA**: 50 periods
- **Initial Capital**: $100,000
- **Position Size**: $10,000 (fixed)
- **Commission**: $0 (disabled for baseline validation)

## TradingView Setup Instructions

### 1. Load the Strategy

1. Open TradingView
2. Navigate to Pine Editor
3. Copy contents of `strategy.pine`
4. Click "Add to Chart"

### 2. Configure Settings

Go to Strategy Settings:

- **Initial Capital**: 100000
- **Base Currency**: USD
- **Order Size**: Cash, 10000
- **Commission**: 0.0
- **Slippage**: 0 ticks
- **Verify Position Sizing**: Should show "Order size: $10000"

### 3. Set Time Range

- **Start Date**: January 1, 2023
- **End Date**: December 31, 2024
- **Timeframe**: 1H (1 hour)
- **Symbol**: EURUSD (or EUR/USD depending on broker)

### 4. Export Data

#### Export Trades

1. Go to Strategy Tester tab
2. Click "List of Trades"
3. Export to CSV
4. Save as: `data/dvc/golden/strategies/ema_crossover/trades.csv`

**Required columns:**
- Entry Time
- Entry Price
- Exit Time
- Exit Price
- Side (Long/Short)
- Profit
- Cumulative Profit
- Size (contracts/shares)

#### Export OHLCV Data

1. Right-click on chart
2. Select "Export Chart Data"
3. Save as: `data/dvc/golden/strategies/ema_crossover/ohlcv.csv`

#### Export Equity Curve (if available)

1. In Strategy Tester, look for equity curve export option
2. Save as: `data/dvc/golden/strategies/ema_crossover/equity_curve.csv`

### 5. Record Metadata

Create `data/dvc/golden/strategies/ema_crossover/metadata.json`:

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
  "initial_capital": 100000.0,
  "notes": "Baseline validation - no stops or commission"
}
```

### 6. Track with DVC

```bash
dvc add data/dvc/golden/strategies/ema_crossover/
dvc push
git add data/dvc/golden/strategies/ema_crossover.dvc
git commit -m "data: Add EMA crossover golden validation dataset"
```

## Known Differences & Tolerances

### Acceptable Variances

- **Entry/Exit Times**: Must match exactly (0 minutes tolerance)
- **Entry/Exit Prices**: ±0.0001 (1 pip for forex)
- **Trade PnL**: ±$0.50 per trade
- **Total PnL**: ±$1.00 cumulative
- **Trade Count**: Must match exactly

### Why These Tolerances?

- **Prices**: Minor differences in how libraries handle OHLC data
- **PnL**: Small rounding differences accumulate across trades
- **Times**: Should be exact since we're using same data

## Regeneration Schedule

Regenerate this dataset when:

1. TradingView updates their indicator calculations
2. We update pandas-ta version
3. Data quality issues discovered
4. Strategy logic changes

**Last Generated**: 2025-10-11 (Pending first generation)

## Validation Test Location

See: `tests/validation/test_strategy_validation.py::test_ema_crossover`
