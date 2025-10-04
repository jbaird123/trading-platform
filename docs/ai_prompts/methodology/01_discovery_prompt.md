# AI Prompt: Autonomous Strategy Discovery & Validation

## 1. Your Mission

Your primary mission is to autonomously find and validate a profitable trading strategy. You will use the tools and capabilities of this trading platform to discover, validate, and refine strategies in a structured, chronological, and reproducible workflow.

---

## 2. Core Mandates & Guardrails

These rules are absolute and must be followed at all times.

-   **Unified Campaign Workspace:**
    -   All work for a single strategy idea **MUST** be contained within a single parent "campaign" directory under `workspace/research/`.
    -   You must ask the user for a campaign name (e.g., `ema_crossover_campaign`).
-   **Chronological, Timestamped Steps:**
    -   Every action you take (a discovery sweep, a validation run, a refinement iteration) **MUST** be executed in its own unique, timestamped subdirectory within the campaign folder.
    -   Directory names **MUST** follow the format: `YYYYMMDD_HHMMSS_ms_phase_description` (e.g., `20251005_143000_123_01_discovery_initial_sweep`).
    -   This ensures a perfectly sorted, auditable history of the entire process.
-   **Meticulous Logging:**
    -   Each step's timestamped directory **MUST** contain a `run_summary.md` file detailing the hypothesis, actions taken, and results for that specific step.
    -   The root of the campaign directory **MUST** contain a master `campaign_log.md` that provides a high-level summary and links to each step's `run_summary.md`.

---

## 3. The Unified Workflow

### Phase 0: Campaign Initialization

1.  **Define Campaign:** Ask the user for a name for the new research campaign (e.g., `rsi_mean_reversion`).
2.  **Create Campaign Workspace:** Create the parent directory: `workspace/research/<campaign_name>/`.
3.  **Initialize Campaign Log:** Create the master `campaign_log.md` in the root of the campaign directory.

### Phase 1: Iterative Discovery & Refinement

This is a loop where you will generate and test ideas. Each iteration is a new, timestamped step in the campaign workspace.

1.  **Create Step Directory:** Create a new timestamped directory for this iteration (e.g., `.../20251005_143000_123_01_discovery_initial_sweep/`). All work for this step occurs here.
2.  **Hypothesize:** Formulate a single, concrete hypothesis. This could be a brand new strategy idea or an improvement to the result of a previous step. Log this in the step's `run_summary.md`.
3.  **Implement:** Create the necessary configuration files (strategy `.yaml`, parameter grids, etc.) within the current step directory.
4.  **Test & Measure:** Run the appropriate script (`run-improvement-cycle.sh`, a parameter sweep, etc.). All output artifacts must be saved within the current step directory.
5.  **Evaluate & Log:** Analyze the results (`brief.json`, etc.). Record your findings in the `run_summary.md` and update the master `campaign_log.md` with a link to this new step.
6.  **Decide Next Step:** Based on the evaluation, decide whether to:
    -   **Continue Refining:** Start a new "Discovery" iteration.
    -   **Validate Candidate:** If a promising candidate is found, proceed to Phase 2.
    -   **Pivot or Conclude:** If the idea is not working, you can pivot to a new hypothesis or end the campaign.

### Phase 2: Rigorous Validation

When you have a "winning" candidate from Phase 1, you must subject it to rigorous testing.

1.  **Create Validation Step Directory:** Create a new timestamped directory for the validation phase (e.g., `.../20251005_144510_456_02_validation_of_sweep_winner/`).
2.  **Run Validation Gauntlet:** Inside this directory, perform the necessary robustness checks. This typically involves running Walk-Forward Evaluation (WFE) and Monte Carlo (MC) simulations as defined in the `02_validation_prompt.md` guide.
3.  **Log Validation Results:** Document the WFE and MC outcomes and your final verdict (`Robust` or `Brittle`) in the step's `run_summary.md`. Update the master `campaign_log.md`.

### Phase 3: Promotion

If a strategy successfully passes validation, it can be promoted.

1.  **Create Promotion Step Directory:** Create a final timestamped directory (e.g., `.../20251005_151540_999_PROMOTION/`).
2.  **Consolidate Artifacts:** Copy the final, "golden" artifacts into this directory:
    -   The final strategy `.yaml` file.
    -   The definitive `brief.json` from the validation run.
    -   A `final_report.md` summarizing the entire campaign journey from initial idea to final validated parameters.
3.  **Propose Next Action:** Ask the user if you should formally add the promoted strategy to the main `config/strategy/` directory.

---

## 4. Success Criteria

A strategy is considered "winning" or "successful" when it meets a combination of these criteria over a significant backtest period. You should aim for:

-   **Consistent Profitability:** `total_pnl` is positive.
-   **Acceptable Risk:** `max_drawdown` is less than 20% of the total PnL.
-   **Good Risk/Reward:** Sharpe Ratio > 1.0.
-   **Robustness:** The strategy passes the validation criteria (e.g., WFE and MC tests).

---

## 5. Final Output

At the end of your process, you will have:

1.  A complete campaign directory in `workspace/research/` containing a chronologically sorted series of timestamped folders, each documenting a specific step.
2.  A `PROMOTION` folder containing the final, validated artifacts of a successful strategy.
