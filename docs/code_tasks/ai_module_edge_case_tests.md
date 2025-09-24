# AI Module Edge Case and Robustness Testing

**Objective:** This document provides a precise, ordered set of tasks for a developer to improve the robustness of the AI module by adding tests for edge cases, malformed data, and unexpected inputs.

---

### **Task 1: Harden `Parameter Suggester`**

-   **File to Modify:** `tests/ai/lab/test_param_suggester.py`
-   **Action:**
    -   1.1 Add a new test function `test_suggest_parameters_malformed_results`. In this test, pass a `brief` where `brief["parameter_search"]["results"]` is a list containing dictionaries that are missing the `objective_score` or `parameters` keys. Assert that the function handles this gracefully and returns an empty dictionary.
    -   1.2 Add a new test function `test_suggest_parameters_empty_brief`. In this test, pass an empty dictionary `{}` as the `brief`. Assert that the function returns an empty dictionary.

---

### **Task 2: Harden `Model Trainer`**

-   **File to Modify:** `tests/ai/lab/test_trainer.py`
-   **Action:**
    -   2.1 Add a new test function `test_train_profitability_model_no_trades`. In this test, pass a `brief` containing an empty `trades` list (`{"trades": []}`). Assert that the function raises a `ValueError`.
    -   2.2 Add a new test function `test_train_profitability_model_no_entry_context`. In this test, pass a list of trades where some or all are missing the `entry_context` key. Assert that the function runs without error and successfully trains a model on the available data.
    -   2.3 Add a new test function `test_train_profitability_model_empty_entry_context`. In this test, pass a list of trades where `entry_context` is an empty dictionary. Assert that the function runs without error.

---

### **Task 3: Harden `Insight Predictor`**

-   **File to Modify:** `tests/ai/lab/test_predictor.py`
-   **Action:**
    -   3.1 Add a new test function `test_get_trade_insights_missing_context`. In this test, call `get_trade_insights` with a `trade` dictionary that is missing the `entry_context` key. Assert that the function returns a valid dictionary structure with default or `None` values and does not raise an error.
    -   3.2 Add a new test function `test_get_trade_insights_feature_mismatch`. In this test, the `features` list passed to the function should contain feature names that are not present in the trade's `entry_context`. Assert that the function handles these missing values gracefully (e.g., by treating them as `NaN`) and returns a valid insight dictionary without error.

---

### **Task 4: Harden `Diagnostic Rules`**

-   **File to Modify:** `tests/ai/synthesis/test_rules.py`
-   **Action:**
    -   4.1 For each diagnostic rule, add a new test case to verify its behavior when the part of the brief it depends on is missing. The rule should return `None` without raising an error.
    -   4.2 **Example for `SignalPersistenceRule`**: Create a new test function `test_signal_persistence_rule_missing_key`. In this test, pass `analysis_data = {}` to the rule's `evaluate` method. Assert that the result is `None`.
    -   4.3 **Apply this pattern** to all other rules in the file: `InefficientExitsRule` (test with missing `model_analysis`), `LowWinRateHighTradesRule` (test with missing `backtest_metrics`), `StrategyParameterOptimizationOpportunityRule` (test with missing `strategy_params`), `MarketRegimeMismatchRule` (test with missing `regimes`), and `DataQualityImpactRule` (test with missing `data_quality`).

---

### **Task 5: Harden `Diagnostic Engine`**

-   **File to Create/Modify:** `tests/ai/synthesis/test_engine.py`
-   **Action:**
    -   5.1 Create the test file `tests/ai/synthesis/test_engine.py` if it does not already exist.
    -   5.2 Add a new test function `test_engine_with_empty_brief`. In this test, initialize `DiagnosticSynthesisEngine` with `analysis_data={}`. Call the `engine.run()` method and assert that `engine.conclusions` and `engine.recommendations` are empty lists and that no errors were raised.
    -   5.3 Add a new test function `test_engine_with_brief_missing_trades`. In this test, initialize the engine with a `brief` that has no `trades` key. Assert that the engine runs successfully and that the `model_insights` section is an empty list.
