# Golden Validation Guide

This document explains the golden validation system for comparing platform backtests against TradingView exports.

## Table of Contents

- [Overview](#overview)
- [The Golden Validation Contract](#the-golden-validation-contract)
- [Common Confusion Points](#common-confusion-points)
- [Implementation Guidelines](#implementation-guidelines)
- [Example Test Structure](#example-test-structure)

## Overview

Golden validation tests verify that our platform produces identical results to TradingView Pine Script backtests. This validates the entire trading stack: signal generation, position management, risk management, and trade execution.

**Key Principle**: TradingView exports contain MORE data than the validation range. Tests MUST filter both platform and TradingView trades to the exact validation range specified in `metadata.json`.

## The Golden Validation Contract

### 1. Data Export Ranges

**WHY exports contain extra data:**
- TradingView doesn't support precise date range exports
- Exports must include warmup period for indicator calculations
- Exports often include data before warmup and after validation end

**RULE**: Always filter trades to validation range from `metadata.json`:

```json
{
  "date_range": {
    "start": "2023-01-01",  // Validation starts here
    "end": "2024-12-31"      // Validation ends here
  },
  "total_trades": 261,        // Total in export (warmup + validation)
  "validation_range_closed_trades": 249  // Only in validation range
}
```

**Correct filtering:**
```python
# Platform trades: Filter by entry_time in validation range
platform_trades = [
    t for t in all_trades
    if validation_start <= t.entry_time <= validation_end
    and t.exit_reason != "end_of_data"
]

# TradingView trades: Filter by entry_time in validation range
tv_trades = [
    t for t in all_tv_trades
    if validation_start <= t.entry_time <= validation_end
]
```

### 2. Warmup Period Requirements

**WHY warmup is needed:**
- Technical indicators (EMAs, SMA, etc.) need historical data to converge
- TradingView calculates indicators from years of historical data
- Platform starts fresh, needs warmup to match TradingView's values

**RULE**: Use 1 month of warmup for hourly strategies (NOT 100 bars):

```python
# Hardcoded warmup start: 1 month before validation
WARMUP_START = pd.Timestamp("2022-12-01", tz="UTC")  # For 2023-01-01 validation start
VALIDATION_START = pd.Timestamp("2023-01-01", tz="UTC")

# Run backtest on extended data
ohlcv_for_backtest = ohlcv[(ohlcv.index >= WARMUP_START) & (ohlcv.index <= validation_end)]

# But only compare trades in validation range
trades_to_compare = [t for t in trades if validation_start <= t.entry_time <= validation_end]
```

**Empirical evidence:**
- 100 bars (~5 days hourly): ❌ Trade discrepancies observed
- 1 month (~720 bars hourly): ✅ Perfect matching achieved

**Different timeframes:**
- **Hourly**: 1 month warmup (~720 bars)
- **4-hour**: 1 month warmup (~180 bars)
- **Daily**: 6 months warmup (~130 bars)

### 2.5 Cached Global Features

Global contextual indicators are now precomputed and cached per data root. This
keeps warmup windows focused on strategy features while guaranteeing that the
master trade log, campaign runs, and golden validations see the exact same
feature values.

**Command overview**

```bash
# Raw Dukascopy data (used by backtests / campaigns)
poetry run trading-platform precompute-global-features \
  --symbol EURUSD \
  --data-root data/dvc/raw \
  --config config/features/global.yaml \
  --timeframes 5min 15min 1H 4H 1D

# TradingView golden data (used by tests/validation)
poetry run trading-platform precompute-global-features \
  --symbol EURUSD \
  --data-root data/dvc/golden/ohlcv/tradingview \
  --config data/dvc/golden/features/global.yaml \
  --timeframes 1H
```

Each run writes parquet snapshots under `<data_root>/features/global/`. The
CLI auto-skips existing caches unless `--overwrite` is provided.

**Warmup impact**

Golden validation now checks whether the cache covers every global feature used
for the execution timeframe. When present, only strategy features influence the
warmup calculation; otherwise the code gracefully falls back to the legacy
behavior and recomputes features on the fly. This guarantees deterministic
feature values while keeping the validation contract unchanged.

### 3. OHLCV Data Start vs Warmup Start

**COMMON CONFUSION**: "The OHLCV export starts at 2022-11-24, but you said warmup starts 2022-12-01?"

**CLARIFICATION**:
```
Timeline:
├─ 2022-11-24 ─┐
│              ├─ OHLCV export starts (ignored data)
│              │
├─ 2022-12-01 ─┤
│              ├─ Warmup period starts (USE this as start)
│              ├─ Any data before this is IGNORED
│              │
├─ 2023-01-01 ─┤
│              ├─ Validation period starts
│              ├─ Trades are counted from HERE
│              │
├─ 2024-12-31 ─┤
               └─ Validation period ends
```

**WHY exports include extra data before warmup:**
- TradingView export UI doesn't allow precise date selection
- Exporting "extra" data is harmless - we just ignore it
- Tests explicitly filter to `warmup_start`, discarding earlier data

**Implementation:**
```python
# WRONG: Using export start date
warmup_start = ohlcv_data.index.min()  # ❌ Could be 2022-11-24

# CORRECT: Using hardcoded warmup start
warmup_start = pd.Timestamp("2022-12-01", tz="UTC")  # ✅ Always 2022-12-01
ohlcv_filtered = ohlcv_data[ohlcv_data.index >= warmup_start]
```

### 4. Timezone Requirements

**RULE**: ALL timestamps MUST be UTC. No other timezones are allowed.

**WHY UTC only:**
- Eliminates timezone conversion bugs
- Avoids DST (daylight saving time) issues
- TradingView export uses "UTC (Reykjavik)" which has no DST
- Simplifies time comparisons

**CRITICAL DISTINCTION:**

**OHLCV Files** (with timezone info):
- Timestamps have explicit timezone markers: `2023-01-06T19:00:00Z`
- MUST use **UTC (Reykjavik)** in TradingView (NOT "UTC (Azores)")
- Validation checks timezone markers and rejects non-UTC

**Trades Files** (timezone-naive):
- Timestamps have NO timezone markers: `2023-01-06 19:00`
- ASSUMED to be UTC based on TradingView timezone setting
- Cannot validate timezone (no markers to check)

**TradingView Export Settings:**
```
Settings → Chart → Timezone → "UTC (Reykjavik)"

✅ CORRECT: UTC (Reykjavik) - Pure UTC, no DST
❌ WRONG:   UTC (Azores)    - Has DST offsets (-01:00)
❌ WRONG:   Exchange         - Varies by instrument
❌ WRONG:   EST/EDT/PST      - US timezones with DST
```

**See also:** `configs/golden_strategies/ema_crossover/UTC_TIMEZONE_REQUIREMENTS.md`

**Validation:**
```python
from tests.validation.golden_utils import (
    validate_utc_timezone_ohlcv,  # For OHLCV files ONLY
    load_and_validate_ohlcv,      # Validates automatically
    load_and_validate_tradingview_trades  # Assumes UTC (can't validate)
)

# OHLCV: Explicit validation (has timezone markers)
validate_utc_timezone_ohlcv(ohlcv_df, "time", "OHLCV data")

# Trades: No validation possible (no timezone markers)
# Just parse as UTC and trust TradingView export settings
trades_df["Date/Time"] = pd.to_datetime(trades_df["Date/Time"], utc=True)
```

**Common mistake:**
```python
# ❌ WRONG: Trying to validate trades timezone
validate_utc_timezone_ohlcv(trades_df, "Date/Time", "trades")  # Will fail!

# ✅ CORRECT: Only validate OHLCV
validate_utc_timezone_ohlcv(ohlcv_df, "time", "OHLCV data")
trades_df["Date/Time"] = pd.to_datetime(trades_df["Date/Time"], utc=True)  # Assume UTC
```

### 5. Trade Counting and Matching

**RULE**: Match trades by `entry_time` within validation range.

**Correct comparison:**
```python
# Both filtered to same validation range
platform_count = len([t for t in platform_trades
                     if validation_start <= t.entry_time <= validation_end])

tv_count = len([t for t in tv_trades
               if validation_start <= t.entry_time <= validation_end])

assert platform_count == tv_count
```

**Common mistakes:**
```python
# ❌ WRONG: Using total trades from export
assert len(platform_trades) == metadata["total_trades"]  # Includes warmup trades!

# ❌ WRONG: Comparing unfiltered data
assert len(platform_trades) == len(tv_df)  # TV export not filtered!

# ✅ CORRECT: Using validation range count from metadata
assert len(platform_trades) == metadata["validation_range_closed_trades"]
```

## Common Confusion Points

### "Why does TradingView export have 261 trades but metadata says 249?"

**Answer**: The 261 includes trades from the warmup period (2022-12-01 to 2022-12-31). The validation range (2023-01-01 to 2024-12-31) has 249 trades. Tests MUST filter to 249.

### "Why do we ignore OHLCV data before 2022-12-01?"

**Answer**: TradingView export includes extra data because precise date filtering isn't available in the UI. The extra data is harmless - we just filter it out. The warmup start (2022-12-01) is hardcoded and explicitly documented.

### "Could there be a timezone issue causing 1-hour differences?"

**Answer**: No. All data files use UTC timestamps:
- **OHLCV files**: Have explicit UTC timezone markers (`Z` suffix) that are validated
- **Trades files**: Have no timezone markers, but are ASSUMED to be UTC based on TradingView's timezone setting (UTC Reykjavik)

The validation utilities check OHLCV timezone markers and raise errors if non-UTC is found (e.g., `-01:00` from UTC Azores).

Any time differences in trades are due to other factors (e.g., intra-bar stop loss timing differences between platform and TradingView), NOT timezone issues.

### "Why 1 month warmup instead of 100 bars?"

**Answer**: Empirical testing. With 100 bars, we saw trade discrepancies in early validation period. With exactly 1 month, we achieved perfect matching (248 trades, zero time/price differences). This was validated with the baseline EMA crossover test.

## Implementation Guidelines

### Using the Golden Utilities

**All golden validation tests MUST use the utilities in `tests/validation/golden_utils.py`:**

```python
from tests.validation.golden_utils import (
    load_and_validate_ohlcv,
    load_and_validate_tradingview_trades,
    filter_platform_trades_to_validation_range,
)

# 1. Load metadata
with open(metadata_path) as f:
    metadata = json.load(f)

validation_range = metadata["date_range"]  # {"start": "2023-01-01", "end": "2024-12-31"}

# 2. Load OHLCV (automatically filtered and validated)
ohlcv = load_and_validate_ohlcv(
    ohlcv_path,
    validation_range=validation_range,
    warmup_start=pd.Timestamp("2022-12-01", tz="UTC")
)

# 3. Load TradingView trades (automatically filtered and validated)
tv_trades_df = load_and_validate_tradingview_trades(
    tv_trades_path,
    validation_range=validation_range
)

# 4. Run platform backtest on extended data
results = run_backtest_from_config(config, ohlcv, strategy_config)

# 5. Filter platform trades to validation range
platform_trades = filter_platform_trades_to_validation_range(
    results["trades"],
    validation_range
)

# 6. Compare
assert len(platform_trades) == len(tv_trades_df)
```

### What Gets Validated Automatically

When using the utility functions:

✅ **Automatic UTC validation** - Raises error if non-UTC timestamps found
✅ **Automatic range filtering** - Filters to validation range from metadata
✅ **Automatic warmup handling** - Uses correct warmup start (2022-12-01)
✅ **Clear error messages** - Explains exactly what's wrong if validation fails

### Creating New Golden Tests

**Template for new golden validation tests:**

```python
import json
from pathlib import Path
import pandas as pd

from tests.validation.golden_utils import (
    load_and_validate_ohlcv,
    load_and_validate_tradingview_trades,
    filter_platform_trades_to_validation_range,
)

def test_my_strategy_matches_tradingview():
    """Validates my_strategy produces same trades as TradingView."""

    # 1. Load metadata
    strategy_path = Path("data/dvc/golden/strategies/my_strategy")
    with open(strategy_path / "metadata.json") as f:
        metadata = json.load(f)

    validation_range = metadata["date_range"]

    # 2. Load and validate data (automatic filtering + UTC validation)
    ohlcv = load_and_validate_ohlcv(
        strategy_path / "ohlcv.csv",
        validation_range=validation_range
    )

    tv_trades = load_and_validate_tradingview_trades(
        strategy_path / "trades.csv",
        validation_range=validation_range
    )

    # 3. Run platform backtest
    # (config, strategy setup omitted for brevity)
    results = run_backtest_from_config(config, ohlcv, strategy_config)

    # 4. Filter platform trades
    platform_trades = filter_platform_trades_to_validation_range(
        results["trades"],
        validation_range
    )

    # 5. Compare
    assert len(platform_trades) == len(tv_trades)
    assert len(platform_trades) == metadata["validation_range_closed_trades"]
```

## Example Test Structure

Here's the complete structure for a golden validation test:

```
data/dvc/golden/strategies/my_strategy/
├── metadata.json          # Contains validation range, expected counts
├── ohlcv.csv             # Price data (may include extra data)
└── trades.csv            # TradingView export (may include extra trades)

configs/golden_strategies/my_strategy/
├── strategy.yaml         # Strategy definition
├── run_config.yaml       # Backtest configuration
└── rem.yaml             # Risk management config (optional)

tests/validation/
├── test_strategy_validation.py  # Test implementation
└── golden_utils.py              # Shared utilities (USE THESE!)
```

**Key points:**
1. `ohlcv.csv` may start before warmup_start → Ignored
2. `trades.csv` may include warmup trades → Filtered
3. `metadata.json` specifies exact validation range → Used for filtering
4. `golden_utils.py` functions handle all filtering → Use them!

## Summary Checklist

When creating or reviewing golden validation tests:

- [ ] Uses `load_and_validate_ohlcv()` for OHLCV data
- [ ] Uses `load_and_validate_tradingview_trades()` for TV trades
- [ ] Uses `filter_platform_trades_to_validation_range()` for platform trades
- [ ] Validates against `metadata["validation_range_closed_trades"]`
- [ ] Does NOT use raw CSV lengths for assertions
- [ ] Does NOT assume OHLCV start date = warmup start date
- [ ] Does NOT manually parse timestamps (utilities handle it)
- [ ] UTC validation is automatic (no manual timezone conversion)
- [ ] Comments explain WHY filtering happens, not just WHAT

## References

- Utility Functions: `tests/validation/golden_utils.py`
- Test Examples: `tests/validation/test_strategy_validation.py`
- Warmup Analysis: `docs/testing_guide.md` (Section: "Golden Validation Warmup")
- Metadata Schema: `tests/validation/metadata_schema.json`
