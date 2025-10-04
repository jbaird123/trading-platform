# AI Prompt: Autonomous Strategy Validation

## 1. Your Mission

Your mission is to take a "candidate" trading strategy that was identified during the **Discovery Phase** and determine if its performance is robust or an illusion of curve-fitting. You will subject the strategy to a rigorous gauntlet of validation tests.

---

## 2. Core Mandates & Guardrails

-   **Workspace Integrity:** You **MUST** work within a dedicated session directory under `workspace/strategy_validation/`. Name it with a timestamp and the candidate's name (e.g., `20251005_100000_ema_crossover_short_only_validation`).
-   **Input:** Your primary input will be the file path to the candidate strategy's configuration file (`.yaml`).
-   **Meticulous Logging:** Maintain a `session_log.md` detailing each validation step, the commands run, and the results observed.

---

## 3. The Validation Workflow

### Phase 0: Initialization

1.  **Identify Candidate Strategy:** Ask the user to provide the file path to the "winning" candidate strategy's configuration file (`.yaml`) that was generated during the Discovery Phase.
2.  **Create Workspace:** Create your unique session directory under `workspace/strategy_validation/`. Name it with a timestamp and the candidate's name.
3.  **Start Log:** Create the `session_log.md` file.
4.  **Load Candidate:** Copy the candidate strategy's `.yaml` file into your workspace.

### Phase 1: Walk-Forward Evaluation (WFE)

This is the most critical test for robustness against changing market conditions. The goal is to determine if the strategy's performance is consistent across different time periods using a **post-hoc analysis**.

1.  **Execute Baseline Backtest:** First, run a standard backtest using the candidate strategy's static parameters. This run will generate the full history of trades needed for the analysis.
2.  **Perform Post-Hoc WFA:** After the backtest is complete, use the `walk_forward_summary` function (from `src/trading_platform/core/robustness.py`) on the list of generated trades. Configure this analysis with appropriate time-based windows, for example:
    -   `window`: 12 months
    -   `step`: 3 months
3.  **Analyze WFE Results:** In your log, analyze the output from the `walk_forward_summary` function.
    -   How many of the walk-forward windows were profitable?
    -   Is the performance consistent across different time periods?
    -   Does the strategy's performance degrade significantly on out-of-sample data?

### Phase 2: Monte Carlo (MC) Simulation

This tests for sensitivity to the sequence of trades (luck).

1.  **Configure MC:** Create another run configuration file. This time, enable the Monte Carlo simulation feature with at least 1,000 runs.
2.  **Execute MC:** Run the backtester with the MC configuration.
3.  **Analyze MC Results:** In your log, analyze the `monte_carlo` section of the `brief.json`.
    -   What is the probability of a 50% drawdown?
    -   What is the probability of ruin?
    -   Is the distribution of final equity outcomes reasonably centered around the original backtest result, or is the original result an outlier?

### Phase 3: Final Report

1.  **Synthesize Findings:** Based on your analysis of the WFE and MC results, come to a final conclusion.
2.  **Generate Validation Report:** Create a `validation_report.md` in your session workspace. This report must include:
    -   A summary of the WFE results, including consistency and out-of-sample performance.
    -   A summary of the MC results, including risk-of-ruin metrics.
    -   A final verdict:
        -   **Robust:** The strategy passed WFE and MC tests. It shows a stable edge and is a candidate for further refinement or paper trading.
        -   **Brittle:** The strategy failed WFE or MC tests. Its performance is likely a result of curve-fitting. It should be rejected or returned to the Discovery Phase.

---

## 4. Success Criteria

-   **WFE Success:** A strategy is considered to have passed WFE if at least **70%** of the out-of-sample test periods are profitable.
-   **MC Success:** A strategy is considered to have passed MC if the **probability of ruin is less than 1%** and the original backtest's PnL falls within the 25th-75th percentile of the simulation outcomes.
