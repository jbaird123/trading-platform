# EMA Crossover - 20pip Stop Loss + 40pip Take Profit

Golden validation dataset for EMA crossover strategy with 20-pip stop-loss and 40-pip take-profit.

## Strategy Overview

**Entry Rules:**
- Long: Fast EMA (20) crosses above Slow EMA (50)
- Short: Fast EMA (20) crosses below Slow EMA (50)

**Exit Rules:**
- Signal-based: Opposite EMA crossover
- Stop-loss: Fixed 20 pips from entry price
- Take-profit: Fixed 40 pips from entry price

**Position Sizing:**
- Fixed: $10,000 per trade
- No pyramiding

## Risk Management

This variation validates the Risk & Exit Manager (REM) with both:
1. Stop-loss logic (20 pips)
2. Take-profit logic (40 pips)
3. Exit prioritization when multiple exits trigger

## TradingView Export Instructions

### Configuration
- **Symbol:** EURUSD
- **Timeframe:** 1 Hour
- **Date Range:**
  - Export Start: **2022-12-01** (1 month warmup required)
  - Validation Range: **2023-01-01 to 2024-12-31**

### Strategy Parameters
- Fast EMA Length: 20
- Slow EMA Length: 50
- Stop Loss: 20 pips
- Take Profit: 40 pips
- Initial Capital: $100,000
- Position Size: $10,000 per trade
- Commission: 0%

### Export Steps
1. Load `strategy.pine` into TradingView Pine Editor
2. Apply to EURUSD 1H chart
3. Set date range: 2022-12-01 to 2024-12-31
4. Verify strategy parameters match above
5. Export List of Trades as CSV
6. Save as: `data/dvc/golden/strategies/ema_crossover/20pip_stop_40pip_tp/trades.csv`

## Validation Range

- **Warmup Start:** 2022-12-01
- **Validation Start:** 2023-01-01
- **Validation End:** 2024-12-31

**IMPORTANT:** TradingView export must start at 2022-12-01 (exactly 1 month before validation start) to allow proper warmup for EMA indicators.

## Exit Prioritization

When multiple exits trigger on the same bar:
1. Stop-loss takes priority (if hit)
2. Take-profit second
3. Signal-based exit last

This matches the `exit_tie_break: "stop_then_tp"` configuration.

## Known Limitations

- **Same-bar stops/TPs:** Platform can detect intra-bar stop/TP hits, TradingView cannot in historical mode
- **Position sizing:** Minor PnL differences due to calculation methods
- Focus validation on trade execution (times and prices), not PnL amounts
