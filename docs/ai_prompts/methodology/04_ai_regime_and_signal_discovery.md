# AI Prompt: Structured Regime and Signal Discovery

## 1. Your Mission

Your primary mission is to autonomously discover a profitable **trading system**, which is defined as a **combination of a strategy and the specific market regime in which it thrives**. Your goal is not just to find a good strategy, but to find the right environment for it to operate in.

This process is guided by a structured, two-stage iterative loop: **"Analyze, Filter, Compare."** You must strictly adhere to this workflow for each iteration.

---

## 2. Core Mandates & Guardrails

- **Campaign Workspace:** All work must be contained within a single campaign directory under `workspace/research/`.
- **Chronological Steps:** Every iteration must be in its own unique, timestamped subdirectory.
- **Meticulous Logging:** Every decision, hypothesis, and result must be documented in the `run_summary.md` for each step and linked in the master `campaign_log.md`.
- **Bug Reporting:** You must be vigilant in identifying and logging potential platform bugs in the `technical_debt.log`.

---

## 3. The "Analyze, Filter, Compare" Workflow

Each iteration of your discovery process consists of two primary stages. You will first establish a baseline, then analyze it to form a hypothesis, and finally test that hypothesis against the baseline.

### Stage 1: Establish Baseline

1.  **Create Iteration Directory:** Create a new timestamped directory for this full iteration (e.g., `.../001_ema_crossover_iteration/`). All files for this iteration will live here.
2.  **Run Baseline Backtest:** In a subdirectory named `baseline`, run the strategy with **no RMM filter** (`rmm_config: null`).
    -   This action establishes the strategy's raw performance across all market conditions.
    -   The output will be `baseline/brief.json`.

### Stage 2: Dual-Track Analysis and Refinement

Your primary goal is now to analyze `baseline/brief.json` to find a path to improvement. You must investigate two tracks simultaneously.

#### Track 1: Regime Analysis (The "When")

-   **Action:** Analyze the `timing_buckets` (hour_of_day, day_of_week), `contrasts` (long vs. short), and volatility metrics within the baseline `brief.json`.
-   **Task:** Identify the most profitable and unprofitable conditions. Your goal is to form a hypothesis about the ideal **market regime**.
-   **CRITICAL - Justify Your Hypothesis:** You must provide a plausible, market-based explanation for why a proposed filter should work. This is to prevent curve-fitting.
    -   **Good Example:** "The data shows profitability is concentrated between 13:00-16:00 UTC. This corresponds to the London/New York session overlap, which is typically characterized by high liquidity that should benefit this strategy. I will propose an RMM filter for this window."
    -   **Bad Example:** "Trades at 2:00 PM are profitable. I will filter for 2:00 PM."

#### Track 2: Signal Analysis (The "What")

-   **Action:** Analyze the `context_at_entry` and `context_at_exit` fields for all trades in `baseline/brief.json`.
-   **Task:** Compare the indicator values for winning trades versus losing trades. Your goal is to form a hypothesis about how to **refine the strategy's own logic**.
-   **Example:** "Winning trades consistently have an ADX value above 30 at entry, while many losing trades have an ADX below 20. This suggests the strategy suffers when the trend is weak. I will propose adding `adx > 30` as a required entry condition."

#### Formulate Hypothesis and Test

1.  **Prioritize:** Based on your dual-track analysis, decide which path offers the most promising improvement: Regime Filtering or Signal Refinement.
2.  **State Hypothesis:** In your `run_summary.md`, clearly state your hypothesis. For example, "My primary hypothesis is that this strategy is only profitable during the London session. I will test this by creating an RMM filter."
3.  **Implement:** Create a new subdirectory named `refinement_01`. Inside this directory, place the new configuration files (`rmm.yaml` or an updated `strategy.yaml`).
4.  **Run Refinement Backtest:** Execute the backtest with the new configuration. The output will be `refinement_01/brief.json`.

### Stage 3: Compare and Conclude

1.  **Compare Results:** Your final task for the iteration is to perform a side-by-side comparison of `baseline/brief.json` and `refinement_01/brief.json`.
2.  **Document Verdict:** In your `run_summary.md`, answer the following questions:
    -   Did the change improve the target metrics (Sharpe Ratio, PnL, Max Drawdown)?
    -   Was the hypothesis validated?
    -   Based on the result, what is the plan for the next iteration? (e.g., "The RMM filter was highly effective. I will now use this filtered result as the baseline for the next iteration and investigate signal refinement.", or "The RMM filter did not improve performance. I will discard it and test my signal refinement hypothesis next.")

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

| Metric        | Baseline | Refinement | Change |
|---------------|----------|------------|--------|
| Total PnL     | $X       | $Y         | +Z%    |
| Sharpe Ratio  | A        | B          | +C%    |
| Max Drawdown  | D%       | E%         | -F%    |

-   **Verdict:** [e.g., Hypothesis VALIDATED. The RMM filter dramatically improved performance.]

## 6. Plan for Next Iteration

-   **Next Step:** [e.g., Use the London session filter as the new standard for this strategy. For the next iteration, I will investigate the Signal Analysis finding and test adding an ADX filter to the strategy logic.]
```

---

## 5. Success Criteria (ABSOLUTE REQUIREMENTS)

A trading system is only considered successful and ready for formal validation if it meets **ALL** of these criteria over a significant backtest period (e.g., from `2013-01-01` to present).

### 5.1 Profitability
-   `total_pnl` > 0 (must be profitable)

### 5.2 Risk Management
-   `max_drawdown` < 20% of total PnL
-   **Maximum Drawdown Period**: The primary target is a maximum drawdown period of **less than 2 weeks**. A slightly longer period (e.g., 3 weeks) may be acceptable only if other metrics are exceptionally strong, but the goal is to avoid prolonged periods of losses.
    -   **Calculation Note**: The drawdown period calculation **MUST** exclude inactive periods where trading is blocked by a filter (e.g., an RMM policy). The clock "pauses" when the system is intentionally sidelined.

### 5.3 Risk/Reward
-   Sharpe Ratio > 1.0
-   Reward/Risk Ratio (Avg Win / Avg Loss) > 1.0

### 5.4 Consistency & Reliability
-   **Profit Factor** (Gross Profit / Gross Loss) > 1.5. This demonstrates that winning trades significantly outweigh losing trades.
-   **Low PnL Volatility**: The standard deviation of trade PnL should be low relative to the average PnL, indicating consistent, predictable returns rather than infrequent large windfalls.

### 5.5 Statistical Significance & Robustness
-   Sufficient number of trades to be statistically meaningful (typically 30+ trades).
-   Performance must be consistent across different time periods and market regimes identified during analysis.
-   The final system must pass a formal Walk-Forward Evaluation (WFE) during the validation phase to prove it is not curve-fit.

---

## 6. Final Goal

Your objective is to repeat this workflow until you produce a trading system that meets all the project's success criteria (Sharpe > 1.0, passing WFE, etc.). Once such a system is found, you may proceed to the formal Validation and Promotion phases outlined in the other methodology documents.
