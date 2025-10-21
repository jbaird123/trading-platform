# TradingView Golden Validation Testing

## Overview

Golden validation testing ensures our trading platform produces
identical results to TradingView by comparing:

1. **Indicator calculations** (EMA, RSI, ADX, etc.)
2. **Strategy signals** (entry/exit timing)
3. **Trade execution** (entry/exit prices)
4. **Performance metrics** (PnL, win rate, drawdown)

## Why TradingView?

TradingView is:
- Industry-standard charting platform
- Well-tested indicator implementations
- Used by millions of traders
- Provides easy data export

By validating against TradingView, we ensure our platform is
accurate and trustworthy.

## Directory Structure

```
├── configs/golden_strategies/    # Strategy configs & PineScript
│   ├── ema_crossover/
│   ├── bb_mean_reversion/
│   └── multi_indicator_strategy/
│
├── data/dvc/golden/              # DVC-tracked validation data
│   ├── indicators/
│   └── strategies/
│
└── tests/validation/             # Validation test suite
    ├── conftest.py
    └── test_strategy_validation.py
```

## Quick Start

### 1. Pull Golden Data

```bash
dvc pull data/dvc/golden
```

### 2. Run Validation Tests

```bash
pytest -m validation
```

### 3. Review Results

Tests will report any discrepancies with detailed error messages.

## Detailed Workflow

### Phase 1: Indicator Validation

#### Step 1: Export from TradingView

1. Open TradingView chart for EURUSD 1H
2. Add indicators (EMA 20, EMA 50, RSI 14, etc.)
3. Export chart data with indicators included
4. Save to `data/dvc/golden/indicators/eurusd_1h_full.csv`

#### Step 2: Run Indicator Tests

```bash
pytest tests/data/test_golden_datasets.py -v
```

#### Step 3: Adjust Tolerances

If tests fail due to minor library differences:

1. Review actual vs expected values
2. Determine if difference is acceptable
3. Adjust tolerances in test file
4. Document rationale in comments

### Phase 2: Strategy Validation

#### Step 1: Choose Strategy

Start with simplest strategy first:
- **EMA Crossover** (recommended first)
- **BB Mean Reversion**
- **Multi-Indicator Strategy**

#### Step 2: Configure TradingView

1. Open Pine Editor in TradingView
2. Load PineScript from
   `configs/golden_strategies/ema_crossover/strategy.pine`
3. Add to chart
4. Open Strategy Tester settings:
   - Initial Capital: $100,000
   - Order Size: Cash, $10,000
   - Commission: 0.0
   - Slippage: 0 ticks

#### Step 3: Set Parameters

Ensure parameters match exactly:

| Parameter | Value |
|-----------|-------|
| Fast EMA | 20 |
| Slow EMA | 50 |
| Symbol | EURUSD |
| Timeframe | 1H |
| Start Date | 2023-01-01 |
| End Date | 2024-12-31 |

#### Step 4: Export Data

**Trades Export:**

1. Strategy Tester → List of Trades
2. Export to CSV
3. Save as: `data/dvc/golden/strategies/ema_crossover/trades.csv`

**OHLCV Export:**

1. Right-click chart → Export Chart Data
2. Save as: `data/dvc/golden/strategies/ema_crossover/ohlcv.csv`

**Equity Curve (if available):**

1. Strategy Tester → Equity Curve
2. Export to CSV
3. Save as: `data/dvc/golden/strategies/ema_crossover/equity_curve.csv`

#### Step 5: Create Metadata

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

#### Step 6: Validate Metadata

```bash
pytest tests/validation/test_strategy_validation.py::test_metadata_schema_validation
```

#### Step 7: Track with DVC

```bash
# Add to DVC
dvc add data/dvc/golden/strategies/ema_crossover/

# Push to remote
dvc push

# Commit DVC pointer
git add data/dvc/golden/strategies/ema_crossover.dvc
git commit -m "data: Add EMA crossover golden validation dataset"
```

#### Step 8: Run Strategy Tests

```bash
pytest tests/validation/test_strategy_validation.py::test_ema_crossover -v
```

## Tolerances Explained

### Critical: Warmup Period Requirements

**⚠️ The old "100 bars" warmup guidance was insufficient!**

Empirical testing with EMA crossover golden validation revealed that:
- **100 bars (~5 days for hourly data)** resulted in trade discrepancies
- **Exactly 1 month (~720 bars for hourly data)** produces perfect matching with TradingView
- Using the fixed date of 2022-12-01 for a 2023-01-01 validation start achieved zero-tolerance validation

**Required warmup periods by timeframe:**
- Hourly: 1 month (~720 bars)
- 4-hour: 1 month (~180 bars)
- Daily: 6 months (~130 bars)

### Why Tolerances?

Different libraries use slightly different algorithms:
- **pandas-ta** vs **TradingView built-ins**
- Rounding differences
- Floating-point arithmetic variations

### Acceptable Tolerances

#### Indicators

| Indicator | Tolerance | Reason |
|-----------|-----------|--------|
| EMA/SMA | rtol=1e-5 | Very stable calculation |
| RSI | rtol=1e-3 | Different smoothing methods |
| ADX | rtol=1e-2 | Complex multi-step calculation |
| Bollinger Bands | rtol=2e-4 | Standard deviation differences |

#### Trades

| Metric | Tolerance | Reason |
|--------|-----------|--------|
| Entry Time | 0 minutes | Should be exact |
| Exit Time | 0 minutes | Should be exact |
| Entry Price | 1 pip | Minor data differences |
| Exit Price | 1 pip | Minor data differences |
| Trade PnL | $0.50 | Rounding accumulation |

#### Performance

| Metric | Tolerance | Reason |
|--------|-----------|--------|
| Win Rate | 1% | Small sample variance |
| Profit Factor | 5% | Depends on PnL precision |
| Max Drawdown | 2% | Cumulative calculation |

### When to Adjust

**DO adjust** if:
- Difference is due to known library variations
- Tolerance is documented and justified
- New tolerance is still strict enough

**DON'T adjust** if:
- Difference indicates actual bug
- Logic mismatch between platforms
- Tolerance would be too lenient

## Adding New Strategies

### 1. Create Directory Structure

```bash
mkdir -p configs/golden_strategies/my_strategy
mkdir -p data/dvc/golden/strategies/my_strategy
```

### 2. Create Configuration Files

- `strategy.yaml` - Platform strategy definition
- `rem.yaml` - Risk/exit management
- `run_config.yaml` - Backtest configuration
- `strategy.pine` - PineScript equivalent
- `README.md` - Documentation

### 3. Implement in Both Platforms

Ensure logic is **identical**:
- Same indicators with same parameters
- Same entry conditions
- Same exit conditions
- Same position sizing

### 4. Export and Validate

Follow Phase 2 workflow above.

### 5. Add Tests

Add test functions in `tests/validation/test_strategy_validation.py`:

```python
@pytest.mark.validation
def test_my_strategy_trades_match_tradingview(
    golden_strategy_config,
    tradingview_trades,
):
    """Validates my_strategy against TradingView."""
    # Implementation here
    pass
```

## CI/CD Integration

### Current Setup

Validation tests are marked with `@pytest.mark.validation` and run
manually or on-demand.

### Why Not Automatic?

1. **Requires DVC Data** - Not all CI environments have data pulled
2. **Slower Execution** - Full backtests take time
3. **Optional Verification** - Not needed for every commit

### Running in CI

To enable in CI:

```yaml
# .github/workflows/validation.yml
name: Golden Validation

on:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup DVC
        run: pip install dvc[s3]
      - name: Pull Golden Data
        run: dvc pull data/dvc/golden
      - name: Run Validation Tests
        run: pytest -m validation
```

## Troubleshooting

### Problem: "Trade count mismatch"

**Cause**: Different entry logic or data

**Fix**:
1. Verify PineScript matches YAML exactly
2. Check date ranges are identical
3. Review warmup period settings
4. Ensure position sizing logic matches

### Problem: "Price differences > tolerance"

**Cause**: Different OHLC data or fill logic

**Fix**:
1. Use TradingView exported OHLCV
2. Verify data timestamps align
3. Check that both use same bar's close price
4. Review tolerance - may need slight adjustment

### Problem: "PnL doesn't match"

**Cause**: Position sizing or cost model differences

**Fix**:
1. Verify commission settings match
2. Check position size calculation
3. Ensure both use same currency
4. Review cost model implementation

### Problem: "Metadata validation fails"

**Cause**: Missing or incorrect metadata fields

**Fix**:
1. Check schema: `docs/schemas/golden_metadata.schema.json`
2. Validate JSON syntax
3. Ensure all required fields present
4. Check date format (YYYY-MM-DD)

## Maintenance

### Weekly

- [ ] Check DVC remote is accessible
- [ ] Verify test suite runs successfully

### Monthly

- [ ] Review tolerance settings
- [ ] Check for TradingView updates
- [ ] Validate pandas-ta version compatibility

### Quarterly

- [ ] Regenerate golden datasets
- [ ] Update documentation
- [ ] Review and add new strategies

## References

### Internal Documentation

- [Project Requirements](../project_requirements.md)
- Strategy validation model: `StrategyConfig` (see `src/trading_platform/strategy/models.py`)
- [Golden Metadata Schema](../schemas/golden_metadata.schema.json)

### External Resources

- [TradingView Pine Script Documentation](https://www.tradingview.com/pine-script-docs/en/v5/)
- [pandas-ta Documentation](https://github.com/twopirllc/pandas-ta)
- [DVC Documentation](https://dvc.org/doc)

## Contributing

When adding new golden validation datasets:

1. Follow existing patterns
2. Document everything thoroughly
3. Test before committing
4. Update this guide if workflow changes

## Questions?

Contact the Trading Platform Team or open an issue on GitHub.
