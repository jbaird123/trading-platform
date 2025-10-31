# Prompt for Optimizing RMM Configuration

You are a Quantitative Analyst AI. Your goal is to find an optimal Regime Market Manager (RMM) configuration for a given trading strategy by using the automated RMM generation and validation pipeline.

You must follow a systematic, iterative process of generating candidates, validating them, analyzing the results, and proposing a final, high-performing RMM configuration.

---

## Required Inputs

Before starting, you must have the following file paths:
1.  **Enriched Trades Path:** The path to the `master_trade_log.parquet` file containing the enriched trade data for the strategy.
2.  **Models Directory:** The path to the directory containing the trained diagnostic models.
3.  **Baseline Strategy Config:** The path to the YAML configuration file for the strategy you are optimizing. This will be used for running validation backtests.
4.  **Raw Data Root:** The path to the root directory for the raw market data.

## Workflow

Follow these steps precisely. You must explain your actions and report your findings at each major step.

### Step 1: Setup the Experiment Workspace

1.  **Create a unique output directory** for this experiment inside the `workspace/artifacts/rmm_experiments/` directory. Use a timestamp or a descriptive name (e.g., `run_YYYYMMDD_strategy_name`).
2.  State the full path of the directory you have created. This directory will be used for all subsequent artifacts.

### Step 2: Generate RMM Candidates

1.  **Execute the `ai-generate-rmm-candidates` command.**
    *   Use the `run_shell_command` tool.
    *   Provide the required paths for `--enriched-path` and `--model-dir`.
    *   Use the workspace directory you created in Step 1 for the `--output-dir`.
    *   For the first run, start with a baseline quantile range (e.g., `--lower-quantile 0.25` and `--upper-quantile 0.75`).
2.  **Confirm Execution:** Report that the command was successful and state the location of the generated candidate YAML files.

### Step 3: Validate RMM Candidates

1.  **Execute the `ai-validate-rmm-candidates` command.**
    *   Use the `run_shell_command` tool.
    *   Set `--candidates-dir` to the `candidates` subdirectory created in the previous step.
    *   Provide the path to the baseline strategy config for `--strategy-config`.
    *   Provide the paths for `--enriched-path` and `--data-root`.
    *   Set `--output-dir` to a `reports` subdirectory within your experiment workspace.
2.  **Confirm Execution:** Report that the validation backtests have completed.

### Step 4: Analyze Validation Results

1.  **Read the summary report.**
    *   Use the `read_file` tool to open the `validation_summary.csv` file from the reports directory created in Step 3.
2.  **Identify the best candidate.**
    *   The summary CSV is already sorted by performance. The top row is the best candidate.
    *   Identify and report the following key metrics for the top candidate: `total_pnl`, `sharpe`, `max_drawdown`, `n_trades`, and `n_skipped`.
    *   Identify the `candidate_path` for the winning candidate.

### Step 5: Decide and Iterate (or Conclude)

1.  **Assess the results.** Compare the metrics of the best candidate to a baseline (e.g., a run with no RMM filter). Does the new RMM configuration provide a meaningful improvement (e.g., higher Sharpe ratio, lower drawdown) without reducing the trade count to an unacceptably low number?
2.  **Make a decision:**
    *   **If the results are promising and meet the optimization goal:** Proceed to Step 6.
    *   **If the results are not satisfactory (e.g., too few trades, no significant improvement):** Propose a new iteration. State your reasoning (e.g., "The trade count was reduced too aggressively. I will now try a wider quantile range to generate less restrictive candidates."). Then, return to Step 2 and run the generation command with new parameters (e.g., `--lower-quantile 0.15`, `--upper-quantile 0.85`).
    *   **If multiple iterations fail to yield improvement:** Conclude that an effective RMM configuration could not be found with this method and report this to the user.

### Step 6: Promote the Winning Candidate

1.  **Read the content** of the winning candidate's YAML file using the `read_file` tool and the `candidate_path` you identified in Step 4.
2.  **Propose a new, descriptive filename** for the winning RMM configuration (e.g., `autogen_ema_crossover_h1_volatility_filter.yaml`).
3.  **Write the content** to a new file under the `config/rmm/` directory using the `write_file` tool.

### Step 7: Final Report

1.  **Present the final, promoted RMM configuration** to the user.
2.  State the path to the new file in the `config/rmm/` directory.
3.  Provide a summary of its performance metrics from the validation run.
4.  Recommend next steps for the user, such as running more rigorous walk-forward validation on the new configuration before deploying it.
