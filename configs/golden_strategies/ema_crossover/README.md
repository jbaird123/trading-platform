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

- **Validation Start Date**: January 1, 2023
- **Validation End Date**: December 31, 2024
- **Timeframe**: 1H (1 hour)
- **Symbol**: EURUSD (or EUR/USD depending on broker)

**⚠️ CRITICAL: Export Date Range Configuration**

When exporting trade data from TradingView, you MUST set the export start date **EARLIER** than the desired validation start date. This is because:

1. **Indicator Warmup Period**: Strategies need historical data to warm up indicators (EMAs, etc.) before the validation period begins
2. **TradingView Filter Behavior**: TradingView may filter out trades that occur near the start date even if they're technically within range
3. **Recommended Buffer**: Set export start date **at least 100 bars (for hourly data: ~5-7 days) before** the validation start date

**Example for this strategy:**
- Validation period: 2023-01-01 to 2024-12-31
- Export start date: 2022-12-01 (1 month before validation start)
- This ensures trades from early January 2023 are included in the export

The test suite will automatically filter trades to the validation range, but the raw export must include the warmup period.

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

- **Entry/Exit Times**: ±1 hour tolerance
- **Entry/Exit Prices**: ±0.00001 (0.1 pip for forex)
- **Trade PnL**: ±$5.00 per trade
- **Total PnL**: ±$10.00 cumulative
- **Trade Count**: Must match exactly

### Why These Tolerances?

- **Times (1 hour)**: When EMAs are extremely close (nearly identical), floating-point precision differences can cause crossovers to be detected on adjacent bars. This is acceptable as it represents minor calculation differences, not logic errors.
- **Prices (0.1 pip)**: Minor differences in EMA calculation precision with `next_bar_open` execution model
- **PnL ($5/trade)**: Timing differences of 1 hour can result in ~4-5 pip price differences, translating to $4-5 PnL difference on 10,000 unit positions
- **Total PnL ($10)**: Small rounding differences accumulate across 248 trades
- **Trade Count (exact)**: With extended warmup (100 bars before validation start), both systems should detect the same number of crossovers

## Regeneration Schedule

Regenerate this dataset when:

1. TradingView updates their indicator calculations
2. We update pandas-ta version
3. Data quality issues discovered
4. Strategy logic changes

**Last Generated**: 2025-10-11 (Pending first generation)

## Validation Test Location

See: `tests/validation/test_strategy_validation.py::test_ema_crossover`
