# AI Prompt Guide: Performing a Strategy Validation Step

## 1. Your Mission

Your mission is to take a "candidate" trading strategy that was identified during a Discovery step and determine if its performance is robust or an illusion of curve-fitting. This process is a **step within a larger research campaign**.

---

## 2. Core Mandates & Guardrails

-   **Campaign Integrity:** You **MUST** be working within an existing campaign directory under `workspace/research/`.
-   **Create Step Directory:** You **MUST** create a new, unique, timestamped subdirectory for this validation step. The name should clearly identify it as a validation phase (e.g., `.../20251005_144510_456_02_validation_of_candidate/`).
-   **Input:** Your primary input is the path to the candidate strategy's `.yaml` file from a **previous step** within the same campaign.
-   **Meticulous Logging:** Maintain a `run_summary.md` within your new step directory, detailing each validation test, the commands run, and the results observed. Update the master `campaign_log.md` with a link to this step.

---

## 3. The Validation Workflow

### Phase 0: Initiating the Validation Step

1.  **Identify Candidate:** The candidate strategy is the best-performing configuration from a preceding Discovery step in the current campaign.
2.  **Create Step Workspace:** Create your unique, timestamped directory for this validation run.
3.  **Start Log:** Create the `run_summary.md` file and link it in the master `campaign_log.md`.
4.  **Load Candidate:** Copy the candidate strategy's `.yaml` file from the previous step's directory into your current validation step directory.

### Phase 1: Walk-Forward Evaluation (WFE)

This is a critical test for robustness against changing market conditions.

1.  **Execute WFE:** Run the necessary backtests and analysis to perform a Walk-Forward Evaluation on the candidate strategy. All artifacts must be saved in the current step directory.
2.  **Analyze WFE Results:** In your `run_summary.md`, analyze the WFE output.
    -   How many of the walk-forward windows were profitable?
    -   Is the performance consistent across different time periods?
    -   Does the strategy's performance degrade significantly on out-of-sample data?

### Phase 2: Monte Carlo (MC) Simulation

This tests for sensitivity to the sequence of trades (luck).

1.  **Execute MC:** Run a backtest with the Monte Carlo simulation feature enabled (at least 1,000 runs).
2.  **Analyze MC Results:** In your `run_summary.md`, analyze the `monte_carlo` section of the resulting `brief.json`.
    -   What is the probability of a 50% drawdown or ruin?
    -   Is the original backtest result an outlier compared to the distribution of simulation outcomes?

### Phase 3: Final Verdict

1.  **Synthesize Findings:** Based on your analysis of the WFE and MC results, come to a final conclusion for this validation step.
2.  **Log Verdict:** In your `run_summary.md`, record a final verdict:
    -   **Robust:** The strategy passed WFE and MC tests, and its maximum drawdown period did not exceed two weeks. It is a candidate for `PROMOTION`.
    -   **Brittle:** The strategy failed WFE or MC tests, or it endured an unacceptably long drawdown. Its performance is likely a result of curve-fitting. It should be rejected or returned to a new `Discovery` step for refinement.

---

## 4. Success Criteria

-   **WFE Success:** A strategy is considered to have passed WFE if at least **70%** of the out-of-sample test periods are profitable.
-   **MC Success:** A strategy is considered to have passed MC if the **probability of ruin is less than 1%** and the original backtest's PnL falls within the 25th-75th percentile of the simulation outcomes.
