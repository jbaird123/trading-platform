# EMA Crossover Strategy Variations

This directory contains multiple variations of the EMA 20/50 crossover
strategy for golden validation testing against TradingView.

## Overview

All variations share the same core logic:
- **Entry:** EMA(20) crosses EMA(50)
- **Exit:** Opposite crossover
- **Parameters:** Fast=20, Slow=50
- **Instrument:** EURUSD 1H
- **Position Size:** $10,000 per trade
- **Initial Capital:** $100,000

The variations differ only in their risk management (stop loss/TP).

---

## Variations

### 1. Baseline (No Stops)
**Location:** `baseline/`

**Purpose:** Validate core signal generation without risk management

**Characteristics:**
- No stop loss
- No take profit
- Exits only on opposite crossover signal
- Pure signal-to-signal validation

**What This Tests:**
- Indicator calculations (EMA)
- Entry/exit signal timing
- Trade count accuracy
- Signal-based PnL

**Status:** ✅ Validated and passing

---

### 2. 20-Pip Stop Loss
**Location:** `20pip_stop/`

**Purpose:** Validate Risk & Exit Manager (REM) stop-loss logic

**Characteristics:**
- Fixed 20-pip stop loss on all trades
- No take profit
- Can exit via stop OR opposite signal (whichever first)

**What This Tests:**
- Stop loss execution timing
- Intra-bar fill logic
- Exit precedence (stop vs signal)
- Risk-managed PnL calculation

**Status:** 📋 Ready for export

---

## Directory Structure

```
ema_crossover/
├── README_VARIATIONS.md         # This file
├── baseline/
│   ├── strategy.yaml            # Platform strategy config
│   ├── strategy.pine            # TradingView PineScript
│   ├── rem.yaml                 # Risk/exit config (empty)
│   ├── run_config.yaml          # Backtest config
│   └── README.md                # Variation-specific docs
├── 20pip_stop/
│   ├── strategy.yaml            # Same as baseline
│   ├── strategy.pine            # With stop loss logic
│   ├── rem.yaml                 # Fixed 20-pip stop
│   ├── run_config.yaml          # Same as baseline
│   └── README.md                # Variation-specific docs
└── [Analysis docs...]           # Shared analysis documents
```

## Corresponding Data Structure

```
data/dvc/golden/strategies/ema_crossover/
├── baseline/
│   ├── ohlcv.csv
│   ├── trades.csv
│   └── metadata.json
└── 20pip_stop/
    ├── ohlcv.csv
    ├── trades.csv
    └── metadata.json
```

---

## Adding New Variations

To add a new variation:

1. **Create subdirectory:**
   ```bash
   mkdir configs/golden_strategies/ema_crossover/new_variation/
   ```

2. **Copy baseline files:**
   ```bash
   cp baseline/{strategy.yaml,run_config.yaml} new_variation/
   ```

3. **Modify risk management:**
   - Update `rem.yaml` with new stop/TP rules
   - Update `strategy.pine` to match logic

4. **Document:**
   - Create `README.md` in variation directory
   - Update this file with new variation

5. **Export from TradingView:**
   - Follow instructions in variation's README
   - Place data in `data/dvc/golden/strategies/ema_crossover/new_variation/`

6. **Track with DVC:**
   ```bash
   dvc add data/dvc/golden/strategies/ema_crossover/new_variation/
   dvc push
   git add data/dvc/golden/strategies/ema_crossover/new_variation.dvc
   ```

---

## Future Variation Ideas

Potential variations to test different aspects of the platform:

### Risk Management Variations
- **Take-profit only** (e.g., 30-pip TP, no stop)
- **Stop + TP together** (e.g., 20-pip stop, 40-pip TP)
- **Trailing stop** (e.g., 30-pip trailing)
- **ATR-based stop** (dynamic stop based on volatility)

### Position Sizing Variations
- **Fixed risk** (risk 1% of equity per trade)
- **Smaller positions** (e.g., $5k per trade)

### Entry Variations
- **ADX filter** (only enter when ADX > 25)
- **Volume filter** (only enter on high volume)

---

## Validation Testing

Each variation has corresponding tests in:
```
tests/validation/test_strategy_validation.py
```

Tests are organized by variation name:
- `test_baseline_*` - Tests for baseline variation
- `test_20pip_stop_*` - Tests for 20-pip stop variation

Run all variation tests:
```bash
pytest -m validation tests/validation/test_strategy_validation.py
```

Run specific variation:
```bash
pytest -m validation -k "baseline" tests/validation/
pytest -m validation -k "20pip_stop" tests/validation/
```

---

## Notes

- Keep strategy logic identical across variations
- Only modify risk management (REM) settings
- Document expected differences clearly
- Each variation tests different platform components
- All variations use same OHLCV data (different trades)
