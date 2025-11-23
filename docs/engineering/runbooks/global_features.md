# Global Features Runbook

## Overview

This runbook documents the global feature cache system, which provides precomputed technical indicators across multiple timeframes for backtesting and strategy development.

## Canonical Global Feature Pipeline

### Purpose

The canonical global feature pipeline ensures **identical feature computation** across all contexts:
- Strategy backtesting (`compute_features()`)
- Cache building (`build_global_feature_caches()`)
- Cache validation (`validate_feature_cache.py`)

This eliminates subtle discrepancies that could lead to inconsistent backtesting results or cache invalidation issues.

**Requirements Compliance:**
- `[SYS-1.1.3]`: Data integrity and consistency across pipeline stages
- `[7. Backtester]`: Accurate feature computation for backtesting

### Architecture

The pipeline is implemented in `build_global_feature_frame()` located in:
```
src/trading_platform/core/global_feature_pipeline.py
```

**Key Responsibilities:**

1. **Timeframe Validation and Canonicalization**
   - Validates execution timeframe against supported timeframes (1min, 5min, 15min, 30min, 1h, 2h, 4h, 1d, 1w)
   - Canonicalizes timeframe aliases (e.g., "1H" → "1h", "5T" → "5min")
   - Raises `ValueError` for unsupported timeframes

2. **Efficient Timeframe Grouping**
   - Groups features by timeframe to minimize resampling operations
   - Processes base-timeframe features directly on input data
   - Resamples higher-timeframe groups once per timeframe

3. **OHLC Aggregation**
   - Correctly resamples OHLCV data for higher timeframes
   - Respects session boundaries (24hr Forex, 17hr Equity)
   - Preserves data alignment with `available_at` timestamps

4. **Indicator Computation**
   - Looks up indicators from unified registry (`INDICATORS`)
   - Handles single-column outputs (EMA, RSI, ATR)
   - Handles multi-column outputs (BB, MACD, ADX)
   - Supports parameter substitution (`${param_name}` placeholders)

5. **NaN Guard Tracking**
   - Tracks first valid timestamp per feature
   - Returns metadata: `{"valid_start": {column: timestamp}}`
   - Used to prevent lookahead bias in backtesting

6. **Index Alignment**
   - Aligns all features to market data index
   - Shifts higher-timeframe indices by timeframe delta
   - Forward-fills to base timeframe for availability semantics

### Usage

**In Strategy Code:**
```python
from trading_platform.core.global_feature_pipeline import build_global_feature_frame

feature_defs = [
    {"name": "5min_ema_20", "type": "EMA", "params": {"length": 20}, "timeframe": "5min"},
    {"name": "15min_rsi_14", "type": "RSI", "params": {"length": 14}, "timeframe": "15min"},
]

features_df, metadata = build_global_feature_frame(
    market_data=df_1min,
    feature_defs=feature_defs,
    execution_timeframe="5min"
)

# metadata["valid_start"]["5min_ema_20"] = Timestamp('2023-01-01 00:20:00+0000')
```

**In Cache Builder:**
```python
from trading_platform.core.global_features_cache import build_global_feature_caches

descriptor = build_global_feature_caches(
    symbol="EURUSD",
    data_root=data_root,
    config_path=manifest_path,
    timeframes=["5min", "15min", "1h"],
    overwrite=True,
    cache_root=cache_root,
)
```

The cache builder internally calls `build_global_feature_frame()` for each timeframe, ensuring consistency.

## Manifest Digest Contract

### Purpose

The **manifest digest** is a SHA256 hash of the feature manifest that ensures cache integrity. It prevents using stale or corrupted cached features that don't match the current manifest definition.

### How It Works

1. **During Cache Build:**
   - Computes SHA256 digest of manifest content (not file path)
   - Stores digest in `metadata.json` alongside cached features
   - Uses deterministic serialization (sorted keys, normalized types)

2. **During Cache Load:**
   - Recomputes digest from current manifest file
   - Compares against stored digest in metadata
   - Raises `ValueError` if mismatch detected

3. **Digest Computation:**
   - Handles non-JSON-serializable types (pandas Timestamps, numpy types)
   - Normalizes dictionary key ordering
   - Produces identical hashes for semantically equivalent manifests

**Implementation:**
```python
from trading_platform.core.global_features_cache import compute_manifest_digest

manifest = {
    "features": [
        {"name": "ema_20", "type": "EMA", "params": {"length": 20}, "timeframe": "5min"}
    ]
}

digest = compute_manifest_digest(manifest)
# Returns: "a3f2b8c1..." (64-character hex string)
```

### When to Rebuild Caches

**Rebuild Required When:**
- Feature definitions change (new features, modified parameters)
- Feature timeframes change
- Indicator implementations change (registry updates)
- Data source changes (new CSV files, extended history)

**Rebuild NOT Required When:**
- Manifest comments change
- Manifest formatting changes (whitespace, key ordering)
- Unrelated code changes

**How to Rebuild:**
```bash
# Rebuild all timeframes for a symbol
poetry run python -m trading_platform.core.global_features_cache \
    --symbol EURUSD \
    --config-path configs/global_features.yaml \
    --timeframes 5min 15min 1h 4h \
    --overwrite
```

**Error Message on Digest Mismatch:**
```
ValueError: Manifest digest mismatch for EURUSD/5min.
Cache was built with digest a3f2b8c1...,
but current manifest has digest d4e5f6a7....
Rebuild the cache with the current manifest.
```

## Cache Validation

### Purpose

The validation script verifies that cached features match freshly recomputed features, ensuring cache integrity before production deployment or after pipeline changes.

**Requirements Compliance:**
- `[SYS-1.1.3]`: Data integrity verification
- `[7. Backtester]`: Cache correctness for accurate backtesting

### Running Validation

**Basic Usage:**
```bash
poetry run python scripts/validate_feature_cache.py \
    --cache-dir cache/global_features \
    --symbol EURUSD \
    --timeframe 5min \
    --feature-config configs/global_features.yaml \
    --data-root data
```

**With Sampling (Faster):**
```bash
# Validate 1000 random timestamps instead of all
poetry run python scripts/validate_feature_cache.py \
    --cache-dir cache/global_features \
    --symbol EURUSD \
    --timeframe 5min \
    --feature-config configs/global_features.yaml \
    --data-root data \
    --sample-size 1000
```

**With Tolerance (For Floating Point Drift):**
```bash
# Allow up to 1e-6 numeric drift (useful for cross-platform validation)
poetry run python scripts/validate_feature_cache.py \
    --cache-dir cache/global_features \
    --symbol EURUSD \
    --timeframe 5min \
    --feature-config configs/global_features.yaml \
    --data-root data \
    --max-drift 1e-6
```

### Exit Codes

- **0**: All validations passed (cache matches recomputed features)
- **1**: Mismatches found or validation failed

### Example Output

**Successful Validation:**
```
Loading feature manifest from configs/global_features.yaml
Manifest digest: a3f2b8c1d4e5f6a7...

Loading cached features for EURUSD/5min from cache/global_features
Loaded 14400 rows, 12 columns
Validating 14400 rows

Recomputing features from market data...
Loaded 72000 rows of market data

Comparing cached vs recomputed features...

============================================================
VALIDATION PASSED: All 12 columns match
Timeframe: 5min
Rows validated: 14400
Manifest digest: a3f2b8c1d4e5f6a7...
Max drift tolerance: 1e-09
```

**Failed Validation:**
```
Loading feature manifest from configs/global_features.yaml
Manifest digest: a3f2b8c1d4e5f6a7...

Loading cached features for EURUSD/5min from cache/global_features
Loaded 14400 rows, 12 columns
Validating 14400 rows

Recomputing features from market data...
Loaded 72000 rows of market data

Comparing cached vs recomputed features...
  MISMATCH: 5min_ema_20 has 234 mismatched cells (out of 14400)
    2023-01-15 08:35:00+00:00: cached=1.0850234567, recomputed=1.0850198765, diff=3.58e-06
    2023-01-15 08:40:00+00:00: cached=1.0851123456, recomputed=1.0851087654, diff=3.58e-06
    2023-01-15 08:45:00+00:00: cached=1.0852012345, recomputed=1.0851976543, diff=3.58e-06

============================================================
VALIDATION FAILED: 1 column(s) with mismatches
Timeframe: 5min
Manifest digest: a3f2b8c1d4e5f6a7...
Max drift tolerance: 1e-09

Mismatched columns:
  - 5min_ema_20: 234 cells
```

### Integration with CI/CD

**Release Validation Workflow:**

1. **Build caches** for all symbols and timeframes
2. **Run validation** on each cache
3. **Fail deployment** if any validation fails

**Example GitHub Actions Workflow:**
```yaml
name: Validate Feature Caches

on:
  push:
    branches: [main, release/*]

jobs:
  validate:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        symbol: [EURUSD, GBPUSD, USDJPY]
        timeframe: [5min, 15min, 1h]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install

      - name: Validate cache
        run: |
          poetry run python scripts/validate_feature_cache.py \
            --cache-dir cache/global_features \
            --symbol ${{ matrix.symbol }} \
            --timeframe ${{ matrix.timeframe }} \
            --feature-config configs/global_features.yaml \
            --data-root data \
            --sample-size 1000
```

**Pre-Release Checklist:**
- [ ] All caches rebuilt with current manifest
- [ ] Validation passes for all symbols/timeframes
- [ ] No digest mismatch errors in logs
- [ ] Test coverage ≥ 100% (per `[SYS-1.10.2]`)

## Troubleshooting

### "Manifest digest mismatch" Error

**Cause:** Cache was built with different manifest than currently loaded

**Solution:**
1. Check if manifest file was recently modified
2. Rebuild cache with `--overwrite` flag
3. Verify correct manifest path is being used

### Validation Shows Mismatches

**Possible Causes:**
1. **Cache corruption** - Rebuild cache
2. **Floating point drift** - Increase `--max-drift` tolerance
3. **Indicator implementation changed** - Rebuild cache and update version
4. **Data source changed** - Rebuild cache with new data

**Debugging Steps:**
```bash
# 1. Check manifest digest
poetry run python -c "
from trading_platform.core.global_features_cache import compute_manifest_digest
import yaml
manifest = yaml.safe_load(open('configs/global_features.yaml'))
print(compute_manifest_digest(manifest))
"

# 2. Validate with verbose output
poetry run python scripts/validate_feature_cache.py \
    --cache-dir cache/global_features \
    --symbol EURUSD \
    --timeframe 5min \
    --feature-config configs/global_features.yaml \
    --data-root data \
    --sample-size 10

# 3. Rebuild cache and retry
poetry run python -m trading_platform.core.global_features_cache \
    --symbol EURUSD \
    --config-path configs/global_features.yaml \
    --timeframes 5min \
    --overwrite
```

### Cache Loading Fails

**Error:** `ValueError: No cache found for EURUSD/5min`

**Solution:**
1. Verify cache directory exists: `ls cache/global_features/eurusd/`
2. Check config_hash matches: Compare directory name to SHA256 of manifest file
3. Rebuild cache if missing

**Error:** `KeyError: Indicator type 'FOO' not found in registry`

**Solution:**
1. Check indicator name spelling in manifest
2. Verify indicator is registered in `trading_platform.strategy.indicators_registry.INDICATORS`
3. Available indicators: EMA, SMA, RSI, BB, MACD, ATR, ADX, etc.

## Related Documentation

- [Global Feature Pipeline Implementation](../../src/trading_platform/core/global_feature_pipeline.py)
- [Global Features Cache Module](../../src/trading_platform/core/global_features_cache.py)
- [Validation Script](../../scripts/validate_feature_cache.py)
- [Architecture Overview](../../architecture.md)
- [Testing Guide](../../testing_guide.md)

## Contact

For questions or issues with the global feature pipeline:
- Review test files: `tests/core/test_global_feature_pipeline.py`, `tests/core/test_manifest_digest.py`
- Check task documentation: `docs/code_tasks/active/2025-11-16_global_feature_parity.md`
