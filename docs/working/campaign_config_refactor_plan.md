# End-to-End Research & Model Governance Plan

## 1. Overview

This document outlines a complete, iterative workflow for strategy research, from data preparation to live deployment. It incorporates principles of model governance, validation, and efficient experimentation to manage complexity and ensure robustness.

The core innovation is a "meta-campaign" system that automates the creation of all campaign configurations needed to train the comprehensive suite of ML models. This system is driven by a single, high-level configuration file.

---

## 2. The Meta-Campaign System

### Two-Stage Workflow

We use a "meta-campaign" system that separates config generation from execution:

*   **Stage 1: Generation (`tp meta-campaign-plan`):** A new CLI command reads a `meta-campaign.yaml` file, calculates the cartesian product of all parameters (dates, instruments, timeframes, strategies, and their parameters), and automatically generates individual, ready-to-run campaign files.
*   **Stage 2: Execution & Review (Manual):** The user then uses existing CLI commands (`tp campaign-run`, `tp campaign-review`) to run the generated campaigns and manually verify the results before publishing.

### Setup: Create Stable Config Templates

To ensure reproducibility, we will not reference volatile files from `config/strategy/`. Instead, we use a dedicated directory for the master configurations used in data generation.

**Action:**
1.  Create a new directory: `config/master_data_generation/`
2.  Inside it, create `strategies/` and `rem/` subdirectories.
3.  Copy the baseline `ema_crossover.yaml` to `config/master_data_generation/strategies/ema_crossover_v1.yaml`.
4.  Copy the `chandelier_stop.yaml` to `config/master_data_generation/rem/chandelier_stop_v1.yaml`.

### Example Meta-Campaign Configuration

This file, `config/meta_campaigns/trend_following_data_gen.yaml`, defines the entire grid:

```yaml
# config/meta_campaigns/trend_following_data_gen.yaml

meta_campaign_id: trend_following_model_generation
description: "Generates all campaign configs needed to train all trend-following models."

run_grid:
  date_ranges:
    - { start: "2018-01-01", end: "2023-12-31" }
  instruments:
    - EUR_USD
    - GBP_USD
  execution_timeframes:
    - 1min
    - 5min
    - 15min
    - 1H
    - 4H
    - 1D

strategy_profiles:
  # Profile for data WITH defined risk.
  - name: trend_with_risk
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: config/master_data_generation/rem/chandelier_stop_v1.yaml
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10, slow_length: 20 }
        rem_params: { atr_length: 22, atr_multiplier: 2.0 }
      - strategy_params: { fast_length: 10, slow_length: 20 }
        rem_params: { atr_length: 22, atr_multiplier: 3.0 }
      - strategy_params: { fast_length: 20, slow_length: 50 }
        rem_params: { atr_length: 14, atr_multiplier: 2.5 }

  # Profile for data WITHOUT defined risk.
  - name: baseline_no_risk
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 9, slow_length: 21 }
      - strategy_params: { fast_length: 15, slow_length: 45 }
```

---

## 3. The Research Lifecycle

The process is broken down into distinct, sequential phases. Each phase has a clear goal, a set of actions, and a defined outcome that feeds into the next phase.

### Phase 0: Data Preparation & Quality Assurance

*   **Goal:** Ensure all historical data is clean and reliable before any experimentation.
*   **Actions:**
    1.  **Verify Data Integrity:** Check raw data for gaps, corrupted files, or timestamp inconsistencies.
    2.  **Define `global.yaml`:** Populate `config/features/global.yaml` with the comprehensive, multi-timeframe feature set required for all ML models.
    3.  **Establish Costs:** Configure realistic commission and slippage settings in the backtester to ensure results are not overly optimistic.

### Phase 1: Foundational Data Generation & Model Training

This is a one-time setup phase you'll repeat periodically (e.g., once a quarter) to keep models fresh.

*   **Goal:** Create a large, diverse dataset and train our foundational suite of ML models.
*   **Actions:**
    1.  **Define Meta-Campaign:** Create a `meta-campaign.yaml` file using the structure shown above. **Crucially, start with a small, representative subset** to manage computational cost (e.g., 1-2 years of data, 2-3 instruments, and only the `15min` and `1H` timeframes).
    2.  **Generate & Run:** Execute `tp meta-campaign-plan` to generate all campaign configs, then run them.
    3.  **Review & Publish:** Manually review results and publish all approved data to the `master_trade_log.parquet`.
    4.  **Train Foundational Models:** Run `tp train-profitability-models` and `tp train-diagnostic-models`.
*   **Outcome:** A rich dataset and a full suite of foundational ML models.

### Phase 2: Foundational Model Training & Validation

*   **Goal:** Train the first iteration of our models and establish performance baselines.
*   **Actions:**
    1.  **Temporal Split:** Split the master dataset into a Training Set (e.g., 80%) and a held-out Test Set (e.g., 20%).
    2.  **Train Models:** Run `tp train-profitability-models` and `tp train-diagnostic-models` using only the **Training Set**.
    3.  **Validate & Baseline:** Evaluate the newly trained models against the **Test Set**. Calculate and record baseline performance metrics (e.g., R² for the regressor, classification accuracy/F1-score for the diagnostic models). These baselines determine if the models have any predictive power at all.
*   **Outcome:** A suite of validated, baseline models with known out-of-sample performance.
*   **Decision Point:** If model performance is below a minimum threshold (e.g., R² is negative), **STOP**. The features have no predictive power. Return to Phase 0 to engineer new features.

### Phase 3: Baseline Strategy Analysis (Regime Discovery)

*   **Goal:** Use the diagnostic models to find a promising market regime for a simple baseline strategy.
*   **Actions:**
    1.  Analyze the results of the "baseline_no_risk" campaign runs from Phase 1 using the `pnl_no_risk` diagnostic model.
    2.  Specifically use the model trained on PnL for trades *without* risk (e.g., `15min_trend_following_pnl_no_risk.pkl`).
    3.  Examine the features of the top-performing trades to form a hypothesis for a regime filter (e.g., "EMA crossover works best when H4 trend is up" or "the most profitable trades occurred when the `h4_ema_50` was rising").
*   **Outcome:** A data-driven hypothesis for a market regime filter.
*   **Decision Point:** If no clear patterns emerge, **STOP**. The entry signal may be flawed. Re-evaluate the baseline strategy or return to Phase 0 to add more features.

### Phase 4: Iterative Optimization & Validation

This phase uses a focused, incremental workflow to test hypotheses without re-running the entire grid.

*   **Goal:** Refine the strategy with risk parameters and predictive filtering.
*   **Actions:**
    1.  **Create Focused Campaign:** Create a new, small `meta-campaign.yaml` to test the regime hypothesis from Phase 3. This campaign will now use a "trend_with_risk" profile, iterating through different `rem_params` (e.g., various Chandelier stop settings).
    2.  **Run & Analyze:** Execute this small campaign on a held-out validation set (e.g., a new year of data not used in foundational training). Analyze the results using the **`r_multiple` diagnostic model**.
    3.  **Optimize Predictive Filter:** Once a good risk strategy is found, create another small campaign to optimize the `profitability_threshold`. Modify the Candidate Strategy to call the `predict_profitability` model before entering a trade. The `param_grid` should iterate through different values for `profitability_threshold` (e.g., `[0.3, 0.5, 0.7, 1.0]`) and also test `max_std` thresholds using the `predict_with_confidence` method to discard high-uncertainty predictions.
*   **Outcome:** A candidate strategy with a defined entry, regime filter, stop-loss, take-profit, and a validated predictive filter threshold.
*   **Decision Point:** If the predictive filter fails to improve performance, discard it. Proceed with the best strategy found from the risk optimization step.

### Phase 5: Walk-Forward Validation

*   **Goal:** Ensure the final candidate strategy is robust and not overfit to a specific time period.
*   **Actions:**
    1.  **Define Periods:** Break the full dataset into multiple contiguous blocks (e.g., by year: 2019, 2020, 2021, 2022, 2023).
    2.  **Walk Forward:** Create a script that performs the following loop:
        *   Train models on data up to period N (e.g., 2019-2021).
        *   Run a backtest of the final candidate strategy on period N+1 (e.g., 2022).
        *   Record performance.
    3.  Repeat for all periods.
*   **Outcome:** A set of performance results across multiple out-of-sample periods. Consistent performance across periods gives high confidence in the strategy's robustness.

### Phase 6: Launch to Live Trading

*   **Goal:** Deploy the winning strategy.
*   **Action:** Take the single best configuration from Phase 5 and deploy it to the live trading engine.

---

## 4. Model Governance & Deployment

### Temporal Safety

The entire workflow is protected by the lookahead bias guardrails built into the models. The system will automatically raise an error if you attempt to run a backtest on data that overlaps with a model's training period.

### Pre-Deployment Checklist

- [ ] All foundational models meet minimum out-of-sample performance baselines.
- [ ] The final candidate strategy shows consistent positive performance across all walk-forward validation periods.
- [ ] The predictive filter threshold and uncertainty threshold (`max_std`) are justified by the results of Phase 4.
- [ ] The `git_commit` hash of the final strategy configuration is recorded.

### Live Monitoring & Retraining

*   **Monitoring:** The live performance of the deployed strategy must be tracked. Key metrics are PnL, Sharpe ratio, and drawdown.
*   **Retraining Trigger:** A full Phase 1 & 2 retrain should be initiated if live performance degrades by more than a set threshold (e.g., 20%) from backtested expectations over a statistically significant period.
*   **Frequency:** A full refresh of the foundational models should be considered on a regular basis (e.g., annually) to incorporate new market data.

---

## Implementation Status

### CLI Commands Implemented

All research workflow phases are supported by the following CLI commands:

**Phase 0: Data Validation**
- `tp validate-data --data-dir <path>` - Validate data integrity for historical price data
- Module: [src/trading_platform/data/integrity_validator.py](../../src/trading_platform/data/integrity_validator.py)
- Tests: [tests/data/test_data_integrity_validator.py](../../tests/data/test_data_integrity_validator.py)

**Phase 1: Campaign Generation**
- `tp meta-campaign-plan --config <meta-campaign.yaml>` - Generate campaign configurations
- Module: [src/trading_platform/core/meta_campaign_generator.py](../../src/trading_platform/core/meta_campaign_generator.py)
- Tests: [tests/core/test_meta_campaign_generator.py](../../tests/core/test_meta_campaign_generator.py)
- User Guide: [docs/user_guides/meta_campaign_system.md](../user_guides/meta_campaign_system.md)

**Phase 5: Walk-Forward Validation**
- `tp walk-forward-validate --strategy <config> --data <file>` - Perform walk-forward validation
- Module: [src/trading_platform/validation/walk_forward.py](../../src/trading_platform/validation/walk_forward.py)
- Tests: [tests/validation/test_walk_forward_validation.py](../../tests/validation/test_walk_forward_validation.py)

**Pre-Deployment Governance**
- `tp pre-deployment-checklist --model-metrics <json> --walk-forward-results <json> --phase4-results <json> --strategy-config <yaml>` - Validate deployment readiness
- Module: [src/trading_platform/validation/pre_deployment.py](../../src/trading_platform/validation/pre_deployment.py)
- Tests: [tests/validation/test_pre_deployment_checklist.py](../../tests/validation/test_pre_deployment_checklist.py)

### Test Coverage Achieved

- **MetaCampaignConfig**: 100% coverage (11 tests)
- **MetaCampaignGenerator**: 94% coverage (9 tests)
- **IntegrityValidator**: 85% coverage (4 tests)
- **WalkForwardValidation**: 100% coverage (4 tests)
- **PreDeploymentChecklist**: 100% coverage (7 tests)
- **Integration Tests**: 7 end-to-end tests covering full workflow

### Example Usage

**Phase 0: Validate Data**
```bash
tp validate-data --data-dir data/historical/
```

**Phase 1: Generate Campaigns**
```bash
tp meta-campaign-plan --config config/meta_campaigns/trend_following_data_gen.yaml --output-dir config/campaigns/generated/
```

**Phase 5: Walk-Forward Validation**
```bash
tp walk-forward-validate --strategy config/strategy/final.yaml --data runs/master_trade_log.parquet --periods year
```

**Pre-Deployment Checklist**
```bash
tp pre-deployment-checklist \
  --model-metrics runs/model_metrics.json \
  --walk-forward-results runs/walk_forward_results.json \
  --phase4-results runs/phase4_optimization.json \
  --strategy-config config/strategy/final.yaml
```
