# Diagnostic RMM Automation

## Overview

### Current State
- Profitability and diagnostic models are trained via the ML pipeline and stored under `data/dvc/ml/models`.
- `ModelRegistry` is responsible for loading, saving, and routing both model families.
- Diagnostic model outputs (quintiles/probabilities) currently require manual interpretation before they influence RMM configs.
- Prior to this automation, there was no deterministic path from diagnostic insights to executable RMM YAML; experimentation relied on ad-hoc prompts or manual editing.

### Goals
- Blend deterministic automation with AI-driven exploration so that models and humans can collaborate on RMM tuning.
- Automate the translation from diagnostic model output into candidate RMM configurations.
- Provide validation tooling that backtests each candidate and summarizes performance deltas.
- Create CLI entry points so the workflow can run in CI, scheduled jobs, or ad-hoc exploratory sessions.

## Pipeline Components

### Diagnostic Context Collector (`collect_diagnostic_contexts`)
- Inputs: enriched trades (`rich_trades.parquet`) and a loaded diagnostic `ModelRegistry`.
- Actions:
  - Iterates over `(execution_timeframe, strategy_archetype)` contexts present in the data.
  - For each context, computes diagnostic probabilities and predictions.
  - Records the number of high-quintile trades and the top feature importances.
  - Captures 25th/75th percentile bounds for each top feature to seed candidate thresholds.
  - Writes `diagnostic_summary.json` under `outputs/<context>/` containing model hash, bounds, probabilities, and metadata.
- Location: `src/trading_platform/ai/pipeline/diagnostic_collector.py`.

### Candidate Rule Generator (`generate_rmm_candidates`)
- Inputs: diagnostic summaries produced by the collector.
- Actions:
  - Reads each `diagnostic_summary.json` and extracts the stored feature bounds.
  - Emits deterministic `RMMConfig` YAML files (`candidate-XXX.yaml`) under `outputs/candidates/<context>/` with `all_of` predicates using the provided ranges.
  - Writes `metadata.json` capturing candidate IDs, thresholds, and source summary hashes.
- Location: `src/trading_platform/ai/pipeline/candidate_generator.py`.

### Validation Runner (`validate_rmm_candidate`, `validate_all_candidates`)
- Inputs: candidate YAMLs, strategy configuration, enriched data, and a backtest callable.
- Actions:
  - Executes a full backtest per candidate using
    `trading_platform.backtester.run_backtest`.
  - Computes total PnL, Sharpe proxy, max drawdown, trade count, and skipped count for each run.
  - Persists `validation_report.json` alongside each candidate, plus an aggregated `validation_summary.csv` sorted by performance.
- Location: `src/trading_platform/ai/pipeline/validation_runner.py`.

## CLI Usage

Two new commands wrap the pipeline:

1. **Generate candidates**
   ```bash
   poetry run tp ai-generate-rmm-candidates \
     --enriched-path data/dvc/processed/training_sets/master_trade_log.parquet \
     --model-dir data/dvc/ml/models \
     --output-dir artifacts/rmm_automation \
     --lower-quantile 0.2 \
     --upper-quantile 0.8
   ```
   - Creates diagnostic summaries at `artifacts/rmm_automation/diagnostic_summaries/`.
   - Produces candidate YAMLs and metadata in `artifacts/rmm_automation/candidates/`.

2. **Validate candidates**
   ```bash
   poetry run tp ai-validate-rmm-candidates \
     --candidates-dir artifacts/rmm_automation/candidates \
     --strategy-config configs/strategies/bb_mean_reversion/backtest.yaml \
     --enriched-path data/dvc/processed/training_sets/master_trade_log.parquet \
     --output-dir artifacts/rmm_automation/reports \
     --data-root data/dvc/raw
   ```
   - Generates individual `validation_report.json` per context and an overall `validation_summary.csv` under the specified output directory.

Integration tests under `tests/cli/test_rmm_automation_commands.py` exercise both commands.

## Output Artifacts

- `diagnostic_summaries/<context>/diagnostic_summary.json`: model hash, top features, percentile bounds, and raw probabilities.
- `candidates/<context>/candidate-XXX.yaml`: machine-generated RMM configs for validation.
- `candidates/<context>/metadata.json`: machine-readable index of candidates and thresholds.
- `reports/<context>/validation_report.json`: metrics for each candidate after backtest execution.
- `reports/validation_summary.csv`: aggregated view of all candidates sorted by total PnL and Sharpe proxy.

## Extensibility Notes

- **Threshold heuristics**: Adjust the percentile or interpolation logic in `candidate_generator` to experiment with tighter or looser bounds (e.g., 10th/90th percentiles or adaptive ranges based on volatility).
- **Backtest integration**: Replace the stubbed backtest callable in `validation_runner` with the real `_run_backtest_simulation` once the execution layer is ready. Update metrics to include additional fields (e.g., equity curve diagnostics, regime compliance).
- **AI orchestration**: Because the pipeline is deterministic, an AI assistant can iterate by tweaking inputs (model dir, enriched slices, percentile logic) while preserving reproducibility.
- **Future enhancements**: Capture performance metadata per diagnostic model version, maintain an autogen RMM library with provenance, and feed validation outcomes back into the diagnostic models for continual learning.

## Immediate Next Steps

1. Connect the validation runner to the production backtester for realistic metrics.
2. Add richer reporting (HTML/Markdown) that highlights deltas versus baseline strategies.
3. Integrate with CI to auto-generate candidates after diagnostic models are retrained.
4. Extend the generator to support multi-stage candidate exploration (e.g., `any_of` combinations, regime labels).
5. Document success stories and tuning heuristics as we adopt the pipeline in real campaigns.
