# TradingView Data Collection Plan

**Purpose**: Comprehensive list of all data to collect from TradingView in one
session for golden validation testing.

**Date**: 2025-10-11

---

## Part 1: Indicator Validation Data

### 1.1 Current Coverage (Already Testing) ✅

These indicators are already validated with existing sample data:

| Indicator | Parameters | TradingView Name | Status |
|-----------|-----------|------------------|---------|
| EMA | length: 20 | EMA_20 | ✅ Testing |
| EMA | length: 50 | EMA_50 | ✅ Testing |
| RSI | length: 14 | RSI_14 | ✅ Testing |
| ADX | length: 14 | ADX_14_14 | ✅ Testing |
| ATR | length: 14 | ATR_14_RMA | ✅ Testing |
| BB Upper | length: 20, std: 2.0 | BB_Upper | ✅ Testing |
| BB Middle | length: 20, std: 2.0 | BB_Basis | ✅ Testing |
| BB Lower | length: 20, std: 2.0 | BB_Lower | ✅ Testing |

### 1.2 Priority Additions (Commonly Used)

These are in our registry and commonly used in strategies:

| Indicator | Parameters | TradingView Equivalent | Priority |
|-----------|-----------|----------------------|----------|
| **SMA** | length: 20 | SMA(20) | HIGH |
| **SMA** | length: 50 | SMA(50) | HIGH |
| **MACD** | fast: 12, slow: 26, signal: 9 | MACD(12,26,9) | HIGH |
| **Stochastic** | k: 14, d: 3 | Stochastic(14,3,3) | HIGH |
| **CCI** | length: 20 | CCI(20) | MEDIUM |
| **WMA** | length: 20 | WMA(20) | MEDIUM |
| **ROC** | length: 12 | ROC(12) | MEDIUM |
| **PSAR** | step: 0.02, max: 0.2 | Parabolic SAR | LOW |

### 1.3 Volume Indicators

| Indicator | Parameters | TradingView Equivalent | Priority |
|-----------|-----------|----------------------|----------|
| **OBV** | none | On Balance Volume | MEDIUM |
| **CMF** | length: 20 | Chaikin Money Flow(20) | MEDIUM |
| **VWAP** | none | VWAP | LOW |

### 1.4 Advanced Indicators (Lower Priority)

| Indicator | Parameters | TradingView Equivalent | Priority |
|-----------|-----------|----------------------|----------|
| Ichimoku | tenkan:9, kijun:26, senkou:52 | Ichimoku Cloud | LOW |
| SuperTrend | length:7, mult:3.0 | SuperTrend(7,3.0) | LOW |
| Keltner Channels | length:20, mult:2.0 | KC(20,2.0) | LOW |
| Choppiness | length:14 | Choppiness Index(14) | LOW |

### 1.5 Custom/Platform-Specific (Skip for Now)

These are custom implementations - not validating against TradingView:
- EMA Slope
- BBWidth (derived from BB)
- HHV/LLV (simple rolling max/min)
- Swing High/Low (custom logic)
- Donchian Channels (custom)
- Candlestick patterns (pandas-ta has these)

---

## Part 2: Strategy Validation Data

### 2.1 Recommended Strategy Portfolio

Based on your existing strategies, here are the best candidates for
golden validation:

#### Strategy 1: EMA Crossover (PRIORITY 1) ✅

**Status**: PineScript ready, YAML ready

**Why**: Simplest, baseline validation, already implemented

**Configuration**:
- Instrument: EUR/USD
- Timeframe: 1H
- Date Range: 2023-01-01 to 2024-12-31
- Parameters:
  - Fast EMA: 20
  - Slow EMA: 50
- Position Size: $10,000 fixed
- Initial Capital: $100,000
- Commission: $0
- Risk: No stops (pure signal validation)

**What to Export**:
- ✅ PineScript: Already created
- ✅ YAML: Already created
- 🔲 trades.csv (from TradingView)
- 🔲 ohlcv.csv (from TradingView)
- 🔲 equity_curve.csv (if available)
- 🔲 metadata.json (create manually)

---

#### Strategy 2: BB Mean Reversion (PRIORITY 2)

**Why**: Tests more complex indicator (BB), different signal logic

**Proposed Configuration**:
- Instrument: USD/JPY
- Timeframe: 5min (or simplify to 1H for consistency)
- Date Range: 2023-01-01 to 2024-12-31
- Parameters:
  - BB Length: 20
  - BB Std Dev: 2.0
- Entry:
  - Long: Close < BB Lower
  - Short: Close > BB Upper
- Exit:
  - Long: Close > BB Middle
  - Short: Close < BB Middle
- Position Size: $10,000 fixed
- Initial Capital: $100,000
- Commission: $0
- Risk: No stops (pure signal validation)

**What to Create**:
- 🔲 PineScript version
- 🔲 Simplified YAML (signal-only)
- 🔲 REM YAML (no exits)
- 🔲 Run config YAML

**What to Export**:
- 🔲 trades.csv
- 🔲 ohlcv.csv
- 🔲 metadata.json

---

#### Strategy 3: RSI + ADX Multi-Indicator (PRIORITY 3)

**Why**: Tests multiple indicator combination, more complex logic

**Proposed Configuration**:
- Instrument: EUR/USD
- Timeframe: 1H
- Date Range: 2023-01-01 to 2024-12-31
- Parameters:
  - RSI Length: 14
  - ADX Length: 14
  - EMA Fast: 20
  - EMA Slow: 50
- Entry:
  - Long: EMA_20 > EMA_50 AND RSI < 30 AND ADX > 25
  - Short: EMA_20 < EMA_50 AND RSI > 70 AND ADX > 25
- Exit:
  - Long: RSI > 70 OR EMA_20 < EMA_50
  - Short: RSI < 30 OR EMA_20 > EMA_50
- Position Size: $10,000 fixed
- Initial Capital: $100,000
- Commission: $0
- Risk: No stops

**What to Create**:
- 🔲 PineScript version
- 🔲 YAML version
- 🔲 REM YAML
- 🔲 Run config YAML

**What to Export**:
- 🔲 trades.csv
- 🔲 ohlcv.csv
- 🔲 metadata.json

---

#### Strategy 4: MACD Crossover (OPTIONAL - PRIORITY 4)

**Why**: Tests MACD indicator, another common momentum strategy

**Proposed Configuration**:
- Instrument: EUR/USD
- Timeframe: 4H
- Date Range: 2023-01-01 to 2024-12-31
- Parameters:
  - MACD Fast: 12
  - MACD Slow: 26
  - MACD Signal: 9
- Entry:
  - Long: MACD crosses above Signal
  - Short: MACD crosses below Signal
- Exit:
  - Long: MACD crosses below Signal
  - Short: MACD crosses above Signal
- Position Size: $10,000 fixed
- Initial Capital: $100,000
- Commission: $0

**What to Create**:
- 🔲 PineScript version
- 🔲 YAML version
- 🔲 REM YAML
- 🔲 Run config YAML

**What to Export**:
- 🔲 trades.csv
- 🔲 ohlcv.csv
- 🔲 metadata.json

---

### 2.2 Why NOT Validate These Strategies

**Swing Point Strategies** (swing_high_short, swing_low_long):
- Use custom swing point detection
- No direct TradingView equivalent
- Would require custom PineScript that may not match our logic

**Institutional Order Block**:
- Custom/proprietary logic
- Not standard TradingView patterns

---

## Part 3: Complete TradingView Export Checklist

### Session 1: Indicator Validation Export

**Instrument**: EUR/USD
**Timeframe**: 1H
**Date Range**: 2023-01-01 to 2024-12-31

**Setup TradingView Chart**:

1. Open EUR/USD 1H chart
2. Set date range: Jan 1, 2023 - Dec 31, 2024
3. Add ALL indicators from Priority Additions (Section 1.2):

```pinescript
// Add these indicators to chart
indicator("Golden Validation Indicators", overlay=false)

// Moving Averages (overlay=true)
plot(ta.sma(close, 20), "SMA 20", color=color.blue)
plot(ta.sma(close, 50), "SMA 50", color=color.red)
plot(ta.ema(close, 20), "EMA 20", color=color.green)
plot(ta.ema(close, 50), "EMA 50", color=color.orange)
plot(ta.wma(close, 20), "WMA 20", color=color.purple)

// Oscillators (separate pane)
plot(ta.rsi(close, 14), "RSI 14", color=color.blue)
[macdLine, signalLine, histLine] = ta.macd(close, 12, 26, 9)
plot(macdLine, "MACD", color=color.blue)
plot(signalLine, "Signal", color=color.orange)
plot(histLine, "Histogram", color=color.gray)

[k, d] = ta.stoch(close, high, low, 14)
plot(k, "Stochastic K", color=color.blue)
plot(d, "Stochastic D", color=color.orange)

plot(ta.cci(close, 20), "CCI 20", color=color.purple)
plot(ta.roc(close, 12), "ROC 12", color=color.yellow)
plot(ta.adx(14), "ADX 14", color=color.red)
plot(ta.atr(14), "ATR 14", color=color.green)

// Bollinger Bands
[middle, upper, lower] = ta.bb(close, 20, 2.0)
plot(upper, "BB Upper", color=color.blue)
plot(middle, "BB Middle", color=color.orange)
plot(lower, "BB Lower", color=color.blue)

// Volume
plot(ta.obv, "OBV", color=color.purple)
plot(ta.cmf(20), "CMF 20", color=color.green)

// Parabolic SAR
plot(ta.sar(0.02, 0.02, 0.2), "PSAR", color=color.red)
```

4. Export chart data to CSV
5. Save as: `data/dvc/golden/indicators/eurusd_1h_full_2023-2024.csv`
6. Create metadata.json:

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
    "SMA(20)", "SMA(50)", "EMA(20)", "EMA(50)", "WMA(20)",
    "RSI(14)", "MACD(12,26,9)", "Stochastic(14,3)", "CCI(20)",
    "ROC(12)", "ADX(14)", "ATR(14)", "BB(20,2.0)", "OBV",
    "CMF(20)", "PSAR(0.02,0.2)"
  ],
  "notes": "Comprehensive indicator validation dataset"
}
```

### Session 2: Strategy 1 - EMA Crossover

**Files Ready**: ✅
**PineScript**: `configs/golden_strategies/ema_crossover/strategy.pine`

1. Open EUR/USD 1H chart (2023-2024)
2. Copy PineScript from file
3. Paste into Pine Editor → Add to Chart
4. Strategy Tester → Configure:
   - Initial Capital: $100,000
   - Order Size: Cash, $10,000
   - Commission: $0
   - Slippage: 0
5. Export:
   - List of Trades → CSV → `trades.csv`
   - Chart Data → CSV → `ohlcv.csv`
   - (Screenshot of performance)
6. Create `metadata.json` (template in README)
7. Save all to: `data/dvc/golden/strategies/ema_crossover/`

### Session 3: Strategy 2 - BB Mean Reversion

**Files Needed**: Create PineScript + configs first

1. (Wait for PineScript creation)
2. Follow same export process as EMA Crossover
3. Save to: `data/dvc/golden/strategies/bb_mean_reversion/`

### Session 4: Strategy 3 - RSI + ADX Multi

**Files Needed**: Create PineScript + configs first

1. (Wait for PineScript creation)
2. Follow same export process
3. Save to: `data/dvc/golden/strategies/multi_indicator_strategy/`

---

## Part 4: Recommended Phased Approach

### Phase 1: Minimum Viable Validation (Do This First)

**Goal**: Get basic validation working end-to-end

**What to Export**:
1. ✅ **Indicator Dataset**: EUR/USD 1H with existing 8 indicators
   - Already have sample data, but get full 2023-2024 dataset
2. ✅ **Strategy 1**: EMA Crossover (already ready)
   - Just need to export the 3 files

**Time Estimate**: 30-45 minutes in TradingView

**Outcome**:
- Validate indicator calculations work
- Validate strategy validation framework works
- Prove the concept end-to-end

### Phase 2: Expanded Coverage

**What to Export**:
1. **Enhanced Indicator Dataset**: Add 8 more indicators
   - SMA, MACD, Stochastic, CCI, WMA, ROC, OBV, CMF
2. **Strategy 2**: BB Mean Reversion
   - Create configs first, then export

**Time Estimate**: 1-2 hours

**Outcome**:
- More comprehensive indicator coverage
- Second strategy validates framework is reusable

### Phase 3: Complete Portfolio

**What to Export**:
1. **Strategy 3**: RSI + ADX Multi-Indicator
2. **Strategy 4** (Optional): MACD Crossover
3. **Volume Indicators**: VWAP, enhanced volume analysis
4. **Advanced Indicators**: Ichimoku, SuperTrend, KC, CHOP

**Time Estimate**: 2-3 hours

**Outcome**:
- Full golden validation suite
- Multiple complexity levels tested

---

## Part 5: File Organization

### Directory Structure After Complete Export

```
data/dvc/golden/
├── indicators/
│   ├── eurusd_1h_full_2023-2024.csv    (all indicators)
│   ├── metadata.json
│   └── README.md
│
└── strategies/
    ├── ema_crossover/
    │   ├── ohlcv.csv
    │   ├── trades.csv
    │   ├── equity_curve.csv (if available)
    │   └── metadata.json
    │
    ├── bb_mean_reversion/
    │   ├── ohlcv.csv
    │   ├── trades.csv
    │   └── metadata.json
    │
    └── multi_indicator_strategy/
        ├── ohlcv.csv
        ├── trades.csv
        └── metadata.json
```

---

## Part 6: Questions for You

Before we proceed, please confirm:

1. **Indicator Priority**:
   - Start with existing 8 indicators + add 8 new (Phase 1 + 2)?
   - Or wait and do all indicators at once?

2. **Strategy Priority**:
   - **Option A**: Just EMA Crossover first (fastest validation)
   - **Option B**: EMA + BB Mean Reversion (2 strategies)
   - **Option C**: All 3 strategies (comprehensive)

3. **Timeframe Consistency**:
   - Should all strategies use 1H for consistency?
   - Or use realistic timeframes (5min for BB, 4H for MACD)?

4. **Date Range**:
   - 2 years (2023-2024) sufficient?
   - Or prefer more history?

5. **Next Steps**:
   - Want me to create PineScript for BB Mean Reversion first?
   - Or export EMA Crossover data right away?

---

## Recommendation

**My Recommendation**: Start with **Phase 1 Minimal**

1. Export enhanced indicator dataset (existing 8 + MACD, Stochastic)
2. Export EMA Crossover strategy data
3. Validate framework works end-to-end
4. Then expand to Phase 2 & 3 based on results

**Time Investment**: ~45 minutes in TradingView
**Risk**: Low (proves concept)
**Value**: High (unblocks development)

Would you like me to create the enhanced indicator export script and BB
Mean Reversion PineScript before you go to TradingView?
