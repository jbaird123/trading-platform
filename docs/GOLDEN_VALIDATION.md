# Golden Validation Quick Reference

> **For detailed guide, see:** [docs/validation/golden_validation_guide.md](validation/golden_validation_guide.md)

## TL;DR - What You MUST Know

### 1. Export Data Contains MORE than Validation Range
- TradingView exports include warmup period + extra data
- Tests MUST filter to validation range from `metadata.json`
- Never use raw CSV lengths for assertions

### 2. Warmup Start ≠ Data Start
```
2022-11-24 ← Data export starts (IGNORED)
2022-12-01 ← Warmup starts (USE THIS)
2023-01-01 ← Validation starts (COUNT TRADES FROM HERE)
2024-12-31 ← Validation ends
```

### 3. Timezone: OHLCV vs Trades
- **OHLCV**: Has timezone markers (`Z` suffix), CAN validate
- **Trades**: NO timezone markers, ASSUMED UTC (can't validate)
- MUST use "UTC (Reykjavik)" NOT "UTC (Azores)"

### 4. Use the Utility Functions
```python
from tests.validation.golden_utils import (
    load_and_validate_ohlcv,              # Auto-filters + validates
    load_and_validate_tradingview_trades, # Auto-filters (assumes UTC)
    filter_platform_trades_to_validation_range,
)
```

## Critical Documentation

1. **Main Guide**: [docs/validation/golden_validation_guide.md](validation/golden_validation_guide.md)
2. **Timezone Requirements**: [configs/golden_strategies/ema_crossover/UTC_TIMEZONE_REQUIREMENTS.md](../configs/golden_strategies/ema_crossover/UTC_TIMEZONE_REQUIREMENTS.md)
3. **Utility Functions**: [tests/validation/golden_utils.py](../tests/validation/golden_utils.py)

## Common Mistakes

❌ **WRONG**: Using total trades from export
```python
assert len(platform_trades) == len(tv_trades_df)  # Includes warmup!
```

✅ **CORRECT**: Using validation range count
```python
assert len(platform_trades) == metadata["validation_range_closed_trades"]
```

---

❌ **WRONG**: Using data start as warmup start
```python
warmup_start = ohlcv.index.min()  # Could be 2022-11-24
```

✅ **CORRECT**: Using hardcoded warmup start
```python
warmup_start = pd.Timestamp("2022-12-01", tz="UTC")
```

---

❌ **WRONG**: Trying to validate trades timezone
```python
validate_utc_timezone_ohlcv(trades_df, "Date/Time", "trades")  # No timezone markers!
```

✅ **CORRECT**: Only validate OHLCV
```python
validate_utc_timezone_ohlcv(ohlcv_df, "time", "OHLCV")
trades_df["Date/Time"] = pd.to_datetime(trades_df["Date/Time"], utc=True)  # Assume UTC
```

## When Creating New Golden Tests

1. ✅ Use `load_and_validate_ohlcv()` - handles filtering & validation
2. ✅ Use `load_and_validate_tradingview_trades()` - handles filtering
3. ✅ Use `filter_platform_trades_to_validation_range()` - filters platform trades
4. ✅ Compare against `metadata["validation_range_closed_trades"]`
5. ✅ Document WHY filtering happens (not just WHAT)

## FAQ

**Q: Why does my TradingView CSV have 261 trades but metadata says 249?**
A: The 261 includes warmup period trades. Filter to validation range (2023-01-01 onwards) to get 249.

**Q: Why ignore OHLCV data before 2022-12-01?**
A: TradingView export includes extra data. Warmup starts at 2022-12-01 (hardcoded). Earlier data is ignored.

**Q: Could there be a timezone issue?**
A: No. OHLCV has validated UTC markers. Trades are assumed UTC based on export settings. Use "UTC (Reykjavik)" NOT "UTC (Azores)".

**Q: Why 1 month warmup, not 100 bars?**
A: Empirical evidence. 100 bars caused discrepancies. 1 month (~720 bars hourly) achieves perfect matching.

---

**For full explanation and examples, see:** [docs/validation/golden_validation_guide.md](validation/golden_validation_guide.md)
