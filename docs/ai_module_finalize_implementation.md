# AI Module Finalization: Comprehensive Task List

This document outlines the detailed tasks required to fully implement and finalize the AI Module, ensuring it is a robust, fully-featured, and production-ready component of the trading platform. This list aims for no shortcuts, covering testing, core functionality, data integration, and advanced features.


## 1. Core CLI Integration & Testing

- [x] **1.1. Implement `ai-diagnose` CLI Command Test:**
    - [x] **1.1.1.** Create `tests/cli/test_cli_ai_diagnose.py`.
    - [x] **1.1.2.** Add a test case `test_cmd_ai_diagnose_success` to verify the command's basic functionality (takes brief, generates reports, returns 0).
    - [x] **1.1.3.** Add test cases for error handling (e.g., `--brief` not provided, invalid brief path, malformed JSON).
    - [x] **1.1.4.** Ensure test covers output file creation and basic content validation (e.g., "No specific issues" for a benign brief).

## 2. Diagnostic Rules Enhancement (src/trading_platform/ai/synthesis/rules.py)

- [ ] **2.1. Implement `LowWinRateHighTradesRule`:**
    - [ ] **2.1.1.** Create a new rule class in `rules.py` that triggers if `overall_performance.win_rate` is below a configurable threshold AND `overall_performance.n_trades` is above a configurable threshold (even if `n_trades` is not "unusually high" like 500).
    - [ ] **2.1.2.** Add this rule to `get_all_rules()`.
    - [ ] **2.1.3.** Add a corresponding test case in `tests/ai/synthesis/test_rules.py` to verify its behavior.
- [ ] **2.2. Enhance `InefficientExitsRule` (requires data from 3.x):**
    - [ ] **2.2.1.** Refine the rule to analyze `mfe_currency` and `mae_currency` from individual trades in `brief.json` to identify trades where potential profit was left on the table or losses were excessive post-entry.
    - [ ] **2.2.2.** Integrate with `model_analysis` data once available (Task 3.x).
    - [ ] **2.2.3.** Add a corresponding test case in `tests/ai/synthesis/test_rules.py`.
- [ ] **2.3. Implement `StrategyParameterOptimizationOpportunityRule`:**
    - [ ] **2.3.1.** Create a rule that checks if key strategy parameters (e.g., `fast`, `slow` for EMA crossover) are `null` or default values in `brief.json.strategy_params`, suggesting they haven't been optimized.
    - [ ] **2.3.2.** Add this rule to `get_all_rules()`.
    - [ ] **2.3.3.** Add a corresponding test case in `tests/ai/synthesis/test_rules.py`.
- [ ] **2.4. Implement `SignalPersistenceRule` (requires data from 3.x):**
    - [ ] **2.4.1.** Create a rule to analyze `signal_quality_analysis` data (once available from Task 3.x) to detect if signals are persistent states rather than discrete events.
    - [ ] **2.4.2.** Add this rule to `get_all_rules()`.
    - [ ] **2.4.3.** Add a corresponding test case in `tests/ai/synthesis/test_rules.py`.
- [ ] **2.5. Implement `MarketRegimeMismatchRule` (requires data from 3.x):**
    - [ ] **2.5.1.** Create a rule that identifies if the strategy performed poorly in specific market regimes (using `brief.json.regimes` data).
    - [ ] **2.5.2.** Add this rule to `get_all_rules()`.
    - [ ] **2.5.3.** Add a corresponding test case in `tests/ai/synthesis/test_rules.py`.
- [ ] **2.6. Implement `DataQualityImpactRule`:**
    - [ ] **2.6.1.** Create a rule that flags significant data quality issues (`brief.json.data_quality`) and correlates them with poor performance.
    - [ ] **2.6.2.** Add this rule to `get_all_rules()`.
    - [ ] **2.6.3.** Add a corresponding test case in `tests/ai/synthesis/test_rules.py`.

## 3. Data Integration & Generation for AI Analysis

- [ ] **3.1. Generate `MFE/MAE` for all trades in `brief.json`:**
    - [ ] **3.1.1.** Modify `src/trading_platform/portfolio/portfolio.py` and/or `src/trading_platform/backtester/core.py` to calculate `mfe_currency` and `mae_currency` for *all* trades (not just closed ones, if applicable) and ensure they are correctly populated in `brief.json.trades`.
    - [ ] **3.1.2.** Add a test case in `tests/portfolio/test_mfe_mae_bars.py` (or similar) to verify correct calculation and serialization.
- [ ] **3.2. Generate `model_analysis` data for `brief.json`:**
    - [ ] **3.2.1.** Define the schema for `brief.json.model_analysis` (e.g., `avg_pnl_left_on_table_at_tp`, `avg_loss_avoided_by_stop`).
    - [ ] **3.2.2.** Modify `src/trading_platform/core/run.py` (`finalize_run`) to compute and include this data. This will likely involve new logic in `backtester/core.py` or a new utility.
    - [ ] **3.2.3.** Add a test case to verify the presence and correctness of this section in `brief.json`.
- [ ] **3.3. Generate `signal_quality_analysis` data for `brief.json`:**
    - [ ] **3.3.1.** Define the schema for `brief.json.signal_quality_analysis` (e.g., `signal_persistence_pct`, `avg_signal_duration_bars`).
    - [ ] **3.3.2.** Modify `src/trading_platform/core/run.py` (`finalize_run`) to compute and include this data, potentially using `signals.parquet` as input.
    - [ ] **3.3.3.** Add a test case to verify the presence and correctness of this section in `brief.json`.
- [ ] **3.4. Ensure `regimes` data is fully populated in `brief.json`:**
    - [ ] **3.4.1.** Verify that `brief.json.regimes` accurately reflects performance per market regime.
    - [ ] **3.4.2.** Add tests to ensure this section is always present and correct when RMM is used.

## 4. Advanced AI Module Features

- [ ] **4.1. Implement Automated Recommendations:**
    - [ ] **4.1.1.** Extend `DiagnosticSynthesisEngine` to generate actionable recommendations (e.g., "Consider adding an ADX filter to entry rules").
    - [ ] **4.1.2.** Define a schema for recommendations within the JSON report.
    - [ ] **4.1.3.** Implement a `RecommendationRule` class that suggests specific changes based on detected flaws.
    - [ ] **4.1.4.** Add tests for recommendation generation.
- [ ] **4.2. Integrate AI Model for Deeper Analysis (Use Case #1):**
    - [ ] **4.2.1.** Train a simple AI model (e.g., Logistic Regression or RandomForest) to predict trade profitability based on `entry_context` features.
    - [ ] **4.2.2.** Integrate this model into `DiagnosticSynthesisEngine` to provide more nuanced insights (e.g., "This trade was unprofitable because of X, Y, Z features").
    - [ ] **4.2.3.** Implement SHAP or other interpretability methods to explain model predictions within the diagnostic report.
- [ ] **4.3. Implement AI-Driven Parameter Suggestion:**
    - [ ] **4.3.1.** Develop a component that suggests optimized strategy parameters based on backtest results and diagnostic findings.
    - [ ] **4.3.2.** Integrate with the parameter search functionality.

## 5. Documentation & Reporting Refinements

- [ ] **5.1. Update `docs/project_requirements.md`:**
    - [ ] **5.1.1.** Ensure all new AI module features and data points are reflected in the `AI Lab (AI)` section and `JSON Brief Schema` section.
- [ ] **5.2. Enhance Diagnostic Report Output:**
    - [ ] **5.2.1.** Improve the human-readable Markdown report for clarity and actionable insights.
    - [ ] **5.2.2.** Add links to relevant sections of the `brief.json` or other artifacts within the Markdown report.
    - [ ] **5.2.3.** Consider generating simple visualizations directly within the Markdown report (e.g., ASCII charts or links to generated plots).
- [ ] **5.3. Comprehensive AI Module Documentation:**
    - [ ] **5.3.1.** Create a dedicated `docs/ai/` section detailing the architecture, data flow, rule definitions, and usage of the AI module.

## 6. Continuous Integration & Quality Assurance

- [ ] **6.1. Integrate AI Module Tests into CI:**
    - [ ] **6.1.1.** Ensure all new AI module tests run as part of the GitHub Actions CI pipeline (`.github/workflows/ci.yml`).
- [ ] **6.2. Code Quality & Standards:**
    - [ ] **6.2.1.** Ensure all new AI module code adheres to project coding standards (ruff, mypy, 88-column limit).
    - [ ] **6.2.2.** Maintain 100% test coverage for all new AI module code.
