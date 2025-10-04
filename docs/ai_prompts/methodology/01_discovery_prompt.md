# AI Prompt: Autonomous Strategy Discovery

## 1. Your Mission

Your primary mission is to autonomously find a profitable trading strategy. You will use the tools and capabilities of this trading platform to discover, validate, and refine strategies in a structured and methodical way. Your entire process must be self-contained, reproducible, and clean.

---

## 2. Core Mandates & Guardrails

These rules are absolute and must be followed at all times.

-   **Workspace Integrity:**
    -   You **MUST** create a unique session directory for your work under `workspace/strategy_discovery/`. Name it with a timestamp and the target strategy (e.g., `20251004_150000_ema_crossover_discovery`).
    -   **ALL** files you create (configurations, logs, reports, temporary strategies) **MUST** be saved within this session directory. Do not write anywhere else until the final "Promotion" step.
-   **Meticulous Logging:**
    -   You **MUST** maintain a detailed log of your entire process in a file named `session_log.md` within your workspace.
    -   For each iteration, you must log: your hypothesis, the exact change you are implementing, the key results, and your evaluation of those results.
-   **Methodical Process:** You must follow the structured workflows defined below. Do not take shortcuts.

---

## 3. The Discovery Workflow

### Phase 0: Initialization

1.  **Create Workspace:** Create your unique session directory as specified in the Mandates.
2.  **Start Log:** Create the `session_log.md` file and add your first entry, stating the session's goal.

### Phase 1: Mode Selection

Your first operational decision is to choose a mode. You can ask the user for their preference.

-   **[1] Improvement Mode:** Systematically refine an existing strategy.
-   **[2] Discovery Mode:** Brainstorm and validate a completely new strategy.

Log which mode you have chosen.

### Phase 2A: "Improvement Mode" Workflow

If you choose Improvement Mode, follow these steps:

1.  **Select Candidate:** List the strategies in `config/strategy/` and select one to improve.
2.  **Establish Baseline:** Copy the strategy's configuration files into your session workspace. Run the `scripts/run-improvement-cycle.sh` script on this baseline configuration to generate the initial performance reports. Log the path to the baseline run directory.
3.  **Begin Improvement Loop:** Start an iterative cycle to refine the strategy.
    a.  **Synthesize & Hypothesize:** Analyze the `brief.json`, `ai_diagnostic_report.json`, and `ai_qualitative_report.md` from the most recent run. Formulate a single, concrete hypothesis for improvement and log it.
    b.  **Implement Change:** Create a new version of the strategy YAML file (e.g., `strategy_v2.yaml`) in your workspace that implements your hypothesis.
    c.  **Test & Measure:** Run the `scripts/run-improvement-cycle.sh` script on your new strategy version.
    d.  **Evaluate:** Compare the new results to the previous version. If performance has improved and the success criteria are not yet met, continue the loop. If performance has degraded, you may revert the change and try a new hypothesis. Log your evaluation.

### Phase 2B: "Discovery Mode" Workflow

If you choose Discovery Mode, follow these steps:

1.  **Brainstorm & Hypothesize:**
    a.  **Scan Assets:** Review `src/trading_platform/strategy/indicators_registry.py`, `docs/schemas/strategy.schema.json`, and the available instruments in the `data/` directory.
    b.  **Formulate Novel Hypothesis:** Create a hypothesis for a new strategy logic that is not a simple variation of existing ones. Consider different indicators, timeframes, and instruments. Log your hypothesis.
2.  **Scaffold & Validate:**
    a.  **Create Strategy:** Write a new strategy YAML file from scratch in your workspace.
    b.  **Create Wide Grid:** Create a `grid.json` file with a wide range of parameters to test the core concept.
    c.  **Run Broad Sweep:** Execute a parameter search to determine if the concept has any merit. The goal is to find any pocket of profitability, not to perfect it yet.
3.  **Proceed or Pivot:**
    a.  **If Promising:** If the sweep is successful, select the best parameter set as your new "baseline" strategy. Now, **transition to the "Improvement Loop" (Phase 2A, Step 3)** to systematically refine your new discovery.
    b.  **If Not Promising:** Log the failure and your analysis of why it failed. You may either return to the brainstorming step (2B.1) to try a new idea or conclude the session.

### Phase 3: Final Report & Promotion

Once your iterative loop is complete (either by meeting success criteria or reaching a stopping point), you must conclude the session.

1.  **Generate Final Report:** Create a `final_report.md` in your session workspace. This report must summarize the entire journey: the initial state, each iteration's hypothesis and result, and the final, validated "winning" strategy configuration.
2.  **Propose Promotion:** Ask the user if you should promote the winning strategy. If approved, create a new, clean directory under `configs/strategies/` (e.g., `ema_crossover_optimized_v1`) and copy the final strategy YAML, the final `brief.json`, and the `final_report.md` into it.

---

## 4. Success Criteria

A strategy is considered "winning" or "successful" when it meets a combination of these criteria over a significant backtest period. You should aim for:

-   **Consistent Profitability:** `total_pnl` is positive.
-   **Acceptable Risk:** `max_drawdown` is less than 20% of the total PnL.
-   **Good Risk/Reward:** Sharpe Ratio > 1.0.
-   **Robustness:** The strategy shows positive performance in the Walk-Forward Evaluation and does not have a high `ruin_prob` in the Monte Carlo simulation.

---

## 5. Final Output

At the end of your process, you will have:

1.  A complete session directory in `workspace/strategy_discovery/` containing all artifacts and a detailed log.
2.  A final proposal to the user to promote the best strategy found.
