# End-to-End Research & Model Governance Plan

## 1. Overview

This document outlines a complete, iterative workflow for strategy research, from data preparation to live deployment. It incorporates principles of model governance, validation, and efficient experimentation to manage complexity and ensure robustness.

---

## 2. The Research Lifecycle

The process is broken down into distinct, sequential phases. Each phase has a clear goal, a set of actions, and a defined outcome that feeds into the next phase.

### Phase 0: Data Preparation & Quality Assurance

*   **Goal:** Ensure all historical data is clean and reliable before any experimentation.
*   **Actions:**
    1.  **Verify Data Integrity:** Check raw data for gaps, corrupted files, or timestamp inconsistencies.
    2.  **Define `global.yaml`:** Populate `config/features/global.yaml` with the comprehensive, multi-timeframe feature set required for all ML models.
    3.  **Establish Costs:** Configure realistic commission and slippage settings in the backtester to ensure results are not overly optimistic.

### Phase 1: Foundational Data Generation

*   **Goal:** Create a baseline dataset covering a wide range of market conditions and strategy parameters.
*   **Actions:**
    1.  **Define Meta-Campaign:** Create a `meta-campaign.yaml` file. **Crucially, start with a small, representative subset** to manage computational cost (e.g., 1-2 years of data, 2-3 instruments, and only the `15min` and `1H` timeframes).
    2.  **Generate & Run:** Execute `tp meta-campaign-plan` and run the generated campaigns.
    3.  **Review & Publish:** Manually review and publish the data to `master_trade_log.parquet`.
*   **Outcome:** A foundational dataset ready for initial model training.

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
    1.  Analyze the results of the "no risk" campaigns from Phase 1 using the `pnl_no_risk` diagnostic model.
    2.  Examine the features of the top-performing trades to form a hypothesis for a regime filter (e.g., "EMA crossover works best when H4 trend is up").
*   **Outcome:** A data-driven hypothesis for a regime filter.
*   **Decision Point:** If no clear patterns emerge, **STOP**. The entry signal may be flawed. Re-evaluate the baseline strategy or return to Phase 0 to add more features.

### Phase 4: Iterative Optimization & Validation

This phase uses a focused, incremental workflow to test hypotheses without re-running the entire grid.

*   **Goal:** Refine the strategy with risk parameters and predictive filtering.
*   **Actions:**
    1.  **Create Focused Campaign:** Create a new, small `meta-campaign.yaml` to test the regime hypothesis from Phase 3. This campaign will now use a "with risk" profile, iterating through different `rem_params` (stops and take-profits).
    2.  **Run & Analyze:** Execute this small campaign on a held-out validation set (e.g., a new year of data not used in foundational training).
    3.  **Optimize Predictive Filter:** Once a good risk strategy is found, create another small campaign to optimize the `profitability_threshold`. This campaign should also test `max_std` thresholds using the `predict_with_confidence` method to discard high-uncertainty predictions.
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

---

## 6. Model Governance & Deployment

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
