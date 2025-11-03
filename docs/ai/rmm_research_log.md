# RMM Profitability Research Log

## Scope and End State
- **Goal**: Ship production-ready Regime & Risk Manager gating for
  trend-following strategies across `5min`, `15min`, `1H`, `4H`, and `1D`.
- **Deliverables**: Enriched master trade log with full engineered feature
  set, calibrated profitability models (regression + classifier where needed),
  validated gating thresholds, replay harness verification, updated docs, and
  CI-backed tests covering each artifact.

## Data Curation Milestones
- Rebuilt the master trade log after discovering Stage 7 publish was appending
  runs. Confirmed clean rebuild on 2025-10-29 and documented the need to delete
  the parquet before re-publishing.
- Logged campaign validations in `docs/ai/logs/campaign_audit.md`; both baseline
  and risk-managed trend campaigns now replay cleanly across all timeframes.
- Added alignment, slope, ADX, and bias feature families to the enrichment
  pipeline (`config/features/global.yaml`, registry updates) to avoid repeated
  rebuilds.

## Feature Engineering & Tooling
- Implemented deterministic alignment rule analysis producing precision,
  recall, and confusion matrices for each timeframe
  (`analysis/rmm/profitability_alignment_only/` CSVs).
- Added `scripts/rmm_analysis/evaluate_profitability_engineered_only.py` to
  train throwaway models on selected feature patterns (supports targeted A/B
  checks without touching saved artifacts).
- Authored `scripts/rmm_analysis/grid_feature_pattern_search.py` to sweep
  engineered group combinations, writing metrics and importances for offline
  study.
- Captured model variant metrics in
  `analysis/rmm/featureset_trial/selected_combos/` (threshold sweeps, equity
  summaries, feature importances).

## Modeling Experiments
- **Baseline Random Forest regressors**: retrained after each enrichment update;
  sign accuracy typically ~0.53 across contexts post-clean rebuild.
- **Alignment-only logistic model**: 15 min precision ≈ 0.32, recall ≈ 0.24,
  accuracy ≈ 0.60 (931 TP / 1 981 FP / 6 433 TN / 2 926 FN) on the corrected
  trade log, framing expectations for class imbalance.
- **Gradient Boosting profitability classifier**:
  - Added `ProfitabilityClassifierModel` (gradient boosting + balanced weights).
  - Integrated with `ModelRegistry` (save/load alongside regressors).
  - Updated `tp train-profitability-models` to train classifiers for contexts
    in `CLASSIFIER_CONTEXTS` (currently `("5min", "trend_following")`).
  - Stage 10 script now reports classifier counts once artifacts exist.
- **Model variant sweep for 5min**: Compared RF, GradientBoosting, Logistic
  Regression in `analysis/rmm/featureset_trial/selected_combos/5min_model_variants.csv`;
  gradient boosting shows higher precision at moderate recall, guiding the
  gating direction.

## Testing & Quality Gates
- Lint/typing verified for new integrations:
  - `poetry run ruff check` on `cli.py`, registry, classifier, and analysis
    scripts.
  - `poetry run mypy` on the same modules (post-cast adjustments).
- Quick-test suite was not rerun per prior agreement; full regression remains
  pending once classifier integration stabilizes.
- TODO: add unit coverage for `ProfitabilityClassifierModel` persistence and
  CLI Stage 10 classifier training; integrate into CI before production rollout.

## Outstanding Tasks Before Production
1. **Classifier Pipeline Completion**
   - Rerun Stage 10 after the next publish to emit classifier pkl artifacts.
   - Extend `ModelRegistry` tests to cover classifier serialization paths.
   - Document artifact naming and update deployment instructions.
2. **Threshold Calibration**
   - Use `threshold_recommendations.csv` and replay harness to choose per
     timeframe probability cutoffs.
   - Wire thresholds into RMM config (likely via new YAML section).
3. **Replay Verification**
   - Configure replay harness (option 1 previously selected) to simulate live
     gating for each timeframe with classifier outputs.
   - Record P&L / trade-count deltas vs baseline briefs; store results under
     `analysis/rmm/replay/`.
4. **Coverage & CI**
   - Add smoke tests for Stage 10 CLI, classifier save/load, and grid search
     helpers.
   - Ensure `scripts/run-full-ml-pipeline.sh` handles master trade log cleanup
     automatically (pending follow-up change).
5. **Documentation & Handover**
   - Expand docs on feature families and engineered group taxonomy.
   - Produce operator runbook for rerunning Stage 7/Stage 10 safely.

## Near-Term Focus by Timeframe
- **5min**: Finish gradient boosting gating, calibrate probability threshold,
  run replay harness, and backfill unit tests (highest priority).
- **15min / 1H**: Evaluate whether gradient boosting improves precision; if so,
  add to `CLASSIFIER_CONTEXTS` and repeat calibration.
- **4H / 1D**: Current precision ≥ 0.30 with RF; extend feature sweeps to confirm
  incremental value before introducing classifiers.

## Running List of Supporting Artifacts
- `scripts/rmm_analysis/evaluate_profitability_engineered_only.py`
- `scripts/rmm_analysis/grid_feature_pattern_search.py`
- `analysis/rmm/featureset_trial/` (metrics, thresholds, importances)
- `analysis/rmm/profitability_alignment_only/` (rule diagnostics)
- `src/trading_platform/ai/models/profitability_classifier.py`
- `src/trading_platform/ai/models/registry.py`
- `src/trading_platform/cli.py` (`CLASSIFIER_CONTEXTS`, Stage 10 updates)
- `scripts/run-full-ml-pipeline.sh` (Stage 10 summary & counts)

## Next Sync Checklist
- Confirm latest master trade log timestamp and checksum.
- Verify classifier artifacts exist under
  `data/dvc/ml/models/profitability_classifier/`.
- Review replay equity curves vs baseline briefs.
- Update this log with any new experiments, thresholds, or blockers.
