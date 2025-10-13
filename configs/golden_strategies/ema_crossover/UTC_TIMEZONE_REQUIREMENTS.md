# UTC Timezone Requirements for TradingView Exports

## Critical Issue Discovered

TradingView has **TWO** different UTC timezone options that produce **different** results:
1. **UTC (Azores)** ❌ - Includes DST offsets (`-01:00` during certain months)
2. **UTC (Reykjavik)** ✅ - Pure UTC with no offsets (always `Z` suffix)

## Why This Matters

### UTC (Azores) - INCORRECT
- Produces timestamps like: `2023-01-06T19:00:00-01:00`
- The `-01:00` offset means "Azores time during DST"
- Results in **mixed timezone formats** within the same file
- Some bars have `Z` suffix, others have `-01:00`
- **This is NOT pure UTC!**

### UTC (Reykjavik) - CORRECT
- Produces timestamps like: `2023-01-06T19:00:00Z`
- The `Z` suffix means "Zulu time" (UTC)
- **All timestamps are pure UTC**
- Iceland doesn't observe DST, so it's always UTC+0
- This is the **ISO 8601 standard** for UTC

## Export Instructions

### Step 1: Set Timezone in TradingView

1. Click **Settings** (gear icon) in TradingView
2. Go to **Chart** settings
3. Find **Timezone** dropdown
4. Select **`UTC (Reykjavik)`**
   - ⚠️ **DO NOT** select `UTC (Azores)`
   - ⚠️ **DO NOT** select `Exchange` or any named timezone

### Step 2: Export OHLCV Data

1. Right-click on chart → "Export chart data..."
2. Select date range (should cover all trades)
3. **Include "Indicator Values"** (to get EMA values)
4. Save as `ohlcv.csv`

**Expected format:**
```csv
time,open,high,low,close,EMA Fast,EMA Slow
2023-01-06T19:00:00Z,1.06456,1.06482,1.06428,1.06463,1.0573,1.0568
```

Note the `Z` suffix on the timestamp!

### Step 3: Export Trades List

1. Open Strategy Tester tab
2. Click "List of Trades"
3. Export to CSV
4. Save as `trades.csv`

**Expected format:**
```csv
Trade #,Type,Date/Time,Signal,Price USD,...
1,Entry long,2023-01-06 21:00,Long,1.06463,...
```

Note: Trades CSV doesn't include `Z` suffix, but the times are UTC when
TradingView is set to `UTC (Reykjavik)`.

## Validation

Our test suite will **automatically check** for timezone issues:

### OHLCV Validation
✅ Timestamps must end with `Z`
❌ Will reject `-01:00` offsets (Azores)
❌ Will reject `-05:00`, `-04:00` (EST/EDT)
❌ Will reject any non-UTC timezone markers

### Trades Validation
✅ Plain timestamps with no offset markers (assumes UTC)
❌ Will reject `-01:00` offsets (Azores)
❌ Will reject `-05:00`, `-04:00` (EST/EDT)
❌ Will reject any non-UTC timezone markers

### Error Messages

If validation fails, you'll see a clear error message like:

```
TradingView OHLCV export has -01:00 timezone offset (Azores time)!
Found timestamp: 2023-01-06T19:00:00-01:00
Expected format: 2023-01-06T19:00:00Z (with Z suffix)

In TradingView:
1. Go to Settings (gear icon) → Chart Settings
2. Set 'Timezone' to 'UTC (Reykjavik)' (NOT 'UTC (Azores)')
3. Re-export the chart data

Note: 'UTC (Azores)' includes DST offsets (-01:00), which is incorrect.
Use 'UTC (Reykjavik)' for true UTC with no offsets.
```

## Why We Enforce This

1. **Consistency**: All data must be in the same timezone
2. **Simplicity**: Pure UTC eliminates DST complexity
3. **Standards**: ISO 8601 UTC format (`Z` suffix) is industry standard
4. **Accuracy**: No ambiguity about what time a trade occurred
5. **Testing**: Our platform uses UTC internally, so validation requires UTC

## Technical Details

### Iceland (Reykjavik) vs Azores

- **Iceland**: UTC+0 year-round (no DST)
- **Azores**: UTC-1 normally, UTC+0 during DST
- When exporting with `UTC (Azores)`, TradingView applies Azores DST rules
- This creates the `-01:00` offset during non-DST months
- **Solution**: Use `UTC (Reykjavik)` which never has DST

### ISO 8601 UTC Format

The `Z` suffix is the official ISO 8601 way to indicate UTC:
- `2023-01-06T19:00:00Z` = UTC
- `2023-01-06T19:00:00+00:00` = UTC (alternative notation)
- `2023-01-06T19:00:00-01:00` = NOT UTC (Azores DST)

## Quick Reference

| Setting | OHLCV Format | Trades Format | Status |
|---------|--------------|---------------|--------|
| UTC (Reykjavik) | `...Z` | `2023-01-06 21:00` | ✅ Correct |
| UTC (Azores) | Mixed `Z` and `-01:00` | `2023-01-06 21:00` | ❌ Wrong |
| Exchange | Varies | Varies | ❌ Wrong |
| EST/EDT | `...-05:00` | `2023-01-06 16:00` | ❌ Wrong |

## Troubleshooting

### "My data has -01:00 in some timestamps"
→ You used `UTC (Azores)`. Change to `UTC (Reykjavik)` and re-export.

### "My timestamps don't have Z suffix"
→ OHLCV must have `Z`. Trades CSV doesn't need it, but OHLCV does.
   Re-export OHLCV with `UTC (Reykjavik)` setting.

### "Tests fail with 'non-UTC timezone offset'"
→ Your TradingView timezone is not set to `UTC (Reykjavik)`.
   Change it and re-export all data.

## Summary

**Always use `UTC (Reykjavik)` when exporting TradingView data for golden validation tests.**

This ensures:
- ✅ Pure UTC timestamps (no DST complications)
- ✅ Standard ISO 8601 format with `Z` suffix
- ✅ Consistency across all exported data
- ✅ Compatibility with our validation test suite
