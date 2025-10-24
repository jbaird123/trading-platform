# Changelog

All notable changes to the Trading Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Multi-Timeframe Contextual Features

**Summary:** Enhanced ML data curation pipeline with multi-timeframe contextual features, enabling indicators to be computed on higher timeframes (e.g., 1H, 4H, 1D) while executing strategies on base timeframes (e.g., 15m).

#### New Capabilities

- **Multi-Timeframe Feature Engine:** Features can now specify an optional `timeframe` field to compute indicators on resampled data
- **Automatic Resampling:** Feature engine automatically resamples OHLC data to higher timeframes using proper aggregation (first/max/min/last/sum)
- **Forward-Fill Alignment:** Higher-timeframe indicator values are forward-filled to base timeframe index for seamless integration
- **Efficient Caching:** Resampled DataFrames are cached per-call to avoid redundant computation when multiple features share the same timeframe
- **Full Integration:** Multi-timeframe features work transparently across backtester, trade context capture, and rich trade exports

#### Technical Implementation

**New Modules:**
- `src/trading_platform/data/resample.py`: Core resampling utility with OHLC aggregation and validation (100% test coverage)
- `tests/data/test_resample.py`: Comprehensive test suite (6 tests covering aggregation, timezone handling, error cases, warnings)
- `tests/strategy/test_multi_timeframe_features.py`: Feature engine integration tests (3 tests for alignment, caching, backwards compatibility)
- `tests/validation/test_schemas.py`: Schema validation tests (4 tests for Pydantic and JSON schema validation)

**Modified Modules:**
- `src/trading_platform/strategy/features.py`: Added timeframe grouping, caching, and resampling logic to `compute_features()`
- `src/trading_platform/core/config.py`: FeatureConfig already included optional `timeframe` field
- `scripts/generate_schemas_from_pydantic.py`: Added FeatureConfig to auto-generated schemas
- `docs/schemas/feature_config.schema.json`: Generated JSON schema with timeframe field
- `tests/backtester/test_contextual_features.py`: Added integration test verifying multi-timeframe features in trade context

**Test Results:**
- 16 new/modified tests, all passing
- 100% coverage for new `resample.py` module
- Backwards compatible: Features without `timeframe` field work unchanged
- No modifications needed to backtester or export logic (works transparently)

#### Usage Example

```yaml
contextual_features:
  # Base timeframe feature (15m)
  - name: rsi_14
    type: RSI
    params:
      length: 14

  # Higher timeframe features
  - name: h1_rsi
    type: RSI
    params:
      length: 14
    timeframe: 1h

  - name: d1_atr
    type: ATR
    params:
      length: 14
    timeframe: 1D
```

#### Documentation

- `docs/ai/05_ml_data_curation_guide.md`: Added Section 6.5 (Multi-Timeframe Contextual Features) with examples, performance considerations, and validation details
- `docs/ai/05_ml_data_curation_guide.md`: Added Section 6.6 (Migration Guide) with step-by-step instructions for existing and new campaigns
- `docs/schemas/feature_config.schema.json`: Auto-generated schema documenting timeframe field

**Migration Guide:**
For existing campaigns, simply add the `timeframe` field to relevant features in your campaign YAML. Features without `timeframe` continue to work on the base timeframe (fully backwards compatible).

### Changed - Exception Handling Improvements

**Summary:** Systematic remediation of defensive programming anti-patterns implementing "fail-fast by default" principle.

#### Breaking Changes
- **Data Loader:** Incremental data file loading errors now fail fast instead of being silently ignored. This prevents silent data corruption but may surface previously hidden errors.
- **Monte Carlo Analysis:** Now raises exceptions when analysis fails instead of silently returning `None`. Users will see clear errors if Monte Carlo fails.
- **Parameter Search:** Now raises exceptions when analysis fails instead of silently returning `None`. Users will see clear errors if parameter search fails.

#### Improvements
- **Exception Handling Policy:** Created comprehensive policy document establishing fail-fast principle and decision framework for all exception handling
- **Zero Silent Exceptions:** Eliminated all silent exception handlers (50+ improvements)
- **Logging Added:** All exception handlers now log at appropriate levels (debug/warning/error)
- **Backtester Safety:** Added fail-fast validation for corrupted data structures in backtester
- **File I/O:** Added logging for all file save failures (prices.csv, features, charts, etc.)
- **Reporting:** Added logging for analytics, chart generation, and HTML export failures
- **Better Error Messages:** Exceptions now propagate with full context for easier debugging

#### Technical Details

**Modified Files:**
- Core modules: `backtester/core.py`, `core/run.py`, `core/sweeps.py`, `core/demo.py`, `data/loader.py`, `cli.py`
- Reporting: `reporting/analytics.py`, `reporting/brief.py`, `reporting/chart_export.py`, `reporting/html_export.py`
- Tests: Updated to expect fail-fast behavior

**Test Results:**
- 1308 tests passing (all test suite)
- 0 failures
- 40 skipped

**Migration Guide:**
For existing codebases integrating with Trading Platform:
- Expect data loading errors to be raised instead of silently ignored
- Wrap Monte Carlo and Parameter Search calls in try/except if you want to handle failures gracefully
- Monitor logs for new warning/debug messages from optional features

**Documentation:**
- `docs/coding_standards/exception_handling_policy.md`: Comprehensive exception handling guidelines
- `CONTRIBUTING.md`: Added exception handling section for contributors
- `docs/code_tasks/DEFENSIVE_CODE_REMEDIATION_SUMMARY.md`: Detailed remediation report

### Benefits
- **Reliability:** Critical errors no longer hidden, easier to debug production issues
- **Debuggability:** Clear error messages with full context
- **Maintainability:** Consistent exception handling patterns across codebase
- **Visibility:** Logging provides visibility into degraded features without crashes

### Upgrade Notes
If you're upgrading from a previous version:
1. Review any try/except blocks wrapping Trading Platform calls
2. Check logs for new warning messages about degraded features
3. Data loading failures will now be visible - fix any data quality issues
4. Monte Carlo/Parameter Search failures will raise exceptions - handle or fix root cause

## [Previous Versions]

*To be added as releases are made*
