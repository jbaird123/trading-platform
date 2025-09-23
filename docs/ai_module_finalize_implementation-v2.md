# AI Module Finalization & Enhancement Plan (v2)

**Objective:** This document provides a precise, ordered set of tasks for a developer to correct existing deficiencies in the AI Module and implement required future enhancements. There is no room for ambiguity; follow these instructions exactly as written.

---

## **Part 1: Corrective Actions for Existing Implementation (Tasks 1-6)**

### **Task 1: Fix Critical Data Gap in CLI**

-   **File to Modify:** `src/trading_platform/cli.py`
-   **Function to Modify:** `cmd_ai_diagnose`
-   **Action:**
    1.  Locate the `analysis_data` dictionary within the `cmd_ai_diagnose` function.
    2.  Delete the existing dictionary assignment.
    3.  Replace it with the following line to pass the *entire* loaded brief to the engine:
        ```python
        analysis_data = brief_data
        ```
-   **File to Modify:** `src/trading_platform/ai/synthesis/engine.py`
-   **Class to Modify:** `DiagnosticSynthesisEngine`
-   **Action:**
    1.  The `__init__` method currently accepts `analysis_data`. This will now be the full brief.
    2.  The `run` method iterates through rules and calls `rule.evaluate(self.analysis_data)`. This is correct and does not need to be changed. The rules themselves will now be responsible for accessing the sections they need from the full brief.

### **Task 2: Implement `DataQualityImpactRule` Logic**

-   **File to Modify:** `src/trading_platform/reporting/brief.py`
-   **Function to Modify:** `compute_data_quality`
-   **Action:**
    1.  You will add a `quality_score` to the `result` dictionary returned by this function.
    2.  This score must be a float between `0.0` and `1.0`.
    3.  Calculate the score using the following logic:
        -   Start with a `score` of `1.0`.
        -   If `result["has_nans"]` is `True`, subtract `0.5` from the `score`.
        -   Calculate a penalty for duplicate bars: `duplicate_penalty = min(0.5, result["duplicate_bars_count"] / 1000.0)`.
        -   Subtract `duplicate_penalty` from the `score`.
        -   Ensure the final score is not less than `0.0`.
    4.  Add the final calculated score to the dictionary: `result["quality_score"] = score`.
-   **File to Modify:** `tests/data/test_data_normalization.py` (or a more appropriate test file if one exists for `brief.py`)
-   **Action:**
    1.  Add a new test function `test_compute_data_quality_score`.
    2.  In this test, create a sample DataFrame with a known number of `NaN` values and duplicate index entries.
    3.  Call `compute_data_quality` with this DataFrame.
    4.  Assert that the returned dictionary contains a `quality_score` key with the correctly calculated value based on the logic defined above.

### **Task 3: Generalize `StrategyParameterOptimizationOpportunityRule`**

-   **File to Modify:** `src/trading_platform/ai/synthesis/rules.py`
-   **Class to Modify:** `StrategyParameterOptimizationOpportunityRule`
-   **Action:**
    1.  Modify the `__init__` method to remove the hardcoded `param_defaults`.
    2.  Modify the `evaluate` method. The rule must now trigger if any value within the `analysis_data.get("strategy_params", {})` dictionary is `None`.
    3.  The `summary` and `evidence` should report the specific parameters that were found to be `None`.
-   **File to Modify:** `tests/ai/synthesis/test_rules.py`
-   **Action:**
    1.  Rewrite the tests for this rule (`test_strategy_param_optimization_rule_*`).
    2.  The "triggered" test must now pass a `strategy_params` dictionary where one of the values is `None`.
    3.  The "not triggered" test must pass a `strategy_params` dictionary where all values are non-`None` (e.g., numbers or strings).

### **Task 4: Refactor `InefficientExitsRule` Logic**

-   **File to Modify:** `src/trading_platform/ai/synthesis/rules.py`
-   **Class to Modify:** `InefficientExitsRule`
-   **Action:**
    1.  The `evaluate` method currently uses an `if/elif` structure that prevents multiple findings. You will refactor this.
    2.  Create an empty list called `conclusions`.
    3.  Evaluate the `model_analysis` branch. If it triggers, create a `DiagnosticConclusion` and append it to the `conclusions` list.
    4.  Separately, evaluate the `trades` analysis branch. If it triggers, create a `DiagnosticConclusion` and append it to the `conclusions` list.
    5.  At the end of the method, if the `conclusions` list is empty, return `None`.
    6.  If the `conclusions` list contains one or more items, combine their titles and summaries into a single, comprehensive `DiagnosticConclusion` object and return that. The `evidence` should merge the evidence from all triggered conclusions.

### **Task 5: Clean Up Redundant and Out-of-Scope Rules**

-   **File to Modify:** `src/trading_platform/ai/synthesis/rules.py`
-   **Action:**
    1.  Delete the entire `OverTradingRule` class definition.
    2.  Delete the entire `RecommendationRule` class definition.
    3.  In the `get_all_rules` function, remove `OverTradingRule()` and `RecommendationRule()` from the returned list.
-   **File to Modify:** `tests/ai/synthesis/test_rules.py`
-   **Action:**
    1.  Delete the test functions `test_recommendation_rule_triggered` and `test_recommendation_rule_not_triggered`.
    2.  Delete all test functions related to `OverTradingRule`.

### **Task 6: Verify End-to-End Integration**

-   **File to Modify:** `tests/cli/test_cli_ai_diagnose.py`
-   **Action:**
    1.  Create a new test function `test_cmd_ai_diagnose_triggers_specific_rule`.
    2.  In this test, create a `brief.json` file that contains data specifically designed to trigger one of the newly fixed rules (e.g., `SignalPersistenceRule`). This means the brief must include a `signal_quality_analysis` section with a high `signal_persistence_pct`.
    3.  Run `cmd_ai_diagnose` on this brief.
    4.  Assert that the generated `ai_diagnostic_report.md` contains the title and summary from the triggered `SignalPersistenceRule`. This will prove that the data is now flowing correctly from the CLI all the way to the rules engine.

---

## **Part 2: Implementation of New Features (Tasks 7-12)**

### **Task 7: Implement Automated Recommendations**

-   **File to Create:** `src/trading_platform/ai/synthesis/recommendations.py`
-   **Action:**
    1.  Create a `BaseRecommendation` class.
    2.  Create a `Recommendation` data class with fields: `title`, `summary`, `category` (e.g., "Entry Logic", "Exit Logic", "Risk Management"), and `confidence` (float `0.0` to `1.0`).
    3.  Create a function `generate_recommendations(conclusions: list[DiagnosticConclusion]) -> list[Recommendation]`.
    4.  Inside this function, map specific `DiagnosticConclusion` titles to concrete `Recommendation` objects. For example:
        -   If a conclusion title is "Market Regime Mismatch Detected", return a `Recommendation` with the title "Add Regime Filter" and summary "Consider filtering entry signals based on the market regimes where the strategy performs poorly."
        -   If a conclusion title is "Signal Persistence Detected", return a `Recommendation` with the title "Refine Entry/Exit Conditions" and summary "The signals are states, not events. Refine the logic to produce discrete entry/exit triggers instead of persistent `long`/`short` states."
-   **File to Modify:** `src/trading_platform/ai/synthesis/engine.py`
-   **Action:**
    1.  Import `generate_recommendations`.
    2.  After `self.conclusions = ...` in the `run` method, add a new line: `self.recommendations = generate_recommendations(self.conclusions)`.
    3.  Update `generate_report_markdown` and `generate_report_json` to include a new "Recommendations" section based on `self.recommendations`.
-   **File to Create:** `tests/ai/synthesis/test_recommendations.py`
-   **Action:** Write unit tests to verify that `generate_recommendations` produces the correct `Recommendation` objects for given `DiagnosticConclusion` inputs.

### **Task 8: Update Project Requirements Documentation**

-   **File to Modify:** `docs/project_requirements.md`
-   **Action:**
    1.  Review the `AI Lab (AI)` section ([AI-10]) and the `JSON Brief Schema` section ([JSON-11]).
    2.  Ensure all newly implemented features and data points from the tasks above are documented.
    3.  Specifically, add a schema definition for the `recommendations` object in the JSON brief.
    4.  Add a requirement for the `quality_score` in the `data_quality` section.

### **Task 9: Enhance Diagnostic Report Output**

-   **File to Modify:** `src/trading_platform/ai/synthesis/engine.py`
-   **Function to Modify:** `generate_report_markdown`
-   **Action:**
    1.  The report currently lists conclusions. Modify the formatting to be more structured.
    2.  For each conclusion, list its `title`, `summary`, and then format the `evidence` dictionary as a bulleted list for readability.
    3.  Add the new "Recommendations" section generated in Task 7 to the top of the report, as it is the most actionable information.

### **Task 10: Create AI Module Documentation**

-   **File to Create:** `docs/ai/01_architecture.md`
-   **Action:** Write a document that explains the high-level architecture of the AI module. It must include:
    1.  A description of the `ai-diagnose` CLI command.
    2.  An explanation of the `DiagnosticSynthesisEngine`.
    3.  A description of the rule-based system (`BaseDiagnosticRule`).
    4.  A diagram showing the data flow: `brief.json` -> `DiagnosticSynthesisEngine` -> `Conclusions` -> `Recommendations` -> `Reports`.
-   **File to Create:** `docs/ai/02_diagnostic_rules.md`
-   **Action:** Create a document that lists every single `BaseDiagnosticRule` implemented in the system. For each rule, you must document:
    1.  Its purpose (e.g., "Detects potential over-trading").
    2.  The specific `brief.json` fields it uses.
    3.  The exact logic it uses to trigger.

### **Task 11: Integrate AI Module Tests into CI**

-   **File to Modify:** `.github/workflows/ci.yml`
-   **Action:**
    1.  Review the `pytest` step in the workflow.
    2.  Ensure that the tests for the AI module (under `tests/ai/` and `tests/cli/`) are not being excluded and are running as part of the main test suite. No action is needed if they are already included, but you must verify this.

### **Task 12: Final Code Quality & Coverage Check**

-   **Action:**
    1.  Run `poetry run ruff check .` and fix any reported issues in the files you have modified.
    2.  Run `poetry run mypy .` and fix any type-related errors in the files you have modified.
    3.  Run `poetry run pytest --cov=src/trading_platform` and ensure that test coverage for the files you modified is at or near 100%. Add any missing test cases required to meet this standard.
