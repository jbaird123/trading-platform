# EMA Crossover with 20-Pip Stop Loss

## Purpose

This variation validates our Risk & Exit Manager (REM) stop-loss logic
against TradingView. It uses the same EMA 20/50 crossover signals as
the baseline but adds a **fixed 20-pip stop loss** on all trades.

## Strategy Details

**Entry Logic:**
- **Long:** EMA(20) crosses above EMA(50)
- **Short:** EMA(20) crosses below EMA(50)

**Exit Logic:**
- **Signal Exit:** Opposite crossover (same as baseline)
- **Stop Loss:** Fixed 20 pips from entry price
  - Long stop: Entry price - 0.0020 (20 pips)
  - Short stop: Entry price + 0.0020 (20 pips)

**Position Sizing:**
- Fixed $10,000 per trade

**Costs:**
- No spread, commission, or slippage (for clean validation)

## Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Fast EMA | 20 | Same as baseline |
| Slow EMA | 50 | Same as baseline |
| Stop Loss | 20 pips | NEW - Fixed stop |
| Timeframe | 1 Hour | EURUSD hourly bars |
| Initial Capital | $100,000 | Match TradingView |
| Position Size | $10,000 | Fixed cash amount |

## TradingView Export Instructions

### 1. Setup Strategy

1. Open TradingView chart for **OANDA:EURUSD**
2. Set timeframe to **1 Hour**
3. Open Pine Editor and paste code from `strategy.pine`
4. Click "Add to Chart"

### 2. Configure Strategy Settings

**⚠️ CRITICAL SETTINGS:**

Click the strategy gear icon and set:

**Properties Tab:**
- Initial Capital: `100000`
- Base Currency: `USD`
- Order Size: `10000` (Cash)
- Commission: `0%`
- Verify "On every tick" is OFF

**Inputs Tab:**
- Fast EMA Length: `20`
- Slow EMA Length: `50`
- Stop Loss (pips): `20`

### 3. Set Date Range

**⚠️ CRITICAL: Export with warmup period**

- **Validation Range:** 2023-01-01 to 2024-12-31
- **Export Start Date:** 2022-12-01 (REQUIRED - exactly 1 month before)

Set chart to show from **Dec 1, 2022** to **Dec 31, 2024**

**Note**: The old "100 bars" guidance (~5 days) was insufficient. Golden validation testing proved that exactly 1 month of warmup data (~720 bars for hourly charts) is required for perfect matching with TradingView. Using any less will result in discrepancies in early trades.

### 4. Export Data

**Export OHLCV Data:**
1. Right-click chart → "Export chart data"
2. Save as: `ohlcv.csv`
3. Place in: `data/dvc/golden/strategies/ema_crossover/20pip_stop/`

**Export Trade List:**
1. Open Strategy Tester (bottom panel)
2. Click "List of Trades" tab
3. Click download icon (top-right)
4. Save as: `trades.csv`
5. Place in: `data/dvc/golden/strategies/ema_crossover/20pip_stop/`

### 5. Create Metadata

Create `metadata.json` in the same directory:

```json
{
  "dataset_type": "strategy",
  "strategy_name": "ema_crossover_20pip_stop",
  "tradingview_version": "TradingView Pro 2025.X",
  "export_date": "YYYY-MM-DD",
  "date_range": {
    "start": "2023-01-01",
    "end": "2024-12-31"
  },
  "warmup_range": {
    "start": "2022-12-01",
    "end": "2022-12-31"
  },
  "instrument": "EURUSD",
  "timeframe": "1H",
  "initial_capital": 100000.0,
  "position_size": 10000.0,
  "commission": 0.0,
  "stop_loss_pips": 20,
  "parameters": {
    "ema_fast_length": 20,
    "ema_slow_length": 50
  }
}
```

## Expected Differences from Baseline

This variation should produce:
- **Fewer trades** - Some will be stopped out before signal exit
- **More losing trades** - Stops will cut losses short
- **Different equity curve** - Stop losses change PnL profile
- **Lower max drawdown** - Risk is limited by stops

## Validation Focus

This test specifically validates:

1. **Stop Loss Execution** - Do stops hit at correct price?
2. **Intra-Bar Fill Logic** - How do we handle stops within a bar?
3. **Exit Precedence** - Stop vs signal exit priority
4. **PnL Calculation** - Correct stop-out PnL calculation

## Last Regenerated

- **Date:** [To be filled after export]
- **By:** [Your name]
- **TradingView Version:** [Version used]
- **Trade Count:** [Number from TV]
- **Final Equity:** [Final $ from TV]
