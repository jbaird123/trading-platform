# Canonical Timeframes Guide

We normalize every timeframe and column prefix to the canonical pandas-style labels:

| Canonical | Legacy aliases |
|-----------|----------------|
| `1min`    | `m1`, `m1_` |
| `5min`    | `m5`, `m5_` |
| `15min`   | `m15`, `m15_` |
| `30min`   | `m30`, `m30_` |
| `1h`      | `h1`, `h1_` |
| `4h`      | `h4`, `h4_` |
| `1d`      | `d1`, `d1_` |
| `1w`      | `w1`, `w1_` |

## How canonicalization is enforced

1. `trading_platform/data/timeframe_aliases.py` defines `canonicalize_timeframe` and `canonicalize_column_name`.
2. Any config/CLI input for `data_request` or `instrument.timeframe` runs through `canonicalize_timeframe`.
3. Global feature manifests, cache metadata, backtest contexts, and reports only expose canonical column names.
4. `tests/test_canonical_timeframes.py` ensures caches and contexts do not reintroduce legacy prefixes.

## Adding new timeframes

1. Add the alias to `TIMEFRAME_PREFIX_RENAMES` so `canonicalize_column_name` still works.
2. Update `compare_timeframes` (and `TIMEFRAME_RANKS`) with the canonical string.
3. Ensure `GlobalFeatureSetConfig` validators accept the new prefix.
