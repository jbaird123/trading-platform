# Trade Context Validation Script

## Overview

The `validate_trade_context_against_cache.py` script validates that all `context_at_entry` and `context_at_exit` features in the master trade log match the corresponding records in the global feature cache.

## Purpose

This ensures data integrity and consistency between:
- The enriched trade log (`data/dvc/processed/training_sets/master_trade_log.parquet`)
- The global feature cache (`data/cache/global_features/eurusd/...`)

## Usage

### Basic validation (all trades):
```bash
poetry run python scripts/validate_trade_context_against_cache.py
```

### Sample validation (faster testing):
```bash
poetry run python scripts/validate_trade_context_against_cache.py --sample-size 100
```

### Show detailed mismatches:
```bash
poetry run python scripts/validate_trade_context_against_cache.py \
    --sample-size 10 \
    --show-mismatches
```

### Generate detailed report:
```bash
poetry run python scripts/validate_trade_context_against_cache.py \
    --output workspace/validation_report.csv
```

### Adjust tolerance for floating point comparison:
```bash
poetry run python scripts/validate_trade_context_against_cache.py \
    --tolerance 1e-5
```

## How It Works

For each trade in the master trade log:

1. **Match by timeframe**: Identifies the appropriate cache file based on `execution_timeframe`
   - 5min → `5min.parquet`
   - 15min → `15min.parquet`
   - 1H → `1h.parquet`
   - 4H → `4h.parquet`
   - 1D → `1d.parquet`

2. **Entry validation**:
   - Finds cache record where `available_at` == `entry_time`
   - Compares all `context_at_entry_global_features_*` columns
   - Reports matches, mismatches, and missing records

3. **Exit validation**:
   - Finds cache record where `available_at` == `exit_time`
   - Compares all `context_at_exit_global_features_*` columns
   - Reports matches, mismatches, and missing records

4. **Results**:
   - Counts total features checked
   - Reports match rate percentage
   - Identifies trades with validation issues
   - Optionally saves detailed report to CSV

## Output

### Console Summary
```
Validation Summary
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Metric                  ┃  Value ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ Total Trades            │    367,733 │
│ Fully Validated Trades  │    325,412 │
├─────────────────────────┼────────┤
│ Entry Context           │        │
│   Features Checked      │ 96,543,291 │
│   Matches               │ 94,123,456 │
│   Match Rate            │ 97.49% │
│   Missing Cache Records │      0 │
├─────────────────────────┼────────┤
│ Exit Context            │        │
│   Features Checked      │ 96,543,291 │
│   Matches               │ 95,234,567 │
│   Match Rate            │ 98.64% │
│   Missing Cache Records │      0 │
└─────────────────────────┴────────┘
```

### CSV Report (when using --output)
Contains one row per trade with:
- `trade_idx`: Index in the trade log
- `timeframe`: Execution timeframe
- `entry_time`, `exit_time`: Trade timestamps
- `entry_valid`, `exit_valid`: Boolean validation status
- `entry_matches`, `entry_total`: Match counts for entry
- `exit_matches`, `exit_total`: Match counts for exit
- `entry_mismatch_count`, `exit_mismatch_count`: Number of mismatches

## Common Issues

### Small Floating Point Differences
**Symptom**: Match rate 95-99%, differences in 5th-6th decimal place

**Cause**: Floating point precision differences between when features were cached vs when trades were enriched

**Solution**: Adjust `--tolerance` parameter (default: 1e-6)

### Missing Cache Records
**Symptom**: "Missing Cache Records" > 0

**Cause**:
- Cache was rebuilt after some trades were enriched
- Timestamp mismatch between cache and trades
- Cache doesn't cover the full date range of trades

**Solution**: Rebuild cache or filter trades to cache date range

### High Mismatch Rate (< 90%)
**Symptom**: Match rate significantly below 90%

**Cause**:
- Feature calculation changed between cache build and trade enrichment
- Wrong cache directory specified
- Data corruption

**Solution**: Investigate specific mismatches with `--show-mismatches` flag

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--trade-log` | Path | `data/dvc/processed/training_sets/master_trade_log.parquet` | Path to trade log |
| `--cache-dir` | Path | `data/cache/global_features/eurusd/bed9c0d7...` | Path to cache directory |
| `--sample-size` | int | None (all) | Number of trades to validate |
| `--tolerance` | float | 1e-6 | Tolerance for float comparison |
| `--show-mismatches` | flag | False | Show detailed mismatch info |
| `--output` | Path | None | Path to save CSV report |

## Exit Codes

- `0`: All trades validated successfully
- `1`: Some trades have validation issues

## Performance

- **Small sample** (100 trades): ~1 second
- **Full validation** (367K trades): ~5-10 minutes
- Memory usage: ~2-3 GB (loads all cache files)

## Examples

### Quick smoke test:
```bash
poetry run python scripts/validate_trade_context_against_cache.py \
    --sample-size 1000 \
    --tolerance 1e-4
```

### Full validation with report:
```bash
poetry run python scripts/validate_trade_context_against_cache.py \
    --output analysis/cache_validation_$(date +%Y%m%d).csv \
    --tolerance 1e-5
```

### Debug specific mismatches:
```bash
poetry run python scripts/validate_trade_context_against_cache.py \
    --sample-size 20 \
    --show-mismatches \
    --tolerance 1e-7
```
