# Golden Validation Test Framework

This directory contains the golden validation framework for comparing platform backtests against TradingView reference implementations.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Adding a New Golden Strategy Test](#adding-a-new-golden-strategy-test)
4. [File Organization](#file-organization)
5. [Exit Mechanism Analyzers](#exit-mechanism-analyzers)
6. [Data Validation](#data-validation)
7. [Troubleshooting](#troubleshooting)

## Overview

The golden validation framework ensures platform backtests match TradingView reference strategies by:

1. **Comparing trades**: Entry/exit times, prices, and P&L
2. **Categorizing discrepancies**: All differences must be explained
3. **Hash verification**: Golden files prevent unintended changes

**Time to add a new test**: ~5 minutes (down from 30+ minutes)

**Test Performance**: Session-scoped fixtures cache backtest results - 81 tests run in ~26 seconds (79% faster than running backtests per-test)

## Quick Start

See [ANALYZER_GUIDE.md](ANALYZER_GUIDE.md) for details on the analyzer pattern and how to add new exit mechanisms.

## Adding a New Golden Strategy Test

### Prerequisites

Before starting, ensure you have:

1. **TradingView strategy** working correctly in Pine Script
2. **Platform strategy** configured in YAML
3. **OHLCV data** (hourly bars minimum)
4. **1-minute data** (required for trailing stops or indicator-based stops)

### Step 1: Create Strategy Directories

```bash
# Create directories
mkdir -p configs/golden_strategies/ema_crossover/atr_stop
mkdir -p data/dvc/golden/strategies/ema_crossover/atr_stop
```

### Step 2: Create Pine Script Strategy

**Location**: `configs/golden_strategies/ema_crossover/atr_stop/strategy.pine`

```pinescript
//@version=5
strategy("EMA Crossover ATR Stop Golden",
         overlay=true,
         initial_capital=100000,
         default_qty_value=10000,
         default_qty_type=strategy.cash,
         commission_type=strategy.commission.percent,
         commission_value=0.0,
         pyramiding=1,
         process_orders_on_close=false,  // Execute next bar open
         calc_on_order_fills=false,       // Only calculate on bar close
         calc_on_every_tick=false)        // Not real-time

// MANDATORY: Include volume (even if unused)
plot(volume, title="Volume", display=display.none)

// Inputs
fast_length = input.int(10, "Fast EMA Length")
slow_length = input.int(20, "Slow EMA Length")
atr_length = input.int(14, "ATR Length")
atr_multiplier = input.float(2.0, "ATR Multiplier")

// Indicators
ema_fast = ta.ema(close, fast_length)
ema_slow = ta.ema(close, slow_length)
atr = ta.atr(atr_length)

// Entry signals
long_signal = ta.crossover(ema_fast, ema_slow)
short_signal = ta.crossunder(ema_fast, ema_slow)

// ATR-based stop
var float stop_price = na
if (long_signal)
    stop_price := close - atr * atr_multiplier
    strategy.entry("Long", strategy.long)

if (short_signal)
    stop_price := close + atr * atr_multiplier
    strategy.entry("Short", strategy.short)

// Update stop based on current ATR
if (strategy.position_size > 0)  // Long position
    stop_price := close - atr * atr_multiplier
    strategy.exit("Exit Long", "Long", stop=stop_price)

if (strategy.position_size < 0)  // Short position
    stop_price := close + atr * atr_multiplier
    strategy.exit("Exit Short", "Short", stop=stop_price)

// Plot for visualization
plot(ema_fast, "Fast EMA", color=color.blue)
plot(ema_slow, "Slow EMA", color=color.red)
plot(stop_price, "Stop", color=color.orange, style=plot.style_linebr)
```

**CRITICAL**: Always use these exact strategy settings (from reference file):
- `process_orders_on_close=false` (execute next bar open)
- `calc_on_order_fills=false` (only calculate on bar close)
- `calc_on_every_tick=false` (not real-time)
- Include volume plot (mandatory even if unused)

### Step 3: Export TradingView Data

1. **Run strategy** in TradingView on EURUSD 1H chart
2. **Set timezone**: 'UTC (Reykjavik)' (NOT 'UTC (Azores)')
3. **Set date range**: 2022-12-01 to 2024-12-31 (includes warmup period before validation range)
4. **Export trades**: Strategy Tester → List of Trades → Export (CSV)
5. **Export OHLCV**: Chart → ... → Export chart data → CSV

**Save as**:
- `data/dvc/golden/strategies/ema_crossover/atr_stop/trades.csv`
- `data/dvc/golden/strategies/ema_crossover/atr_stop/ohlcv.csv`

**Understanding TradingView Trades CSV Format**:

TradingView exports **2 lines per trade** (Entry + Exit):
```csv
Trade #,Type,Date/Time,Signal,Price USD,...
1,Entry long,2022-12-07 18:00,Long,1.05181,...
1,Exit long,2022-12-08 09:00,Exit Long,1.04941,...
2,Entry short,2022-12-12 04:00,Short,1.05151,...
2,Exit short,2022-12-12 11:00,Close entry(s) order Short,1.05646,...
```

- Each trade has 2 rows (entry + exit)
- `Type` column contains "Entry" or "Exit"
- Trade count = (total lines - 1 header) / 2
- For 522 lines: (522-1)/2 = **260.5**, but we count **Entry lines = 261 trades**

**Date Ranges**:
- **Export range**: 2022-12-01 to 2024-12-31 (includes warmup)
- **Validation range**: 2023-01-01 to 2024-12-31 (actual test range)
- **Warmup period**: 2022-12-01 to 2022-12-31 (for indicator stability)

**Expected Counts for EMA Crossover Strategies**:
- **Total trades**: 261 (all strategies use same entry signals)
- **Validation trades**: 249 (entries with date >= 2023-01-01)
- **Baseline validation**: 248 (1 less due to force-closed end trade)

### Step 4: Create Metadata File

**Location**: `data/dvc/golden/strategies/ema_crossover/atr_stop/metadata.json`

The scaffold script creates this file with placeholder values. **You must update it after TradingView export.**

```json
{
  "dataset_type": "strategy",
  "strategy_name": "ema_crossover_atr_stop",
  "tradingview_version": "TradingView 2025",
  "export_date": "2025-10-19",  // UPDATE: Date you exported from TradingView
  "timezone": "UTC (Reykjavik)",
  "date_range": {
    "start": "2023-01-01",      // Validation range start
    "end": "2024-12-31"          // Validation range end
  },
  "instrument": "OANDA:EURUSD",
  "timeframe": "1H",
  "position_size": 10000.0,
  "commission": 0.0,
  "initial_capital": 100000.0,
  "exit_mechanisms": ["indicator_stop"],
  "indicator_stop_type": "atr",
  "indicator_stop_params": {
    "length": 14
  },
  "stop_distance_multiplier": 2.0,

  // UPDATE THESE AFTER EXPORT:
  "total_trades": 261,           // Total trades in CSV (count entry lines)
  "closed_trades": 261,          // Same as total (all trades closed)
  "open_trades": 0,              // Should be 0
  "validation_range_total_trades": 249,    // Entries >= 2023-01-01 AND <= 2024-12-31
  "validation_range_closed_trades": 249,   // Same as validation_range_total
  "net_profit": 0.0,
  "net_profit_percent": 0.0,
  "notes": "EMA crossover (20/50) with dynamic ATR-based stops. Warmup: 2022-12-01 to 2022-12-31."
}
```

**How to populate trade counts**:

1. **total_trades**: Count "Entry" lines in trades.csv
   ```bash
   grep -c "^[0-9]*,Entry" trades.csv
   ```
   Expected: **261** (all EMA crossover strategies have same entry signals)

2. **validation_range_total_trades**: Count entries where date >= 2023-01-01 AND <= 2024-12-31
   ```bash
   awk -F',' 'NR>1 && $2 ~ /Entry/ && $3 >= "2023-01-01" && $3 <= "2024-12-31"' trades.csv | wc -l
   ```
   Expected: **249** (baseline has 248 due to force-closed trade at end)

3. **closed_trades**: Same as total_trades (all trades should be closed)

4. **export_date**: Date you exported from TradingView (format: YYYY-MM-DD)

**Exit Mechanisms** (choose one or more):
- `"trailing_stop"`: Fixed pip trailing stop
- `"indicator_stop"`: Indicator-based stop (ATR, Bollinger, Keltner, etc.)
- `"fixed_stop"`: Fixed pip stop-loss
- `"take_profit"`: Fixed pip take-profit

**Indicator Stop Types** (when using `indicator_stop`):
- `"atr"`: Average True Range
- `"bollinger"`: Bollinger Bands (params: `band` = auto/lower/upper/middle,
  optional `length`, `std`, `offset`, `column_prefix`)
- `"keltner"`: Keltner Channels
- `"donchian"`: Donchian Channels
- (More can be added as needed)

### Step 5: Create Platform Configuration Files

**Location**: `configs/golden_strategies/ema_crossover/atr_stop/`

Create three files:

**strategy.yaml**:
```yaml
strategy:
  name: "ema_crossover"

  params:
    fast_length: 10
    slow_length: 20
    atr_length: 14
    atr_multiplier: 2.0
```

**rem.yaml** (Risk & Exit Management):
```yaml
rem:
  stop_loss:
    type: "indicator"
    indicator: "atr"
    params:
      length: 14
    multiplier: 2.0
    apply_on_entry: false  # Stop adjusts each bar
```

**run_config.yaml**:
```yaml
execution_model: "next_bar_open"  # Match TradingView
exit_tie_break: "stop_then_tp"  # If both hit same bar

instrument:
  symbol: "EURUSD"
  base_currency: "EUR"
  quote_currency: "USD"
  pip_location: -4
  contract_size: 100000

costs:
  spread_pips: 0.0
  commission_per_trade: 0.0
  slippage_pips: 0.0
```

### Step 6: Validate Data Quality

Run the data validator to ensure TradingView exports are correct:

```bash
poetry run python tests/validation/validate_golden_data.py \
  --strategy ema_crossover/atr_stop
```

This checks for:
- ✅ Volume column present in OHLCV
- ✅ Timezone is "UTC (Reykjavik)" (not "UTC (Azores)")
- ✅ Date range matches metadata.json
- ✅ No missing timestamps
- ✅ Trades within expected range

### Step 7: Generate Platform Golden Trades

```bash
poetry run python tests/validation/generate_golden_trades.py
```

This will:
1. Run platform backtest with your configuration
2. Save trades to `platform_trades_golden.csv`
3. Prevent accidental overwrites (file must be manually deleted to regenerate)

### Step 8: Add Session-Scoped Fixture and Tests

**IMPORTANT**: Tests use session-scoped fixtures to avoid redundant backtest execution. Each backtest runs only ONCE per test session, with results cached and shared across all tests.

#### Step 8.1: Add Session-Scoped Fixture

**Location**: `tests/validation/conftest.py`

Add a new session-scoped fixture for your strategy (add after existing platform_trades fixtures):

```python
@pytest.fixture(scope="session")
def platform_trades_atr_stop(
    shared_data_handler: Any,
    ensure_dvc_data_pulled: bool,
) -> list[dict]:
    """Session-scoped platform trades for ema_crossover/atr_stop strategy.

    Runs the backtest once per session and caches the results for all tests.
    This avoids redundant backtest execution across multiple test functions.

    Returns:
        List of trade dictionaries filtered to validation range
    """
    from tests.validation.test_strategy_validation import load_platform_trades

    # Load strategy-specific data
    strategy_name = "ema_crossover/atr_stop"
    strategy_data_dir = GOLDEN_STRATEGIES_ROOT / strategy_name
    strategy_config_dir = GOLDEN_CONFIG_ROOT / strategy_name

    # Load metadata
    metadata_path = strategy_data_dir / "metadata.json"
    with open(metadata_path) as f:
        metadata = json.load(f)

    # Load run_config
    run_config_path = strategy_config_dir / "run_config.yaml"
    with open(run_config_path) as f:
        run_config = yaml.safe_load(f)

    # Load OHLCV (not actually used since we use data_handler, but needed for signature)
    ohlcv_path = strategy_data_dir / "ohlcv.csv"
    ohlcv = pd.read_csv(ohlcv_path, index_col=0, parse_dates=True)

    return load_platform_trades(
        strategy_name=strategy_name,
        run_config=run_config,
        ohlcv_data=ohlcv,
        data_handler=shared_data_handler,
        date_range=metadata.get("date_range"),
    )
```

**Key points:**
- **Fixture name pattern**: `platform_trades_{strategy_suffix}` (e.g., `platform_trades_atr_stop`)
- **Scope**: Always `session` (backtest runs once and is cached)
- **Dependencies**: Uses `shared_data_handler` (also session-scoped for 1-min data)
- **Purpose**: Eliminates redundant backtest execution across tests

#### Step 8.2: Add to Parametrized Export Tests

**For parametrized tests**, add your strategy to the parametrize lists:

**File**: `tests/validation/test_export_exit_price_comparison.py`
```python
@pytest.mark.parametrize(
    "strategy_name",
    [
        "ema_crossover/20pip_stop",
        "ema_crossover/20pip_stop_40pip_tp",
        "ema_crossover/20pip_trailing_stop",
        "ema_crossover/20pip_trailing_stop_15pip_tp",
        "ema_crossover/atr_stop",  # <- Add this line
    ],
)
def test_export_exit_price_comparison(
    strategy_name,
    golden_strategy_config,
    tradingview_trades,
    tradingview_ohlcv,
    tradingview_ohlcv_1min,
    golden_metadata,
    request,
):
    # ... test uses request.getfixturevalue() to dynamically get platform_trades
```

The test will automatically fetch your fixture using `request.getfixturevalue("platform_trades_atr_stop")`.

Do the same for:
- `tests/validation/test_export_exit_time_comparison.py`

#### Step 8.3: Add Strategy Validation Tests

**File**: `tests/validation/test_strategy_validation.py`

Add test functions for your strategy. **Copy an existing strategy's tests** and modify:

**Example** (copy from 20pip_stop tests):
```python
def test_ema_crossover_atr_stop_metadata_schema_validation(golden_metadata):
    """Validates metadata.json against schema for atr_stop strategy."""
    # Validates: [DH-2.13]
    assert golden_metadata["strategy_name"] == "ema_crossover_atr_stop"


def test_ema_crossover_atr_stop_trade_count_matches_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_atr_stop,  # <- Use your fixture here
):
    """Validates ATR stop variation produces same number of trades.

    # Validates: [SE-3.5.3], [BT-7.8], [REM-6.3]
    """
    platform_trades = platform_trades_atr_stop  # Use cached results

    # Verify platform trades hash matches golden reference
    verify_golden_trades_hash("ema_crossover/atr_stop", platform_trades)

    # ... rest of test logic


def test_ema_crossover_atr_stop_entry_times_match_tradingview(
    tradingview_trades,
    golden_metadata,
    platform_trades_atr_stop,  # <- Use your fixture
):
    """Validates all entry times match between platform and TradingView."""
    platform_trades = platform_trades_atr_stop
    # ... test logic

# Add similar tests for:
# - entry_prices_match_tradingview
# - exit_times_match_tradingview
# - exit_prices_match_tradingview
```

**Pattern for function parameters:**
- Use `platform_trades_{strategy_suffix}` fixture (NOT `golden_strategy_config`, `shared_data_handler`, etc.)
- First line in test: `platform_trades = platform_trades_atr_stop` (use the cached fixture)
- This avoids rerunning the backtest - uses cached results from session start

**Why This Pattern?**
- ✅ **Performance**: Each backtest runs only once per session (saves 60-70% test time)
- ✅ **Consistency**: All tests use identical backtest results
- ✅ **Simplicity**: No need to pass multiple config fixtures to each test

### Step 9: Run Tests

```bash
poetry run pytest tests/validation/test_export_exit_price_comparison.py::test_export_exit_price_comparison[ema_crossover/atr_stop] -v
```

If the test passes:
```
✓ All exit price discrepancies explained
✓ Golden hash matches reference
```

If it fails, see [Troubleshooting](#troubleshooting).

### Step 10: Add to DVC and Git

```bash
# Add golden data to DVC
poetry run dvc add data/dvc/golden/strategies/ema_crossover/atr_stop

# Commit DVC metadata to git
git add data/dvc/golden/strategies/ema_crossover/atr_stop.dvc \
        configs/golden_strategies/ema_crossover/atr_stop/ \
        tests/validation/test_export_exit_price_comparison.py

git commit -m "test: Add ATR-based stop golden validation"

# Push DVC data to remote
poetry run dvc push

# Push git changes
git push
```

**Done!** 🎉 Your new golden strategy test is complete.

## File Organization

```
tests/validation/
├── README.md                           # This file
├── QUICK_START.md                      # Quick overview
├── IMPLEMENTATION_GUIDE.md             # Implementation details
├── IMPLEMENTATION_STATUS.md            # Progress tracker
│
├── analyzers/                          # Exit mechanism analyzers
│   ├── __init__.py                     # Registry and factory
│   ├── trailing_stop.py                # Trailing stop analyzer
│   └── indicator_stop.py               # Generic indicator stop analyzer
│
├── test_strategy_validation.py         # Main validation tests
├── test_export_exit_price_comparison.py # Exit price CSV export
├── test_export_exit_time_comparison.py  # Exit time CSV export
├── test_export_trades_comparison.py     # All trades CSV export
│
├── conftest.py                         # Pytest fixtures
├── golden_utils.py                     # Golden data loading
├── comparison_utils.py                 # Comparison helpers
├── comparison_export.py                # CSV export utilities
│
├── generate_golden_trades.py           # Generate platform trades
└── validate_golden_data.py             # Validate TradingView exports

configs/golden_strategies/
└── ema_crossover/
    └── atr_stop/
        ├── strategy.yaml               # Strategy parameters
        ├── rem.yaml                    # Risk & exit management
        ├── run_config.yaml             # Backtest config
        └── strategy.pine               # TradingView Pine Script

data/dvc/golden/strategies/
└── ema_crossover/
    └── atr_stop/
        ├── metadata.json               # Test metadata
        ├── ohlcv.csv                   # TradingView OHLCV export
        ├── trades.csv                  # TradingView trades export
        ├── platform_trades_golden.csv  # Platform reference trades
        ├── exit_price_comparison_golden.csv  # Price comparison reference
        └── exit_time_comparison_golden.csv   # Time comparison reference
```

## Exit Mechanism Analyzers

The framework uses a pluggable analyzer system for different exit mechanisms:

### Trailing Stop Analyzer

**Analyzer**: `TrailingStopDiscrepancyAnalyzer`
**Registered as**: `"trailing_stop"`
**Metadata fields**:
- `trailing_stop_pips` (required)
- `take_profit_pips` (optional)

**Acceptable discrepancy categories**:
1. `SAME_BAR_EXIT`: Entry and exit on same bar (TV limitation)
2. `TV_IGNORED_ENTRY_BAR_PEAK_MFE_STRICT`: Entry bar MFE ignored by TV
3. `TV_IGNORED_ENTRY_BAR_PEAK_MFE_VERIFIED`: Entry bar MFE verified
4. `PLATFORM_ZOOM_INTRABAR_STOP`: Platform detected intrabar stop
5. `PLATFORM_ZOOM_INTRABAR_TP`: Platform detected intrabar TP

### Indicator Stop Analyzer

**Analyzer**: `IndicatorStopAnalyzer`

- The analyzer registry now returns a `CompositeAmbiguityAnalyzer` when
  `exit_mechanisms` lists multiple entries, so mixed exit strategies are
  validated in a single pass.
**Registered as**: `"indicator_stop"`
**Metadata fields**:
- `indicator_stop_type` (required): "atr", "bollinger", "keltner", etc.
- `indicator_stop_params` (required): indicator-specific parameters
- `stop_distance_multiplier` (required): multiplier for stop distance

**Acceptable discrepancy categories**:
1. `SAME_BAR_EXIT`: Entry and exit on the same bar (TradingView limitation)
2. `PLATFORM_ZOOM_INTRABAR_STOP`: Platform detected intrabar stop via 1-minute zoom
3. `PLATFORM_ZOOM_INTRABAR_TP`: Platform detected intrabar take-profit via zoom

**Example metadata** (ATR stop):
```json
{
  "exit_mechanisms": ["indicator_stop"],
  "indicator_stop_type": "atr",
  "indicator_stop_params": {
    "length": 14
  },
  "stop_distance_multiplier": 2.0
}
```

### Adding a New Analyzer

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for details on creating custom analyzers.

## Data Validation

Before running tests, validate TradingView exports:

```bash
poetry run python tests/validation/validate_golden_data.py \
  --strategy ema_crossover/atr_stop
```

**Common validation errors**:

### Missing Volume Column
```
❌ OHLCV missing volume column
```
**Fix**: Re-export from TradingView, or manually add volume column with value 1.0

### Wrong Timezone
```
❌ Timezone is 'UTC (Azores)' but should be 'UTC (Reykjavik)'
```
**Fix**: Change TradingView chart timezone to "UTC (Reykjavik)" and re-export

### Date Range Mismatch
```
❌ Date range in trades.csv doesn't match metadata.json
```
**Fix**: Update metadata.json or re-export with correct date range

## Troubleshooting

### Test Fails: "Found N UNEXPLAINED exit price mismatches"

**Cause**: Platform and TradingView exits differ, but analyzer didn't categorize it.

**Debug steps**:

1. **Check CSV output**:
   ```bash
   open workspace/exit_price_comparison.csv
   ```
   Look for rows where `failure_category` is "UNEXPLAINED"

2. **Common causes**:
   - **Indicator not matching**: Platform indicator calculation differs from TradingView
   - **Stop logic difference**: Platform applies stop differently than TradingView
   - **Entry bar handling**: TradingView ignores entry bar for some calculations

3. **Fix options**:
   - **Add new category** to analyzer if this is expected behavior
   - **Fix platform code** if platform is wrong
   - **Fix TradingView script** if TradingView script is wrong

### Test Fails: "Golden hash mismatch"

**Cause**: Comparison CSV changed from golden reference.

**Debug steps**:

1. **Compare files**:
   ```bash
   diff workspace/exit_price_comparison.csv \
        data/dvc/golden/strategies/ema_crossover/atr_stop/exit_price_comparison_golden.csv
   ```

2. **If change is expected** (e.g., fixed a bug):
   ```bash
   # Backup old golden
   cp data/dvc/golden/strategies/ema_crossover/atr_stop/exit_price_comparison_golden.csv \
      data/dvc/golden/strategies/ema_crossover/atr_stop/exit_price_comparison_golden.csv.backup

   # Copy new as golden
   cp workspace/exit_price_comparison.csv \
      data/dvc/golden/strategies/ema_crossover/atr_stop/exit_price_comparison_golden.csv

   # Add to DVC
   poetry run dvc add data/dvc/golden/strategies/ema_crossover/atr_stop

   # Commit
   git add data/dvc/golden/strategies/ema_crossover/atr_stop.dvc
   git commit -m "data: Update ATR stop golden after bug fix"
   poetry run dvc push
   ```

3. **If change is unexpected**:
   - Review diff carefully
   - Understand why comparison changed
   - Likely indicates a regression

#### Quick diff helper

Instead of manually running each comparison, use the helper script to run the
hash-based pytest modules and auto-generate diffs for every failing strategy:

```bash
poetry run python scripts/run_golden_hash_checks.py
```

The script prints the pytest output, collects any `hash mismatch` failures and
immediately feeds the corresponding workspace/golden files into
`scripts/golden_compare.py`. Use `--strategies foo/bar baz/qux` to focus the
diffs on a subset of strategies (tests still run for all of them).

Need the raw pytest logs? Add `--show-pytest-output` to stream the underlying
stdout/stderr while the script runs.

### Platform Trades Don't Match TradingView

**Cause**: Strategy logic differs between platform and TradingView.

**Debug steps**:

1. **Compare first discrepancy**:
   ```bash
   open workspace/exit_price_comparison.csv
   ```
   Find first row where `exit_price_match` is False

2. **Check entry conditions** match exactly
3. **Check indicator calculations** match exactly
4. **Check execution model** is correct (`next_bar_open`)
5. **Check warmup period** is sufficient for indicators

### Tests Pass Locally But Fail in CI

**Cause**: Missing DVC data or environment differences.

**Debug steps**:

1. **Pull DVC data**:
   ```bash
   poetry run dvc pull
   ```

2. **Check Python version** matches CI
3. **Check pandas/numpy versions** match CI
4. **Check timezone** is UTC

---

**Questions or issues?** See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) or ask the team.
