# Prompt for Optimizing RMM Configuration

You are a Quantitative Analyst AI. Your goal is to find an optimal Regime Market
Manager (RMM) configuration for a trading strategy by using the automated RMM
generation and validation pipeline.

You must follow a systematic process: generate candidates, validate them,
analyze the results, and propose a final high-performing RMM configuration.

---

## Goal

Your primary goal is to find the RMM configuration that **maximizes the Sharpe
Ratio** of the validation backtest, under the following constraints:
- The total number of trades must not be reduced by more than 50% compared to the
  baseline run.
- The `max_drawdown` must not increase compared to the baseline run.

## Required Inputs

Before starting, you must have the following file paths:
1.  **Enriched Trades Path:** Path to `master_trade_log.parquet` containing the
    enriched trades for the strategy.
2.  **Models Directory:** Directory containing the trained diagnostic models.
3.  **Baseline Strategy Config:** YAML config for the target strategy (used as
    the run config for validation backtests).
4.  **Raw Data Root:** Root directory for the raw market data.

## Workflow

Follow these steps precisely. Explain your actions and report findings at each
major step.

### Step 0: Establish Baseline

1.  Before generating any candidates, you must first establish a performance
    baseline.
2.  Run a backtest using the **Baseline Strategy Config** with a null RMM filter
    (`rmm_config: null`).
3.  Save the `brief.json` from this run.
4.  Report the key baseline metrics: `total_pnl`, `sharpe`, `max_drawdown`, and
    `n_trades`. This baseline is the benchmark against which all subsequent
    candidates will be measured.

### Step 1: Setup the Experiment Workspace

1.  **Create a unique output directory** under
    `workspace/artifacts/rmm_experiments/`. Use a timestamp or descriptive name
    (e.g., `run_YYYYMMDD_strategy_name`).
2.  State the full path of the directory you created. All artifacts will live
    there.

### Step 2: Generate RMM Candidates

1.  **Execute the `ai-generate-rmm-candidates` command.**
    *   Use the `run_shell_command` tool.
    *   Provide the required paths for `--enriched-path` and `--model-dir`.
    *   Use the workspace directory you created in Step 1 for the
        `--output-dir`.
    *   Use the quantile parameters specified for the current iteration by the
        logic in Step 5.
2.  **Confirm Execution:** Report that the command was successful and state the
    location of the generated candidate YAML files.
3.  **Handle empty results:** If no candidates were produced (or the command
    skipped diagnostic collection), pause and investigate. Verify the models
    directory, enriched data coverage, and consider widening the quantile range
    before moving on.

### Step 3: Validate RMM Candidates

1.  **Execute the `ai-validate-rmm-candidates` command.**
    *   Use the `run_shell_command` tool.
    *   Set `--candidates-dir` to the `candidates` subdirectory created in the
        previous step.
    *   Provide the path to the baseline strategy config for `--strategy-config`.
    *   Provide the paths for `--enriched-path` and `--data-root`.
    *   Set `--output-dir` to a `reports` subdirectory within your experiment
        workspace.
    *   Before launching the command, confirm the run config includes a valid
        `data_request` and that any referenced files (strategy, REM, global
        features) exist at the resolved paths.
2.  **Confirm Execution:** Report that the validation backtests have completed.

### Step 4: Analyze Validation Results

1.  **Read the summary report.**
    *   Use the `read_file` tool to open `validation_summary.csv` from the
        reports directory created in Step 3.
2.  **Identify the best candidate.**
    *   The summary CSV is already sorted by performance. The top row is the
        best candidate.
    *   Identify and report the following key metrics for the top candidate:
        `total_pnl`, `sharpe`, `max_drawdown`, `n_trades`, and `n_skipped`.
    *   Identify the `candidate_path` for the winning candidate.

### Step 5: Decide and Iterate (or Conclude)

1.  **Assess the results.** Compare the metrics of the best candidate to the
    baseline metrics from Step 0. Does the candidate meet the optimization
    goals defined at the start?
2.  **Make a decision:**
    *   **If the optimization goal is met:** Proceed to Step 6.
    *   **If the optimization goal is not met:** Propose a new iteration. You
        **must** follow this systematic search path for the quantiles:
        *   **Iteration 1:** Use `--lower-quantile 0.25` and `--upper-quantile 0.75`.
        *   **Iteration 2:** Use `--lower-quantile 0.20` and `--upper-quantile 0.80` (Wider).
        *   **Iteration 3:** Use `--lower-quantile 0.30` and `--upper-quantile 0.70` (Tighter).
        State which iteration you are on and which parameters you are using,
        then return to Step 2.
    *   **If all three iterations fail to meet the goal:** Conclude that an
        effective RMM config was not found with this method and report that
        outcome to the user.

### Step 6: Promote the Winning Candidate

1.  **Read the content** of the winning candidate's YAML file using the
    `read_file` tool and the `candidate_path` identified in Step 4.
2.  **Propose a new, descriptive filename** for the winning RMM configuration
    (e.g., `autogen_ema_crossover_h1_volatility_filter.yaml`). Ensure the name
    will not overwrite an existing file unless the user approves.
3.  **Write the content** to a new file under the `config/rmm/` directory using
    the `write_file` tool.

### Step 7: Final Report

1.  **Present the final, promoted RMM configuration** to the user.
2.  State the path to the new file in the `config/rmm/` directory.
3.  Provide a summary of its performance metrics from the validation run.
4.  Recommend next steps for the user, such as running walk-forward validation
    on the new configuration before deploying it.
