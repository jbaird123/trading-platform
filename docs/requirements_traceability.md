# Requirements Traceability Matrix (live subset)

This matrix links implemented requirements in `docs/project_requirements.md`
to their associated tests. Entries reflect current coverage found in
`tests/` via explicit requirement tags and representative unit tests.

Note: Some historical tags use legacy numbering (e.g., `req_BT_6_4`). These
are registered and mapped to the closest current requirement.

## Data Handler (DH)
- [DH-2.1] Load CSVs (normalized schema)
  - tests/features/data_handler/data_schema.feature:7
- [DH-2.3] Normalize OHLCV schema
  - tests/features/data_handler/data_schema.feature:8
- [DH-2.4] UTC timestamp index
  - tests/features/data_handler/data_schema.feature:14
- [DH-2.5] Safe resampling OHLC aggregation
  - tests/features/data_handler/data_schema.feature:18
- [DH-2.6] Validation checks (missing/dupes/outliers)
  - tests/features/data_handler/data_schema.feature:9
  - tests/features/data_handler/data_schema.feature:19

## Strategy Engine (SE)
- [SE-3.1] Signal generation only
  - tests/features/strategy_engine/signal_generation.feature:8
  - tests/features/strategy_engine/signal_generation.feature:20
  - tests/features/strategy_engine/signal_generation.feature:32
- [SE-3.2] Base interface, flat=exit
  - tests/features/strategy_engine/signal_generation.feature:9
  - tests/features/strategy_engine/signal_generation.feature:21
  - tests/features/strategy_engine/signal_generation.feature:33
- [SE-3.9] Strategy YAML schema validation
  - tests/strategy/test_strategy_jsonschema.py:8
  - tests/strategy/test_strategy_schema_validation.py:97

## Regime Market Manager (RMM)
- [RMM-4.1] Regime labels
  - tests/features/regime_market_manager/market_regime_classification.feature:8
  - tests/features/regime_market_manager/market_regime_classification.feature:18
- [RMM-4.2] Confidence output
  - tests/features/regime_market_manager/market_regime_classification.feature:9
  - tests/features/regime_market_manager/market_regime_classification.feature:19
- [RMM-4.3] Rule-based baseline
  - tests/features/regime_market_manager/market_regime_classification.feature:10
  - tests/features/regime_market_manager/market_regime_classification.feature:20
- [RMM-4.9] RMM YAML schema validation
  - tests/regime_market_manager/test_rmm_jsonschema.py:8

## Backtester (BT)
- [BT-7.1] Orchestrate components (core loop)
  - tests/features/backtester/core_backtest.feature:9
- [BT-7.3] Iterative bar-by-bar loop
  - tests/features/backtester/core_backtest.feature:10
- [BT-7.6] Tie-break policy
  - tests/backtester/test_tie_break_policy.py:14
- [BT-7.7] Warm-up period before trading
  - tests/backtester/test_warmup_bars.py:21
- [BT-7.9] Validate stop/TP fill logic
  - tests/features/backtester/risk_management.feature:12
  - tests/features/backtester/risk_management.feature:25
  - Legacy tag `@req_BT_6_4` also used in these scenarios
- [BT-7.10] Record skipped trades
  - tests/backtester/test_skipped_logging.py:1
  - tests/backtester/test_return_skips_only.py:1
- [BT-7.11] Counterfactual outcomes for skips
  - tests/backtester/test_counterfactual_skips.py:1
- [BT-7.16] Exit precedence policy
  - tests/step_defs/backtester/test_risk_management_steps.py:1
