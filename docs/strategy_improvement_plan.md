# Plan: Transforming a Losing Strategy into a Winning Strategy

## 1. Objective
To systematically improve the `ema_crossover` strategy by leveraging the full analytical suite of the trading platform. The goal is to iteratively refine the strategy until it becomes consistently profitable, documenting each step of the process.

---

## 2. The Plan

### Phase 1: Establish Baseline Performance
*Goal: Create a definitive performance benchmark for the original strategy.*

1.  **Execute Baseline Backtest:**
    -   **Action:** Run the backtest for the `ema_crossover` strategy using the configuration at `configs/strategies/ema_crossover/backtest.yaml`.
    -   **Artifact:** The initial `brief.json` from the run output.
2.  **Initial AI Diagnosis:**
    -   **Action:** Run the `ai-diagnose` command on the baseline `brief.json`.
    -   **Artifact:** The initial `ai_diagnostic_report.json`.

### Phase 2: Automated Optimization & Robustness Testing
*Goal: Use the platform's automated tools to find more optimal parameters and test their robustness.*

1.  **Parameter Search:**
    -   **Action:** Configure and run a parameter search on the strategy's key parameters (e.g., `ema_fast_length`, `ema_slow_length`).
    -   **Goal:** Identify the top 3-5 most profitable parameter sets.
2.  **Walk-Forward Evaluation (WFE):**
    -   **Action:** Take the best parameter sets from the search and run a WFE on each.
    -   **Goal:** Validate the robustness of the optimized parameters and select the set that performs most consistently across different time periods.
3.  **Monte Carlo Simulation:**
    -   **Action:** Apply Monte Carlo simulation to the best-performing and most robust run from the WFE.
    -   **Goal:** Assess the strategy's sensitivity to luck and random chance.

### Phase 3: AI-Driven Diagnosis & Qualitative Review
*Goal: Generate deep, actionable insights using the platform's AI capabilities.*

1.  **Quantitative AI Diagnosis:**
    -   **Action:** Run the `ai-diagnose` command on the `brief.json` from the final, validated run in Phase 2.
    -   **Artifact:** A detailed `ai_diagnostic_report.json` with quantitative findings.
2.  **Qualitative AI Review:**
    -   **Action:** Run the `ai-diagnose` command with the `--qualitative-report` flag on the same brief.
    -   **Artifact:** An `ai_qualitative_report.md` containing human-like, narrative feedback.

### Phase 4: Iteration and Refinement
*Goal: Synthesize all findings, implement changes, and measure improvement.*

1.  **Synthesize Recommendations:**
    -   **Action:** Collate all findings from Phases 1-3: baseline performance, parameter search results, WFE results, Monte Carlo analysis, and both quantitative and qualitative AI reports.
2.  **Implement Changes:**
    -   **Action:** Based on the synthesized recommendations, create a new version of the strategy (e.g., `ema_crossover_v2.yaml`). This may involve changing parameters, adding filters (like an ADX or volume filter), or modifying exit logic.
3.  **Measure and Repeat:**
    -   **Action:** Execute the entire plan (Phases 1-3) with the new `v2` strategy.
    -   **Goal:** Compare the new baseline with the original one. If performance has improved but not met goals, repeat Phase 4. Continue this iterative process until the strategy is deemed profitable or no further improvements can be made.
