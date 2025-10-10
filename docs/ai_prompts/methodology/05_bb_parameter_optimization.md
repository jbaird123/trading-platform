# AI Prompt: WFE-Powered Bollinger Band Optimization

## 1. Your Mission

Your primary mission is to discover the **optimal parameters for a Bollinger Band (BB) trading strategy on the 5-minute timeframe** using a Walk-Forward Evaluation (WFE) approach.

Your goal is to find the best possible configuration of the BB strategy that balances profitability with risk. You must adhere to the principle that **shorter, manageable drawdowns are preferable to larger gains with longer and deeper drawdowns**, prioritizing parameter sets that keep losses shallow even if raw profitability is modest.

This is a **WFE-powered parameter optimization** task. You must configure and run a single, comprehensive backtest that systematically sweeps through a grid of parameters, evaluating each one with a rigorous walk-forward methodology.

---

## 2. Core Mandates & Guardrails

- **Campaign Workspace:** All work must be contained within a single campaign directory under `workspace/research/`.
- **Chronological Steps:** Every iteration must be in its own unique, timestamped subdirectory.
- **Meticulous Logging:** Every decision, hypothesis, and result must be documented in the `run_summary.md` for each step and linked in the master `campaign_log.md`.
- **Organized Outputs:** When executing a backtest, you **MUST** use the `--output-dir` argument and set it to the current iteration's directory to ensure run artifacts are co-located with the research configuration.

### 2.1 Bug Detection & Reporting
-   **CRITICAL**: This platform is new and may contain bugs. You **MUST** flag unexpected behavior for investigation:
    -   Zero trades when trades are expected
    -   Crashes or validation errors
    -   Results that don't match the configuration
    -   Inconsistencies between `brief.json` and `trades.csv`
    -   Any behavior that seems illogical or incorrect
-   When you encounter unexpected behavior:
    1.  Document it in detail in the `run_summary.md`
    2.  Add an entry to a `technical_debt.log` with the issue and affected iteration
    3.  Investigate whether it's a bug or expected behavior
    4.  If uncertain, flag it for the user to review

### 2.2 Research Directives from Performance Catalog
**CRITICAL:** Before any analysis, you **MUST** consult the `docs/research/strategy_performance_catalog.md` file for its top-level **"Key Research Learnings & Directives"**. You must adhere to these principles at all times. The most important of these is:
-   **WFE is Mandatory:** Full-backtest PnL is considered misleading. Your primary goal is to optimize out-of-sample robustness, not in-sample PnL.

### 2.3 Trading Style & Frequency
-   **Target Timeframe:** You must focus your analysis exclusively on the **`5M` timeframe.**
-   **Trade Frequency Guideline:** The ideal strategy should demonstrate consistent activity. A system that trades only a handful of times over the entire backtest is not useful. Use trade frequency as a qualitative measure to break ties between otherwise similar results.

### 2.4 Financial Configuration
-   **Initial Cash:** All backtests must be configured with an initial cash investment of **$10,000**.
-   **Position Sizing:** The size of each position taken must be fixed at **$10,000**.

---

## 3. The "Configure, Execute, Analyze" Workflow

### Stage 1: Configure the WFE-Powered Sweep

1.  **Create Iteration Directory:** Create a new timestamped directory for this iteration (e.g., `.../001_bb_wfe_optimization/`).
2.  **Create Run Configuration:** Inside this directory, create a new YAML run configuration file (e.g., `wfe_sweep_config.yaml`).
3.  **Set Baseline Configuration:**
    -   Set `strategy_path` to `config/strategy/bb_mean_reversion.yaml`.
    -   Set the `timeframe` in the `data_request` section to `5M`.
4.  **Define Parameter Search Space:**
    -   In your configuration file, add a `parameter_search` section.
    -   The `objective` function may not support advanced risk-adjusted metrics directly. Set it to a simple default like `total_pnl`, as you will be performing the primary analysis manually based on WFE results.
    -   Define a `grid` for the `bb_mean_reversion.yaml` parameters: `length` and `std_dev`. You must determine and justify the ranges.
    -   **Example `parameter_search` block:**
        ```yaml
        parameter_search:
          objective: "total_pnl" # Placeholder, manual WFE analysis is primary
          seed: 42
          grid:
            length: [20, 30, 40, 50]
            std_dev: [2.0, 2.5, 3.0]
        ```
5.  **Configure Walk-Forward Evaluation:**
    -   In the same configuration file, add a `walk_forward` section.
    -   You must define a `window` (in-sample training period) and a `step` (out-of-sample testing period) in number of bars. Choose values that are appropriate for a long history of `5M` data.
    -   **Example `walk_forward` block:**
        ```yaml
        walk_forward:
          window: 8640   # Approx. 1 month of 5-min bars (30*24*12)
          step: 2880     # Approx. 10 days of 5-min bars (10*24*12)
        ```
6.  **Document Your Configuration:** Save the YAML file and document its contents and your reasoning in `run_summary.md`.

### Stage 2: Execute the Backtest

1.  **Run the Backtest:** Execute the sweep using the `run-backtest.sh` script, passing your newly created configuration file. Ensure the output is directed to your iteration directory.
    ```bash
    ./scripts/run-backtest.sh path/to/your/wfe_sweep_config.yaml --output-dir path/to/your/iteration_directory
    ```
2.  **Monitor the Run:** This may be a long-running process. The results will be saved to the output directory you specified.

### Stage 3: Analyze WFE Results and Select Optimal Candidate

1.  **Locate Results:** The output directory will contain results for each parameter combination. The key file for your analysis is `parameter_search_results.json`, which summarizes all runs, and the individual `brief.json` files for each run which contain the detailed `walk_forward_summary`.
2.  **Aggregate and Rank:**
    -   Your primary goal is to find the parameter set with the best **out-of-sample risk-adjusted return**.
    -   You **MUST** use the **Out-of-Sample Calmar Ratio** as the primary ranking metric.
    -   For each parameter set, parse the `walk_forward_summary` from its `brief.json`. From the `out_of_sample` section, extract the necessary metrics to calculate the Calmar Ratio (`total_pnl` and `max_drawdown_pct`).
    -   Calculate the Calmar Ratio. *Note: A precise annualized return calculation requires the time period; you can approximate by using the total out-of-sample return as a proxy, or by annualizing based on the total step size of your WFE.*
3.  **Analyze and Select:**
    -   Identify the top 3-5 parameter sets based on the out-of-sample Calmar Ratio (higher is better for balancing return vs. drawdown depth).
    -   From this shortlist, create a comparison table including other key **out-of-sample** metrics so you can weigh trade-offs:
        -   Total PnL
        -   Max Drawdown (%)
        -   Sharpe Ratio
        -   % Profitable Windows
        -   Total Trades / Activity
    -   Discuss the relative strengths and weaknesses of the leading candidates. You do **not** have to declare a single winner if the evidence is mixed; instead, explain how the metrics (especially Calmar, % profitable windows, and drawdown characteristics) influence your ranking.
4.  **Conclude and Report:** In your `run_summary.md`, clearly summarize the top candidates, their key out-of-sample metrics, and your reasoning for preferring or deprioritizing each option.

---

## 4. Iteration Summary Template

Use this template for your `run_summary.md`:

```markdown
# Iteration 1: Bollinger Band WFE Parameter Optimization

## 1. Configuration
-   **Strategy:** `config/strategy/bb_mean_reversion.yaml`
-   **Timeframe:** `5M`
-   **Parameter Grid:**
    -   `length`: [20, 30, 40, 50]
    -   `std_dev`: [2.0, 2.5, 3.0]
-   **WFE Config:**
    -   `window`: 8640 bars
    -   `step`: 2880 bars

## 2. Execution
-   **Command:** `...`
-   **Output Path:** `...`

## 3. Analysis of Top Candidates

| Length | Std Dev | OOS Calmar | OOS Sharpe | OOS PnL | OOS Max DD | OOS Trades | % Profitable Windows |
|--------|---------|------------|------------|---------|------------|------------|----------------------|
| 40     | 2.5     | 1.8        | 1.1        | $12,345 | 8.5%       | 152        | 75%                  |
| 50     | 3.0     | 1.6        | 0.9        | $10,987 | 9.2%       | 110        | 71%                  |
| 30     | 2.5     | 1.5        | 1.0        | $9,876  | 7.8%       | 189        | 68%                  |

## 4. Verdict and Recommendation

-   **Winning Parameters:** `length: 40`, `std_dev: 2.5`
-   **Justification:** This combination produced the highest out-of-sample Calmar Ratio, indicating the best risk-adjusted return according to the mission's primary goal. It also shows a strong Sharpe Ratio and a high percentage of profitable forward windows, suggesting robustness. The trade frequency is reasonable, providing a good balance of activity and quality.

## 5. Plan for Next Iteration
-   **Next Step:** Use the winning parameters as the new baseline for further refinement or for deployment consideration.
```

---

## 5. Ranking & Evaluation Guidelines (WFE-Based)

Your goal is to compare parameter sets holistically—there are no hard pass/fail thresholds. Instead, use these metrics to reason about trade-offs and highlight candidates that best balance reliability with acceptable return:

### 5.1 Primary Ranking Input
-   **`Out-of-Sample Calmar Ratio`:** Treat this as the anchor metric. Prefer higher Calmar values because they reward shallow drawdowns relative to return. If two candidates have similar Calmar, defer to the secondary metrics.

### 5.2 Secondary Considerations: Robustness & Profitability
-   **`% Profitable Windows`:** Favor parameter sets that maintain profitability across more WFE windows, as they indicate consistency. Lower values are acceptable if Calmar remains superior, but document the trade-off.
-   **`Out-of-Sample Sharpe Ratio`:** Use as a supporting signal for risk-adjusted return. A higher Sharpe bolsters confidence, yet a slightly lower value may be tolerable when Calmar and drawdown metrics are strong.
-   **`Performance Degradation`:** Compare in-sample vs. out-of-sample PnL to understand stability. Large degradation should raise caution, but weigh it against improved drawdown control.

### 5.3 Activity & Verification
-   **`Average Trades per Week` (Out-of-Sample):** Use to gauge whether the strategy is active enough to validate. Very low activity can indicate a brittle edge; very high activity might come with higher costs. Use as context when ranking.
-   **`Worst Window PnL`:** Examine the deepest OOS loss window to judge pain tolerance. Prefer candidates with smaller worst-window losses, especially when Calmar differences are minor.

Document how each of these factors influenced your ranking so future iterations can build on the insights.

---
