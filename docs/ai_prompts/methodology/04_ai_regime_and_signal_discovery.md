# AI Prompt: Structured Regime and Signal Discovery

## 1. Your Mission

Your primary mission is to autonomously discover a profitable **trading system**, which is defined as a **combination of a strategy and the specific market regime in which it thrives**. Your goal is not just to find a good strategy, but to find the right environment for it to operate in.

This process is guided by a structured, two-stage iterative loop: **"Analyze, Filter, Compare."** You must strictly adhere to this workflow for each iteration.

---

## 2. Core Mandates & Guardrails

- **Campaign Workspace:** All work must be contained within a single campaign directory under `workspace/research/`.
- **Chronological Steps:** Every iteration must be in its own unique, timestamped subdirectory.
- **Meticulous Logging:** Every decision, hypothesis, and result must be documented in the `run_summary.md` for each step and linked in the master `campaign_log.md`.
- **Organized Outputs:** When executing a backtest, you **MUST** use the `--output-dir` argument and set it to the current iteration's directory (e.g., `.../001_ema_crossover_iteration/`) to ensure run artifacts are co-located with the research configuration.

### 2.1 Bug Detection & Reporting
-   **CRITICAL**: This platform is new and may contain bugs. You **MUST** flag unexpected behavior for investigation:
    -   Zero trades when trades are expected
    -   Crashes or validation errors
    -   Results that don't match the configuration
    -   Inconsistencies between brief.json and trades.csv
    -   Any behavior that seems illogical or incorrect
-   When you encounter unexpected behavior:
    1.  Document it in detail in the `run_summary.md`
    2.  Add an entry to `technical_debt.log` with the issue and affected iteration
    3.  Investigate whether it's a bug or expected behavior
    4.  If uncertain, flag it for the user to review

### 2.2 Standard Timeframes
-   Use only standard timeframes: `1M`, `5M`, `15M`, `30M`, `1H`, `4H`, `1D`
-   Avoid arbitrary timeframes unless there's a specific research reason

### 2.3 Research Directives from Performance Catalog

**CRITICAL:** Before any analysis, you **MUST** consult the `docs/research/strategy_performance_catalog.md` file for its top-level **"Key Research Learnings & Directives"**. You must adhere to these principles at all times.

1.  **WFE is Mandatory:** Full-backtest PnL is considered misleading. Your primary goal is to optimize out-of-sample robustness, not in-sample PnL.
2.  **Avoid Granular Filters:** Prefer broad, session-based filters over hyper-specific, hour-based rules, which are a major overfitting risk.
3.  **Filters Are Not Portable:** Never assume a profitable filter for one strategy will work for another. Every system requires independent optimization.

### 2.4 Trading Style & Frequency

-   **Target Timeframe:** You must focus your analysis on lower timeframes
    suitable for intraday trading. **Start with the `15M` timeframe.** You may
    explore `5M` if `15M` does not yield a sufficient number of trades.
-   **Minimum Trade Frequency:** The discovered trading system must generate a
    minimum number of trades to be considered valid. Over a 10-year backtest,
    the system should generate **at least 1,500 trades**. This encourages the
    discovery of systems with more opportunities and statistical significance.

---

## 3. The "Analyze, Validate, Compare" Workflow (WFE-Centric)

Your discovery process is a rigorous, three-stage loop designed to find **robust** strategies, not just profitable ones. You must prioritize out-of-sample performance over in-sample performance at all times.

### **Stage 0: Select Baseline Strategy**

1.  **Identify Candidate Strategies:** Your first step is to identify a baseline strategy to begin the analysis. The project provides several pre-built strategies in the `config/strategy/` directory (e.g., `ema_crossover.yaml`, `bb_mean_reversion.yaml`).
2.  **Select Initial Strategy:** For the first iteration of any new research campaign, you **MUST** select the `ema_crossover.yaml` strategy as your starting baseline. This ensures a consistent and reproducible starting point for all discovery efforts.
3.  **Proceed to Stage 1:** Once the baseline strategy is selected, you will proceed with the main workflow.

### Stage 1: Establish Baseline Robustness

1.  **Create Iteration Directory:** Create a new timestamped directory for this iteration (e.g., `.../001_ema_crossover_iteration/`).
2.  **Run Baseline WFE:** In a subdirectory named `baseline`, run the strategy with **no RMM filter** (`rmm_config: null`) and with `walk_forward` validation enabled in the run configuration.
    -   This establishes the strategy's **raw robustness** and out-of-sample performance.
    -   The key output is `baseline/brief.json`, specifically the `walk_forward_summary`.

### Stage 2: Dual-Track Analysis and Hypothesis Formulation

Your goal is to analyze the **baseline WFE results** to find a path to **improved robustness**.

#### Track 1: Regime Analysis (The "When")

-   **Action:** Analyze the `timing_buckets`, `contrasts`, and volatility metrics within `baseline/brief.json`. **Crucially, correlate these with the `walk_forward_summary`**. Do failing out-of-sample windows share common characteristics (e.g., low volatility, specific times of day)?
-   **Task:** Form a hypothesis about a market regime that will improve **out-of-sample performance**.
-   **CRITICAL - Justify Your Hypothesis:** You must provide a plausible, market-based explanation for why a proposed filter should improve **generalization**, not just in-sample PnL.
    -   **Good Example:** "The WFE results show that most losing windows occurred during the Asian session. This is a low-liquidity environment prone to whipsaws, which hurts this trend-following strategy. I will propose an RMM filter to exclude these hours, expecting it to improve the percentage of profitable forward windows."
    -   **Bad Example (Overfitting):** "The single best hour in the full backtest was 18:00. I will create a filter for only 18:00." (This is likely noise and will not generalize).

#### Track 2: Signal Analysis (The "What")

-   **Action:** Analyze `context_at_entry` in `baseline/brief.json`. Your
    primary focus here is to **contrast the context of winning vs. losing
    trades, specifically within the out-of-sample (OOS) windows**. This will
    help isolate the conditions that cause the strategy to fail on unseen data.
-   **Action:** **Prioritize analysis of `contextual_features` if they exist in the `RunConfig`.** These features (e.g., `ATR`, `RSI`, `Volume`) were included specifically for this analysis. Look for patterns where winning or losing trades correlate with these contextual indicators, even if the strategy does not use them in its logic.
-   **Action:** Check the `costs` section of `baseline/brief.json`. If the
    `avg_pnl_per_trade` is not significantly greater than the
    `avg_cost_per_trade`, the strategy may be too sensitive to transaction
    costs. Flag this as a potential fragility concern in your analysis.
-   **Task:** Form a hypothesis about a signal refinement that will make the strategy more robust.
-   **Example:** "Losing WFE windows are characterized by low ADX values. The strategy is entering trades when the trend is too weak to generalize to new data. I will propose adding `adx > 25` as a required entry condition to improve robustness."
-   **Example:** "The `RunConfig` included `ATR(14)` as a contextual feature. Analysis of `context_at_entry` shows that losing trades consistently occur when the normalized ATR is in the bottom 20th percentile. This suggests the strategy fails in low-volatility environments. I will propose adding a new RMM filter to block trades when volatility is low."

#### Formulate Hypothesis and Validate

1.  **Formulate a Unified Regime Hypothesis:** Combine insights into a single, composite regime designed to improve **robustness**.
    -   **CRITICAL: Adhere to the Research Directives.** Consult `docs/research/strategy_performance_catalog.md`. Avoid granular, hour-specific filters. Prefer broad, session-based filters. Do not assume filters are portable.
2.  **State Hypothesis:** In your `run_summary.md`, clearly state your hypothesis in terms of **improving robustness**. Example: "My hypothesis is that this strategy's robustness will improve by filtering for the high-liquidity London/NY sessions and requiring ADX > 25. This should increase the percentage of profitable forward windows."
3.  **Implement:** Create a `refinement_01` subdirectory with the new `rmm.yaml` or modified `strategy.yaml`.
4.  **Run Refinement WFE:** Execute the backtest with the new configuration, ensuring `walk_forward` validation is enabled. The output will be `refinement_01/brief.json`.

### Stage 3: Compare Robustness and Conclude

1.  **Compare WFE Results:** Your final task is a side-by-side comparison of the `walk_forward_summary` from the `baseline` and `refinement` runs. Full-backtest PnL is a secondary, informational metric.
2.  **Document Verdict:** In your `run_summary.md`, answer the following based on **out-of-sample metrics**:
    -   Did the change improve the `% Profitable Windows`?
    -   Did it reduce the `Performance Degradation` between in-sample and out-of-sample PnL?
    -   Was the robustness hypothesis validated?
    -   **Plan for Next Iteration:** "The WFE results confirm the filter improved robustness by +15 percentage points. This will be the new baseline. Next, I will investigate..." or "The filter did not improve out-of-sample performance, despite a higher full-backtest PnL. I will discard it and test my signal refinement hypothesis."
3.  **Know When to Pivot:** If after 3-5 iterations, no significant progress
    has been made in improving the **WFE metrics**, the strategy is not robust
    and you must pivot to a new one. "Significant progress" is defined as a
    cumulative improvement of at least 5 percentage points in
    `% Profitable Windows` over three consecutive iterations.
    -   **Optional: Final Hypothesis Generation.** If you are stuck after 3
        failed iterations, you may run the `ai-diagnose --qualitative-report`
        command on the baseline run as a final attempt to generate a new
        hypothesis. Document any insights from this report. If this does not
        lead to a successful refinement on the next iteration, you **MUST**
        pivot.

This completes one full iteration. The winning configuration from this iteration becomes the baseline for the next.

---

## 4. Iteration Summary Template

Use this template for each iteration's `run_summary.md`:

```markdown
# Iteration X: [Brief Description]

## 1. Baseline Performance

-   **Run:** `baseline/`
-   **Key Metrics:** PnL: $X, Sharpe: Y, Max DD: Z%

## 2. Dual-Track Analysis of Baseline

### Regime Analysis (The "When")
-   **Observation:** [e.g., Profitability is highly concentrated in the 13:00-16:00 UTC window.]
-   **Proposed Explanation:** [e.g., This corresponds to the high-volume NY/London overlap.]

### Signal Analysis (The "What")
-   **Observation:** [e.g., Winning trades consistently have a higher ADX at entry.]
-   **Proposed Explanation:** [e.g., The entry signals are more reliable in strong trends.]

## 3. Hypothesis for this Iteration

-   **Primary Hypothesis:** [e.g., Applying a time-based RMM filter for the NY/London overlap will significantly improve the risk-adjusted return.]
-   **Chosen Action:** Regime Filtering.

## 4. Refinement Test

-   **Run:** `refinement_01/`
-   **Configuration Change:** [e.g., Added rmm.yaml with a time-of-day filter.]

## 5. Comparison and Verdict

| Metric                 | Baseline | Refinement | Change |
|------------------------|----------|------------|--------|
| Total PnL              | $X       | $Y         | +Z%    |
| Sharpe Ratio           | A        | B          | +C%    |
| Max Drawdown           | D%       | E%         | -F%    |
| Max Drawdown Duration  | D days   | E days     | -F%    |

-   **Verdict:** [e.g., Hypothesis VALIDATED. The RMM filter dramatically improved performance.]

## 6. Plan for Next Iteration

-   **Next Step:** [e.g., Use the London session filter as the new standard for this strategy. For the next iteration, I will investigate the Signal Analysis finding and test adding an ADX filter to the strategy logic.]
```

---

## 5. Success Criteria (WFE-Based)

A trading system is only considered "successful" if its **Walk-Forward Evaluation (WFE)** meets ALL of these criteria. Full-backtest metrics are for informational purposes only.

### 5.1 Primary Criterion: Robustness

-   **`% Profitable Windows` > 70%:** This is the most important metric. The strategy must be profitable in at least 7 out of 10 out-of-sample periods.
-   **`Performance Degradation` < 30%:** The drop-off between the average in-sample PnL and the average out-of-sample PnL must be minimal. A degradation > 50% indicates severe overfitting.
-   **`Total Trades` > 1,500 (over 10+ years):** The system must be active
    enough to provide a statistically significant sample size. This equates to
    roughly 3 trades per week.

### 5.2 Secondary Criteria: Out-of-Sample Performance

-   **`Out-of-Sample Sharpe Ratio` > 0.8:** The risk-adjusted return in the out-of-sample periods must be positive and reasonable.
-   **`Out-of-Sample Profit Factor` > 1.3:** Gross profits in out-of-sample periods must significantly exceed gross losses.
-   **`Worst Window PnL`:** The PnL of the single worst out-of-sample window should not represent an unacceptable risk to the portfolio.

### 5.3 Sanity Check: Full Backtest

-   **`Total PnL` > 0:** The strategy should at least be profitable on the full dataset.
-   **`Max Drawdown` < 25%:** The overall drawdown should remain within reasonable limits.
-   **`Max Drawdown Duration` < 21 days:** The time spent in a drawdown should be
    minimal. While not a primary failure criterion, strategies with extended
    drawdown periods (e.g., over a month) are generally undesirable, even if
    profitable. This metric should be formally reported in each iteration's
    comparison.
