# Meta-Campaign System Implementation Plan

**Branch Name:** `feature/meta-campaign-system`

**Overview:** Implement a two-stage meta-campaign system that automates the creation of all campaign configurations needed to train the comprehensive suite of ML models. The system reads a single high-level `meta-campaign.yaml` file, calculates the cartesian product of all parameters (dates, instruments, timeframes, strategies, and their parameters), and generates individual, ready-to-run campaign files.

**Reference Document:** `docs/working/campaign_config_refactor_plan.md`

---

## Part 1: Setup and Directory Structure

### 1. [ ] Create branch for meta-campaign system
- Run: `git checkout -b feature/meta-campaign-system`

### 2. [ ] Create stable config template directories
- Create directory: `config/master_data_generation/`
- Create subdirectory: `config/master_data_generation/strategies/`
- Create subdirectory: `config/master_data_generation/rem/`

### 3. [ ] Copy baseline strategy configuration
- Copy file `config/strategy/ema_crossover.yaml` to `config/master_data_generation/strategies/ema_crossover_v1.yaml`
- Verify the copied file contains all required fields for strategy configuration

### 4. [ ] Copy baseline REM configuration
- Copy file `config/rem/chandelier_stop.yaml` to `config/master_data_generation/rem/chandelier_stop_v1.yaml`
- Verify the copied file contains all required fields for risk/exit management configuration

### 5. [ ] Create meta-campaigns configuration directory
- Create directory: `config/meta_campaigns/`
- This directory will store high-level meta-campaign configuration files

---

## Part 2: Data Models and Schema

### 6. [ ] Write tests for MetaCampaignConfig data model
- Create file: `tests/core/test_meta_campaign_config.py`
- Add test: `test_meta_campaign_config_loads_from_yaml()`
  - Load example YAML with `meta_campaign_id`, `description`, `run_grid`, and `strategy_profiles`
  - Assert all fields are correctly parsed
- Add test: `test_run_grid_date_ranges_validation()`
  - Verify `date_ranges` contains list of dicts with `start` and `end` keys
  - Assert dates are valid ISO format strings
- Add test: `test_run_grid_instruments_validation()`
  - Verify `instruments` is a list of strings
  - Assert instruments are valid (e.g., "EUR_USD", "GBP_USD")
- Add test: `test_run_grid_execution_timeframes_validation()`
  - Verify `execution_timeframes` is a list of strings
  - Assert timeframes are valid values: ["1min", "5min", "15min", "1H", "4H", "1D"]
- Add test: `test_strategy_profile_with_risk()`
  - Load strategy profile with `name: "trend_with_risk"`
  - Assert `strategy_path`, `rem_path`, and `archetype` are present
  - Verify `param_grid` contains list of dicts with `strategy_params` and `rem_params`
- Add test: `test_strategy_profile_without_risk()`
  - Load strategy profile with `name: "baseline_no_risk"`
  - Assert `rem_path` is null/None
  - Verify `param_grid` contains only `strategy_params` (no `rem_params`)
- Add test: `test_meta_campaign_config_validates_required_fields()`
  - Test missing `meta_campaign_id` raises validation error
  - Test missing `run_grid` raises validation error
  - Test missing `strategy_profiles` raises validation error

### 7. [ ] Implement MetaCampaignConfig data model
- Create file: `src/trading_platform/core/meta_campaign_config.py`
- Import required modules: `from __future__ import annotations`, `from dataclasses import dataclass`, `from pathlib import Path`, `from typing import Any`, `import yaml`
- Define `@dataclass` class `StrategyProfileParamSet`:
  - Field: `strategy_params: dict[str, Any]`
  - Field: `rem_params: dict[str, Any] | None = None`
- Define `@dataclass` class `StrategyProfile`:
  - Field: `name: str`
  - Field: `strategy_path: str`
  - Field: `rem_path: str | None`
  - Field: `archetype: str`
  - Field: `param_grid: list[StrategyProfileParamSet]`
  - Add method `def has_risk(self) -> bool:` that returns `self.rem_path is not None`
- Define `@dataclass` class `RunGrid`:
  - Field: `date_ranges: list[dict[str, str]]`
  - Field: `instruments: list[str]`
  - Field: `execution_timeframes: list[str]`
  - Add validation method `def validate(self) -> None:` that checks:
    - All date_ranges have "start" and "end" keys
    - All execution_timeframes are in valid set: {"1min", "5min", "15min", "1H", "4H", "1D"}
- Define `@dataclass` class `MetaCampaignConfig`:
  - Field: `meta_campaign_id: str`
  - Field: `description: str`
  - Field: `run_grid: RunGrid`
  - Field: `strategy_profiles: list[StrategyProfile]`
  - Add classmethod `@classmethod def from_yaml(cls, path: Path) -> MetaCampaignConfig:`
    - Load YAML file using `yaml.safe_load()`
    - Parse nested structures and create dataclass instances
    - Call `run_grid.validate()` before returning
    - Return `MetaCampaignConfig` instance
- Run: `pytest tests/core/test_meta_campaign_config.py --cov=src/trading_platform/core/meta_campaign_config -v`
- Verify: 100% test coverage achieved

---

## Part 3: Campaign Generation Logic

### 8. [ ] Write tests for campaign generator utility
- Create file: `tests/core/test_meta_campaign_generator.py`
- Add test: `test_calculate_cartesian_product_single_profile()`
  - Create minimal `MetaCampaignConfig` with 1 date_range, 2 instruments, 2 timeframes, 1 strategy profile with 2 param sets
  - Expected total campaigns: 1 × 2 × 2 × 2 = 8
  - Assert result is list of 8 campaign configurations
- Add test: `test_calculate_cartesian_product_multiple_profiles()`
  - Create `MetaCampaignConfig` with 2 strategy profiles (trend_with_risk and baseline_no_risk)
  - Verify campaigns are generated for both profiles
- Add test: `test_campaign_config_includes_all_dimensions()`
  - Generate campaigns and verify each config dict contains:
    - `date_range: {"start": ..., "end": ...}`
    - `instrument: str`
    - `execution_timeframe: str`
    - `strategy_path: str`
    - `rem_path: str | None`
    - `archetype: str`
    - `strategy_params: dict`
    - `rem_params: dict | None`
    - `meta_campaign_id: str`
    - `profile_name: str`
- Add test: `test_generate_campaign_filename()`
  - Input: meta_campaign_id="trend_following_model_generation", profile_name="trend_with_risk", instrument="EUR_USD", timeframe="15min", param_index=0
  - Expected output: "trend_following_model_generation_trend_with_risk_EUR_USD_15min_00.yaml"
  - Assert filename matches expected pattern
- Add test: `test_campaign_config_to_yaml_dict()`
  - Create campaign config dict
  - Convert to YAML-compatible format
  - Verify all nested dictionaries are properly structured
  - Assert `strategy_params` and `rem_params` are merged into the appropriate config sections

### 9. [ ] Implement meta-campaign generator utility
- Create file: `src/trading_platform/core/meta_campaign_generator.py`
- Import required modules: `from __future__ import annotations`, `from pathlib import Path`, `from typing import Any`, `import itertools`, `import yaml`
- Import: `from trading_platform.core.meta_campaign_config import MetaCampaignConfig, StrategyProfile, StrategyProfileParamSet`
- Define function `def calculate_cartesian_product(config: MetaCampaignConfig) -> list[dict[str, Any]]:`
  - Use `itertools.product()` to generate cartesian product of:
    - `config.run_grid.date_ranges`
    - `config.run_grid.instruments`
    - `config.run_grid.execution_timeframes`
    - For each `profile` in `config.strategy_profiles`: `profile.param_grid`
  - For each combination, create dict with keys:
    - `meta_campaign_id`: from config
    - `profile_name`: from profile
    - `date_range`: {start, end}
    - `instrument`: string
    - `execution_timeframe`: string
    - `strategy_path`: from profile
    - `rem_path`: from profile (or None)
    - `archetype`: from profile
    - `strategy_params`: from param_set
    - `rem_params`: from param_set (or None)
  - Return list of all campaign configuration dicts
- Define function `def generate_campaign_filename(meta_campaign_id: str, profile_name: str, instrument: str, timeframe: str, param_index: int) -> str:`
  - Format: `f"{meta_campaign_id}_{profile_name}_{instrument}_{timeframe}_{param_index:02d}.yaml"`
  - Return filename string
- Define function `def campaign_config_to_yaml_dict(campaign: dict[str, Any]) -> dict[str, Any]:`
  - Create base config dict structure matching existing campaign YAML format
  - Include fields:
    - `start_date`: from campaign["date_range"]["start"]
    - `end_date`: from campaign["date_range"]["end"]
    - `instrument`: from campaign["instrument"]
    - `execution_timeframe`: from campaign["execution_timeframe"]
    - `strategy`: load from campaign["strategy_path"] and merge with campaign["strategy_params"]
    - `rem`: load from campaign["rem_path"] if not None, merge with campaign["rem_params"]
    - `archetype`: from campaign["archetype"]
    - `metadata`:
      - `meta_campaign_id`: from campaign
      - `profile_name`: from campaign
      - `git_commit`: get current git commit hash
  - Return YAML-compatible dict
- Run: `pytest tests/core/test_meta_campaign_generator.py --cov=src/trading_platform/core/meta_campaign_generator -v`
- Verify: 100% test coverage achieved

---

## Part 4: CLI Command Implementation

### 10. [ ] Write tests for meta-campaign-plan CLI command
- Create file: `tests/cli/test_meta_campaign_plan_command.py`
- Add test: `test_meta_campaign_plan_requires_config_argument()`
  - Run CLI with `tp meta-campaign-plan` (no arguments)
  - Assert command fails with error message: "--config is required"
  - Assert exit code is non-zero
- Add test: `test_meta_campaign_plan_generates_campaign_files(tmp_path)`
  - Create minimal `meta-campaign.yaml` in tmp_path with 2 campaigns expected
  - Run CLI: `tp meta-campaign-plan --config {tmp_path}/meta-campaign.yaml --output-dir {tmp_path}/campaigns`
  - Assert 2 YAML files are created in output directory
  - Verify filenames match pattern: `{meta_campaign_id}_{profile}_{instrument}_{timeframe}_{index:02d}.yaml`
- Add test: `test_meta_campaign_plan_output_yaml_structure(tmp_path)`
  - Generate campaigns to tmp_path
  - Load one generated YAML file
  - Assert it contains all required fields for a valid campaign config:
    - `start_date`, `end_date`, `instrument`, `execution_timeframe`
    - `strategy` dict with strategy params merged
    - `rem` dict if profile has risk parameters
    - `metadata` with `meta_campaign_id` and `profile_name`
- Add test: `test_meta_campaign_plan_prints_summary(capsys, tmp_path)`
  - Run command and capture stdout
  - Assert output contains: "Generated {N} campaign configurations"
  - Assert output lists output directory path
  - Assert output suggests next steps: "Run with: tp campaign-run <campaign_file>"
- Add test: `test_meta_campaign_plan_overwrites_with_force_flag(tmp_path)`
  - Generate campaigns once
  - Modify one generated file manually
  - Run command again with `--force` flag
  - Assert modified file is overwritten
- Add test: `test_meta_campaign_plan_fails_without_force_if_files_exist(tmp_path)`
  - Generate campaigns once
  - Run command again without `--force` flag
  - Assert command fails with error: "Output directory contains existing files. Use --force to overwrite."

### 11. [ ] Implement meta-campaign-plan CLI command
- Edit file: `src/trading_platform/cli.py`
- Add function: `def _meta_campaign_plan_logic(args: argparse.Namespace) -> int:`
  - Validate `args.config` is provided; if not, print error and return 2
  - Load `MetaCampaignConfig` from `args.config` using `MetaCampaignConfig.from_yaml()`
  - Get output directory from `args.output_dir` (default: `config/campaigns/generated/`)
  - Check if output directory exists and contains files:
    - If files exist and `--force` not provided, print error and return 1
    - If `--force` provided, clear directory
  - Call `calculate_cartesian_product(config)` to generate list of campaign configs
  - For each campaign config (with enumerated index):
    - Generate filename using `generate_campaign_filename()`
    - Convert to YAML dict using `campaign_config_to_yaml_dict()`
    - Write YAML file to output directory
  - Print summary:
    - "Generated {N} campaign configurations"
    - "Output directory: {output_dir}"
    - "Next steps:"
    - "  1. Review generated configs in {output_dir}"
    - "  2. Run campaigns with: tp campaign-run <campaign_file>"
    - "  3. Review results with: tp campaign-review"
  - Return 0 for success
- In `def main() -> int:` function, add subparser for `meta-campaign-plan` command:
  - Subcommand name: "meta-campaign-plan"
  - Help text: "Generate campaign configurations from a meta-campaign file"
  - Add argument: `--config`, required=True, help="Path to meta-campaign.yaml file"
  - Add argument: `--output-dir`, default="config/campaigns/generated/", help="Directory to write generated campaign configs"
  - Add argument: `--force`, action="store_true", help="Overwrite existing files in output directory"
  - Set function: `args.func = _meta_campaign_plan_logic`
- Run: `pytest tests/cli/test_meta_campaign_plan_command.py --cov=src/trading_platform/cli -v`
- Verify: All tests pass and coverage is maintained

---

## Part 5: Example Meta-Campaign Configuration

### 12. [ ] Create example meta-campaign configuration file
- Create file: `config/meta_campaigns/trend_following_data_gen.yaml`
- Add content following this exact structure:
  ```yaml
  meta_campaign_id: trend_following_model_generation
  description: "Generates all campaign configs needed to train all trend-following models."

  run_grid:
    date_ranges:
      - { start: "2018-01-01", end: "2023-12-31" }
    instruments:
      - EUR_USD
      - GBP_USD
    execution_timeframes:
      - 1min
      - 5min
      - 15min
      - 1H
      - 4H
      - 1D

  strategy_profiles:
    # Profile for data WITH defined risk.
    - name: trend_with_risk
      strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
      rem_path: config/master_data_generation/rem/chandelier_stop_v1.yaml
      archetype: trend_following
      param_grid:
        - strategy_params: { fast_length: 10, slow_length: 20 }
          rem_params: { atr_length: 22, atr_multiplier: 2.0 }
        - strategy_params: { fast_length: 10, slow_length: 20 }
          rem_params: { atr_length: 22, atr_multiplier: 3.0 }
        - strategy_params: { fast_length: 20, slow_length: 50 }
          rem_params: { atr_length: 14, atr_multiplier: 2.5 }

    # Profile for data WITHOUT defined risk.
    - name: baseline_no_risk
      strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
      rem_path: null
      archetype: trend_following
      param_grid:
        - strategy_params: { fast_length: 9, slow_length: 21 }
        - strategy_params: { fast_length: 15, slow_length: 45 }
  ```
- Verify file is valid YAML by loading with `yaml.safe_load()`

### 13. [ ] Write integration test for example meta-campaign
- Create file: `tests/integration/test_meta_campaign_end_to_end.py`
- Add test: `test_generate_campaigns_from_example_meta_campaign(tmp_path)`
  - Load `config/meta_campaigns/trend_following_data_gen.yaml`
  - Calculate expected number of campaigns:
    - 1 date_range × 2 instruments × 6 timeframes × (3 trend_with_risk + 2 baseline_no_risk) = 60 campaigns
  - Generate campaigns to tmp_path
  - Assert 60 YAML files are created
  - Load first generated campaign and verify structure
  - Verify all campaigns have unique filenames
  - Verify campaigns for "trend_with_risk" profile include `rem_path`
  - Verify campaigns for "baseline_no_risk" profile have `rem_path: null`

### 14. [ ] Run integration test
- Run: `pytest tests/integration/test_meta_campaign_end_to_end.py -v`
- Verify: Test passes and 60 campaign files are generated correctly

---

## Part 6: Documentation

### 15. [ ] Create meta-campaign system user guide
- Create file: `docs/user_guides/meta_campaign_system.md`
- Add sections:
  1. **Overview**: Explain two-stage meta-campaign workflow (generation → execution & review)
  2. **Directory Structure**: Document `config/master_data_generation/` and `config/meta_campaigns/`
  3. **Meta-Campaign Configuration Format**: Explain YAML schema with annotated example
  4. **Usage Instructions**:
     - How to create a meta-campaign.yaml file
     - How to run: `tp meta-campaign-plan --config path/to/meta-campaign.yaml`
     - How to review generated configs
     - How to execute campaigns: `tp campaign-run <generated_config>`
     - How to review results: `tp campaign-review`
  5. **Strategy Profiles**: Explain "with risk" vs "no risk" profiles and param_grid structure
  6. **Managing Computational Cost**: Recommend starting with small subsets (1-2 years, 2-3 instruments, 2 timeframes)
  7. **Reproducibility**: Explain purpose of `config/master_data_generation/` vs `config/strategy/`
  8. **Troubleshooting**: Common errors and solutions

### 16. [ ] Update main CLI help documentation
- Edit file: `README.md` or `docs/cli_reference.md` (whichever contains CLI documentation)
- Add entry for `tp meta-campaign-plan` command with:
  - Description
  - Arguments: `--config`, `--output-dir`, `--force`
  - Example usage
  - Link to detailed user guide

---

## Part 7: Phase 0 Research Workflow Support

### 17. [ ] Write tests for data integrity validation utility
- Create file: `tests/data/test_data_integrity_validator.py`
- Add test: `test_check_gaps_in_time_series()`
  - Create sample parquet file with gaps in timestamps
  - Run validation function
  - Assert gaps are detected and reported with date ranges
- Add test: `test_check_corrupted_files()`
  - Create test directory with some corrupted parquet files
  - Run validation function
  - Assert corrupted files are identified
- Add test: `test_check_timestamp_consistency()`
  - Create parquet file with timestamps out of order
  - Run validation function
  - Assert inconsistencies are reported
- Add test: `test_validate_all_instruments()`
  - Create multiple parquet files for different instruments
  - Run validation for all instruments
  - Assert summary report includes all instruments

### 18. [ ] Implement data integrity validation utility
- Create file: `src/trading_platform/data/integrity_validator.py`
- Import required modules: `from __future__ import annotations`, `from pathlib import Path`, `import pandas as pd`, `from typing import Any`
- Define function `def check_time_series_gaps(df: pd.DataFrame, max_gap_minutes: int = 1440) -> list[dict[str, Any]]:`
  - Calculate time differences between consecutive rows
  - Identify gaps larger than max_gap_minutes
  - Return list of dicts with {start_time, end_time, gap_minutes}
- Define function `def check_timestamp_consistency(df: pd.DataFrame) -> list[str]:`
  - Verify timestamps are monotonically increasing
  - Check for duplicate timestamps
  - Return list of error messages
- Define function `def validate_parquet_file(file_path: Path) -> dict[str, Any]:`
  - Try to load parquet file
  - If load fails, return {file: file_path, status: "corrupted", error: exception_message}
  - If load succeeds, run gap and timestamp checks
  - Return {file: file_path, status: "valid", gaps: [...], timestamp_issues: [...]}
- Define function `def validate_all_data(data_dir: Path, instruments: list[str]) -> dict[str, Any]:`
  - For each instrument, find all parquet files in data_dir
  - Run `validate_parquet_file()` on each
  - Aggregate results
  - Return summary dict with totals and issues
- Run: `pytest tests/data/test_data_integrity_validator.py --cov=src/trading_platform/data/integrity_validator -v`
- Verify: 100% test coverage achieved

### 19. [ ] Write tests for data integrity validation CLI command
- Create file: `tests/cli/test_validate_data_command.py`
- Add test: `test_validate_data_requires_data_dir_argument()`
  - Run: `tp validate-data` (no arguments)
  - Assert error: "--data-dir is required"
- Add test: `test_validate_data_prints_summary(tmp_path, capsys)`
  - Create sample data in tmp_path with 1 valid file, 1 file with gaps
  - Run: `tp validate-data --data-dir {tmp_path}`
  - Assert output contains summary of validation results
  - Assert gaps are reported with date ranges
- Add test: `test_validate_data_returns_nonzero_if_issues_found(tmp_path)`
  - Create data with issues
  - Run command
  - Assert exit code is 1

### 20. [ ] Implement data integrity validation CLI command
- Edit file: `src/trading_platform/cli.py`
- Add function: `def _validate_data_logic(args: argparse.Namespace) -> int:`
  - Validate `args.data_dir` is provided
  - Get list of instruments from `args.instruments` or scan directory
  - Call `validate_all_data(Path(args.data_dir), instruments)`
  - Print summary report:
    - Total files checked
    - Files with issues
    - List of gaps and corrupted files
  - Return 0 if no issues, 1 if issues found
- Add subparser in `main()`:
  - Subcommand: "validate-data"
  - Help: "Validate data integrity for historical price data"
  - Argument: `--data-dir`, required=True, help="Directory containing parquet files"
  - Argument: `--instruments`, nargs="+", help="Specific instruments to check (default: all)"
  - Set function: `args.func = _validate_data_logic`
- Run: `pytest tests/cli/test_validate_data_command.py --cov=src/trading_platform/cli -v`
- Verify: All tests pass

---

## Part 8: Phase 5 Walk-Forward Validation Support

### 21. [ ] Write tests for walk-forward validation script
- Create file: `tests/validation/test_walk_forward_validation.py`
- Add test: `test_split_data_into_periods()`
  - Input: DataFrame with dates from 2019-2023
  - Call: `split_into_periods(df, period="year")`
  - Assert result is list of 5 DataFrames, one per year
  - Verify each DataFrame contains only data from its year
- Add test: `test_walk_forward_loop()`
  - Create mock data for 3 years
  - Define training windows: [(year1), (year1-2), (year1-3)]
  - Define test windows: [year2, year3, year4]
  - Run walk-forward loop
  - Assert models are retrained for each window
  - Assert backtest is run on each test window
  - Assert results dict contains performance for each test period
- Add test: `test_walk_forward_results_consistency_check()`
  - Create results from walk-forward validation
  - Check if performance metrics (Sharpe, max drawdown) are consistent across periods
  - Assert function returns consistency score/flag

### 22. [ ] Implement walk-forward validation utility
- Create file: `src/trading_platform/validation/walk_forward.py`
- Import required modules: `from __future__ import annotations`, `from pathlib import Path`, `import pandas as pd`, `from typing import Any, Callable`
- Define function `def split_into_periods(df: pd.DataFrame, period: str = "year") -> list[pd.DataFrame]:`
  - Group DataFrame by year (or other period)
  - Return list of DataFrames, one per period
- Define function `def walk_forward_validate(data: pd.DataFrame, strategy_config: dict[str, Any], periods: list[pd.DataFrame], train_model_fn: Callable, run_backtest_fn: Callable) -> dict[str, Any]:`
  - For each period index N:
    - Training data: concatenate all periods up to N
    - Test data: period N+1
    - Call `train_model_fn(training_data)`
    - Call `run_backtest_fn(strategy_config, test_data)`
    - Store results for period N+1
  - Return dict with {period_name: performance_metrics}
- Define function `def check_performance_consistency(results: dict[str, Any], metric: str = "sharpe_ratio", tolerance: float = 0.3) -> bool:`
  - Calculate mean and std of metric across all periods
  - Check if coefficient of variation (std/mean) is below tolerance
  - Return True if consistent, False otherwise
- Run: `pytest tests/validation/test_walk_forward_validation.py --cov=src/trading_platform/validation/walk_forward -v`
- Verify: 100% test coverage achieved

### 23. [ ] Write tests for walk-forward validation CLI command
- Create file: `tests/cli/test_walk_forward_validate_command.py`
- Add test: `test_walk_forward_validate_requires_strategy_argument()`
  - Run: `tp walk-forward-validate` (no arguments)
  - Assert error: "--strategy is required"
- Add test: `test_walk_forward_validate_runs_and_prints_results(tmp_path, capsys)`
  - Create minimal strategy config and test data
  - Run: `tp walk-forward-validate --strategy {config} --data {data} --periods year`
  - Assert output contains performance results for each test period
  - Assert consistency check result is printed

### 24. [ ] Implement walk-forward validation CLI command
- Edit file: `src/trading_platform/cli.py`
- Add function: `def _walk_forward_validate_logic(args: argparse.Namespace) -> int:`
  - Load strategy config from `args.strategy`
  - Load data from `args.data`
  - Split data into periods using `split_into_periods(data, args.periods)`
  - Define training function that calls `tp train-profitability-models` and `tp train-diagnostic-models`
  - Define backtest function that calls `run_backtest()` from existing code
  - Call `walk_forward_validate()` with data and functions
  - Print results table showing performance by period
  - Check consistency using `check_performance_consistency()`
  - Print consistency assessment
  - Return 0
- Add subparser in `main()`:
  - Subcommand: "walk-forward-validate"
  - Help: "Perform walk-forward validation on a strategy"
  - Argument: `--strategy`, required=True, help="Path to strategy config"
  - Argument: `--data`, required=True, help="Path to master_trade_log.parquet"
  - Argument: `--periods`, default="year", help="Period granularity (year, quarter, month)"
  - Set function: `args.func = _walk_forward_validate_logic`
- Run: `pytest tests/cli/test_walk_forward_validate_command.py --cov=src/trading_platform/cli -v`
- Verify: All tests pass

---

## Part 9: Model Governance Pre-Deployment Checklist

### 25. [ ] Write tests for pre-deployment checklist validator
- Create file: `tests/validation/test_pre_deployment_checklist.py`
- Add test: `test_check_model_baselines_met()`
  - Create mock model performance metrics (R² = 0.3 for profitability, F1 = 0.7 for diagnostic)
  - Define minimum thresholds (R² >= 0.2, F1 >= 0.6)
  - Call: `check_model_baselines(metrics, thresholds)`
  - Assert returns True (baselines met)
- Add test: `test_check_walk_forward_consistency()`
  - Create walk-forward results with consistent positive performance
  - Call: `check_walk_forward_performance(results)`
  - Assert returns True
- Add test: `test_check_predictive_filter_justification()`
  - Create Phase 4 campaign results showing improvement with profitability_threshold=0.5
  - Call: `check_filter_threshold_justified(results, threshold=0.5)`
  - Assert returns True and includes justification text
- Add test: `test_check_git_commit_recorded()`
  - Create strategy config with `git_commit` field
  - Call: `check_git_commit_exists(config)`
  - Assert returns True
- Add test: `test_full_pre_deployment_checklist()`
  - Run all checks together
  - Assert checklist returns dict with all items and their pass/fail status

### 26. [ ] Implement pre-deployment checklist validator
- Create file: `src/trading_platform/validation/pre_deployment.py`
- Import required modules: `from __future__ import annotations`, `from typing import Any`
- Define function `def check_model_baselines(metrics: dict[str, float], thresholds: dict[str, float]) -> bool:`
  - For each metric in thresholds, check if metrics[metric] >= thresholds[metric]
  - Return True if all pass, False otherwise
- Define function `def check_walk_forward_performance(results: dict[str, Any]) -> bool:`
  - Check if all periods have positive Sharpe ratio
  - Return True if consistent
- Define function `def check_filter_threshold_justified(phase4_results: dict[str, Any], threshold: float) -> tuple[bool, str]:`
  - Compare performance with and without predictive filter
  - Check if improvement is statistically significant
  - Return (True, justification_text) if justified
- Define function `def check_git_commit_exists(config: dict[str, Any]) -> bool:`
  - Return "git_commit" in config.get("metadata", {})
- Define function `def run_pre_deployment_checklist(model_metrics: dict, walk_forward_results: dict, phase4_results: dict, strategy_config: dict) -> dict[str, Any]:`
  - Run all checks
  - Return dict with checklist items and their status
- Run: `pytest tests/validation/test_pre_deployment_checklist.py --cov=src/trading_platform/validation/pre_deployment -v`
- Verify: 100% test coverage achieved

### 27. [ ] Write tests for pre-deployment checklist CLI command
- Create file: `tests/cli/test_pre_deployment_checklist_command.py`
- Add test: `test_pre_deployment_checklist_requires_arguments()`
  - Run: `tp pre-deployment-checklist` (no arguments)
  - Assert error listing required arguments
- Add test: `test_pre_deployment_checklist_prints_results(capsys, tmp_path)`
  - Create mock data for all checklist items
  - Run command
  - Assert output contains checkbox list with pass/fail status for each item
  - Assert overall pass/fail recommendation is printed

### 28. [ ] Implement pre-deployment checklist CLI command
- Edit file: `src/trading_platform/cli.py`
- Add function: `def _pre_deployment_checklist_logic(args: argparse.Namespace) -> int:`
  - Load model metrics from `args.model_metrics`
  - Load walk-forward results from `args.walk_forward_results`
  - Load Phase 4 results from `args.phase4_results`
  - Load strategy config from `args.strategy_config`
  - Call `run_pre_deployment_checklist()` with all inputs
  - Print checklist with checkbox format:
    - "☑" for passed items
    - "☐" for failed items
  - Print overall recommendation: "READY FOR DEPLOYMENT" or "NOT READY - Address failed items"
  - Return 0 if all pass, 1 if any fail
- Add subparser in `main()`:
  - Subcommand: "pre-deployment-checklist"
  - Help: "Validate strategy against pre-deployment checklist"
  - Argument: `--model-metrics`, required=True, help="Path to model performance metrics JSON"
  - Argument: `--walk-forward-results`, required=True, help="Path to walk-forward validation results JSON"
  - Argument: `--phase4-results`, required=True, help="Path to Phase 4 optimization results JSON"
  - Argument: `--strategy-config`, required=True, help="Path to final strategy config YAML"
  - Set function: `args.func = _pre_deployment_checklist_logic`
- Run: `pytest tests/cli/test_pre_deployment_checklist_command.py --cov=src/trading_platform/cli -v`
- Verify: All tests pass

---

## Part 10: Integration Testing and Documentation

### 29. [ ] Create end-to-end integration test
- Create file: `tests/integration/test_full_research_workflow.py`
- Add test: `test_phase0_to_phase1_workflow(tmp_path)`
  - Phase 0: Validate data using `validate-data` command
  - Phase 1: Generate meta-campaign, run one campaign, publish results
  - Assert master_trade_log.parquet is created with expected structure
- Add test: `test_phase1_to_phase2_workflow(tmp_path)`
  - Phase 1: Use existing master_trade_log from previous test
  - Phase 2: Train models, validate against test set
  - Assert model files are created and metrics meet baseline
- Add test: `test_phase4_optimization_workflow(tmp_path)`
  - Phase 4: Create focused campaign with profitability_threshold grid
  - Run campaign and analyze results
  - Assert optimal threshold is identified
- Add test: `test_phase5_walk_forward_workflow(tmp_path)`
  - Phase 5: Run walk-forward validation
  - Assert results show consistency across periods
- Add test: `test_pre_deployment_workflow(tmp_path)`
  - Run pre-deployment checklist with all artifacts from previous phases
  - Assert checklist passes

### 30. [ ] Run all integration tests
- Run: `pytest tests/integration/ -v --cov=src/trading_platform`
- Verify: All integration tests pass
- Verify: Overall test coverage remains at or above current level

### 31. [ ] Update research workflow documentation
- Edit file: `docs/working/campaign_config_refactor_plan.md`
- Add new section: "Implementation Status"
- Document:
  - CLI commands implemented
  - Module locations
  - Test coverage achieved
  - Example usage for each research phase

### 32. [ ] Create quickstart guide
- Create file: `docs/quickstart_meta_campaign_workflow.md`
- Include:
  - Overview of the 6-phase research lifecycle
  - Step-by-step instructions for Phase 0-1 (getting started)
  - Example commands with actual file paths
  - Expected outputs at each step
  - Links to detailed documentation for each phase

### 33. [ ] Run full test suite and verify coverage
- Run: `pytest --cov=src/trading_platform --cov-report=term-missing --cov-report=html`
- Verify: Overall test coverage is at least 95%
- Verify: All new modules have 100% coverage
- Review coverage report: `open htmlcov/index.html`

### 34. [ ] Create pull request
- Run: `git add -A`
- Run: `git commit -m "feat: Implement meta-campaign system for ML model training workflow

## Summary
Implements a two-stage meta-campaign system that automates campaign generation
for comprehensive ML model training. The system supports the full research
lifecycle from data validation through walk-forward validation and deployment.

## Changes

### Core Features
- MetaCampaignConfig data model for high-level campaign specification
- Campaign generator utility with cartesian product calculation
- CLI command: tp meta-campaign-plan for automated config generation
- Strategy profiles supporting both "with risk" and "no risk" configurations

### Research Workflow Support
- Phase 0: Data integrity validation utility and CLI command
- Phase 5: Walk-forward validation framework and CLI command
- Pre-deployment checklist validation and CLI command

### Configuration
- config/master_data_generation/ for stable, versioned strategy configs
- config/meta_campaigns/ for high-level meta-campaign definitions
- Example meta-campaign configuration for trend-following models

## Testing
- 100% test coverage for all new modules
- Integration tests for end-to-end workflow
- CLI command tests for all new commands

## Documentation
- User guide for meta-campaign system
- Quickstart guide for research workflow
- Updated CLI reference documentation

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"`
- Run: `git push -u origin feature/meta-campaign-system`
- Create pull request with title: "Implement Meta-Campaign System for ML Model Training"
- In PR description, include:
  - Link to `docs/working/campaign_config_refactor_plan.md`
  - Summary of features implemented
  - Test coverage report
  - Example usage

---

## Completion Checklist

All tasks must be completed in order. After completing all tasks:

- [ ] All tests pass: `pytest`
- [ ] Test coverage ≥ 95%: `pytest --cov=src/trading_platform --cov-report=term`
- [ ] Type checking passes: `mypy src/trading_platform`
- [ ] Linting passes: `ruff check src/trading_platform`
- [ ] Documentation is complete and accurate
- [ ] Pull request is created and ready for review

---

**End of Implementation Plan**
