# Changelog

All notable changes to the Trading Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Campaign Runner

**Summary:** Automated backtest orchestration system for systematic ML training data generation. Implements complete Section 6 workflow from ML Data Curation Guide with full provenance tracking, quality gates, and automated DVC publishing.

#### Key Features

- **Campaign YAML Configuration**: Declarative campaign definitions with parameter matrices and multi-timeframe features
- **Full Provenance Tracking**: Captures git commit, poetry.lock SHA256, Python version, platform, DVC version, and **data snapshot ID**
- **Batch Execution Engine**: Automated backtest execution with progress tracking and comprehensive failure artifact generation
- **Artifact Collection**: Prescribed `data/candidates/<campaign_id>/` structure with metadata extraction and indexing
- **Complete Quality Gates**:
  - Schema validation
  - Data quality checks
  - Minimum trades threshold (5)
  - Duplicate trade ID detection
  - Max drawdown limit (50%)
  - **Indicator registry validation** (ensures all features registered)
  - **Drift monitoring** (KS-statistic vs baseline, threshold 0.15)
  - **Audit log updates** (`docs/ai/logs/campaign_audit.md`)
- **Three-State Review Workflow**: `approved`, `rejected`, `needs-rework` with **campaign-level** `decision.yaml`
- **Enrichment Stage**: Creates intermediate `data/enriched/<campaign_id>/rich_trades.parquet` with campaign metadata
- **Automated DVC Publishing**: Publishes to master trade log with automatic `dvc add` and `dvc push`
- **Full Audit Trail**: SHA256 checksums, curation history, and audit logging

#### New Modules

**Core Implementation:**
- `src/trading_platform/ai/campaigns/models.py`: Pydantic models for campaigns, plans, provenance, results (100% coverage)
- `src/trading_platform/ai/campaigns/provenance.py`: Provenance metadata capture with DVC data snapshots (100% coverage)
- `src/trading_platform/ai/campaigns/planner.py`: Campaign plan generation from YAML (100% coverage)
- `src/trading_platform/ai/campaigns/runner.py`: Batch execution engine with failure handling (100% coverage)
- `src/trading_platform/ai/campaigns/collector.py`: Artifact collection to prescribed folder structure (100% coverage)
- `src/trading_platform/ai/campaigns/validator.py`: Complete quality gates with drift monitoring and audit logging (100% coverage)
- `src/trading_platform/ai/campaigns/review.py`: Three-state review workflow (100% coverage)
- `src/trading_platform/ai/campaigns/enrichment.py`: Intermediate dataset creation (100% coverage)
- `src/trading_platform/ai/campaigns/publisher.py`: Master trade log publishing with automated DVC tracking (100% coverage)

**Test Suites:**
- `tests/ai/campaigns/test_campaign_models.py`: 7 tests for campaign configuration validation
- `tests/ai/campaigns/test_planner.py`: 7 tests for plan generation and provenance
- `tests/ai/campaigns/test_runner.py`: 9 tests for batch execution
- `tests/ai/campaigns/test_collector.py`: 6 tests for artifact collection
- `tests/ai/campaigns/test_validator.py`: 16 tests for complete quality gates (including drift monitoring, indicator registry, audit logging)
- `tests/ai/campaigns/test_review.py`: 7 tests for review workflow
- `tests/ai/campaigns/test_enrichment.py`: 6 tests for enrichment stage
- `tests/ai/campaigns/test_publisher.py`: 7 tests for publishing with DVC automation
- `tests/cli/test_cli.py`: 9 tests for CLI commands

**Documentation:**
- `docs/ai/06_campaign_runner_guide.md`: Complete usage guide with CLI reference
- `docs/ai/05_ml_data_curation_guide.md`: Updated Section 6 with implementation reference
- `src/trading_platform/ai/campaigns/README.md`: Module overview and quick start
- `config/campaigns/example_trend_following_15m.yaml`: Example campaign configuration

#### CLI Commands

Nine new commands for complete workflow automation:

```bash
tp campaign-plan --config <yaml>              # Generate execution plan
tp campaign-run --campaign-id <id>            # Execute all runs
tp campaign-validate --campaign-id <id>       # Run quality gates
tp campaign-review --campaign-id <id>         # Generate review report
tp campaign-approve --campaign-id <id> --run-id <run> --notes <notes>
tp campaign-reject --campaign-id <id> --run-id <run> --reason <reason>
tp campaign-needs-rework --campaign-id <id> --run-id <run> --reason <reason> --suggestions <suggestions>
tp campaign-enrich --campaign-id <id>         # Create enriched dataset
tp campaign-publish --campaign-id <id>        # Publish to master trade log
```

#### Quality Gate Details

All validation checks required by Section 5.3 of the ML Data Curation Guide:

1. **Schema Validation**: Required fields (meta, trades, backtest_metrics)
2. **Data Quality**: No NaN values or data corruption
3. **Minimum Trades**: At least 5 trades per candidate
4. **Duplicate Detection**: No duplicate trade IDs
5. **Max Drawdown**: Maximum drawdown < 50%
6. **Indicator Registry**: All contextual features registered in `indicators_registry.py`
7. **Drift Monitoring**: Kolmogorov-Smirnov statistic vs baseline < 0.15 (warning if exceeded)
8. **Audit Logging**: All validation actions logged to `docs/ai/logs/campaign_audit.md`

#### Alignment with ML Data Curation Guide

Implements all requirements from Section 6:

- ✅ **Section 5.2**: Candidate submission workflow with campaign-level decision.yaml (lines 114-118)
- ✅ **Section 5.3**: Complete quality gates (schema, dedupe, drift KS-stat check, audit logging) (lines 133-143)
- ✅ **Section 6.1**: Campaign runner with full provenance including data version (line 164)
- ✅ **Section 6.4**: Failure handling with failure_report.json and campaign_complete.yaml
- ⚠️ **Section 5.4**: Manual overrides (NOT IMPLEMENTED - future work, requires `data/overrides/<campaign_id>.yaml`)

#### Test Coverage

- **Total tests**: 65+ tests across 9 test modules
- **Coverage**: 100% for entire campaigns module
- **Pre-commit hooks**: All code passes ruff, mypy, and formatting checks

#### Usage Example

```bash
# 1. Create campaign YAML
cat > config/campaigns/my_campaign.yaml <<EOF
campaign_id: my_campaign
strategy_path: config/strategy/ema_crossover.yaml
execution_timeframe: 15m
strategy_archetype: trend_following
run_matrix:
  - instrument: EURUSD
    start_date: "2023-01-01"
    end_date: "2023-12-31"
contextual_features:
  - name: h1_rsi
    type: RSI
    params: {length: 14}
    timeframe: 1h
EOF

# 2. Execute complete workflow
tp campaign-plan --config config/campaigns/my_campaign.yaml
tp campaign-run --campaign-id my_campaign
tp campaign-validate --campaign-id my_campaign
tp campaign-approve --campaign-id my_campaign --run-id run_001 --notes "Good metrics"
tp campaign-enrich --campaign-id my_campaign
tp campaign-publish --campaign-id my_campaign
```

#### Migration Notes

- Existing manual workflow replaced by automated CLI commands
- All provenance metadata now captured automatically
- DVC tracking no longer requires manual `dvc add`/`dvc push` commands
- Campaign-level decision tracking replaces per-run decision files

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
- `src/trading_platform/schemas/feature_config.schema.json`: Generated JSON schema with timeframe field
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
- `src/trading_platform/schemas/feature_config.schema.json`: Auto-generated schema documenting timeframe field

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
