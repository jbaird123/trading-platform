# Meta-Campaign Plan for Trend-Following Models (v3 - Final)

## 1. Objective: Automate Configuration Generation

The primary goal is to design a system that automates the creation of all campaign configurations needed to train the comprehensive suite of `trend_following` models. This system will be driven by a single, high-level configuration file.

## 2. Proposed Solution: A Two-Stage "Meta-Campaign"

We will create a "meta-campaign" system that separates config generation from execution.

*   **Stage 1: Generation (`tp meta-campaign-plan`):** A new CLI command will read a `meta-campaign.yaml` file. It will calculate the cartesian product of all parameters (dates, instruments, timeframes, strategies, and their parameters) and automatically generate individual, ready-to-run campaign files.
*   **Stage 2: Execution & Review (Manual):** The user will then use existing CLI commands (`tp campaign-run`, `tp campaign-review`) to run the generated campaigns and manually verify the results before publishing.

---

## 3. Setup: Create Stable Config Templates

To ensure reproducibility, we will not reference volatile files from `config/strategy/`. Instead, we will use a dedicated directory for the master configurations used in data generation.

**Action:**
1.  Create a new directory: `config/master_data_generation/`
2.  Inside it, create `strategies/` and `rem/` subdirectories.
3.  Copy the baseline `ema_crossover.yaml` to `config/master_data_generation/strategies/ema_crossover_v1.yaml`.
4.  Copy the `chandelier_stop.yaml` to `config/master_data_generation/rem/chandelier_stop_v1.yaml`.

---

## 4. Draft File: The Meta-Campaign Configuration

This file, `config/meta_campaigns/trend_following_data_gen.yaml`, will define the entire grid.

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

## 5. The Iterative Research Workflow

This section outlines the end-to-end process for using the platform's tools to develop a strategy.

### Phase 1: Foundational Data Generation & Model Training

This is a one-time setup phase you'll repeat periodically (e.g., once a quarter) to keep models fresh.

*   **Goal:** Create a large, diverse dataset and train our foundational suite of ML models.
*   **Actions:**
    1.  **Define `global.yaml`:** Populate `config/features/global.yaml` with a rich set of multi-timeframe indicators.
    2.  **Define `meta_campaign.yaml`:** Use the meta-campaign file defined above.
    3.  **Generate & Run:** Execute `tp meta-campaign-plan` to generate all campaign configs, then run them.
    4.  **Review & Publish:** Manually review results and publish all approved data to the `master_trade_log.parquet`.
    5.  **Train Foundational Models:** Run `tp train-profitability-models` and `tp train-diagnostic-models`.
*   **Outcome:** A rich dataset and a full suite of foundational ML models.

### Phase 2: Baseline Strategy Analysis (Finding a Good Regime)

*   **Goal:** Analyze a simple "no stop" strategy to find the ideal market conditions for its entries.
*   **How-To:**
    1.  Use the **`PerformanceDiagnosticModel`** to analyze the results of the "baseline_no_risk" campaign runs from Phase 1.
    2.  Specifically use the model trained on PnL for trades *without* risk (e.g., `15min_trend_following_pnl_no_risk.pkl`).
    3.  Examine the features of the "top quintile" trades to identify patterns (e.g., "the most profitable trades occurred when the `h4_ema_50` was rising").
*   **Outcome:** A data-driven hypothesis for a market regime filter.

### Phase 3: Risk & Regime Refinement

*   **Goal:** Find the best stop-loss strategy for our baseline entry, but only when it trades within our new, promising regime.
*   **How-To:**
    1.  Create a new, focused `meta_campaign.yaml`.
    2.  The strategy will now include a **filter condition** based on the findings from Phase 2.
    3.  The `param_grid` will iterate through different **`rem_params`** (e.g., various Chandelier stop settings).
    4.  Run this new campaign and analyze the results using the **`r_multiple` diagnostic model**.
*   **Outcome:** A "Candidate Strategy" with a defined entry, a market regime filter, and an optimized stop-loss.

### Phase 4: Predictive Model Optimization

*   **Goal:** Further improve the Candidate Strategy by using the `ProfitabilityModel` to filter trades and find the best filter threshold.
*   **How-To:**
    1.  Modify the Candidate Strategy to call the `predict_profitability` model before entering a trade. It will now have a new parameter: `profitability_threshold`.
    2.  Create another focused `meta_campaign.yaml` where the `param_grid` iterates through different values for `profitability_threshold` (e.g., `[0.3, 0.5, 0.7, 1.0]`)
    3.  Run this campaign and analyze the final performance metrics to find the optimal threshold.
*   **Outcome:** A final, fully optimized strategy with a validated predictive filter threshold.

### Phase 5: Launch to Live Trading

*   **Goal:** Deploy the winning strategy.
*   **Action:** Take the single best configuration from Phase 4 and deploy it to the live trading engine.
