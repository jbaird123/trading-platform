# Profitability and Diagnostic Model Refactor Plan (v4)

This document outlines the tasks required to refactor the ML models. The plan includes changing the ProfitabilityModel to a regressor, making the PerformanceDiagnosticModel adaptable, and implementing strict, context-aware guardrails for data validation and lookahead bias prevention.

**Developer:** Before starting, create a new branch named `feature/refactor-ml-models-v4`.

---

## Part 1: Refactor `ProfitabilityModel` (Prediction Engine)

1.  [ ] **Create Failing Tests for Strict Validation:** In `tests/ai/models/test_profitability.py`, add `test_fit_raises_error_on_missing_r_multiple` and `test_fit_raises_error_on_invalid_stop_loss`.

2.  [ ] **Implement Strict Validation in `fit`:** In `src/trading_platform/ai/models/profitability.py`, modify the `fit` method to raise detailed `ValueError` exceptions if `r_multiple` is null or `initial_stop_loss_pips` is null or non-positive.

3.  [ ] **Implement `RandomForestRegressor`:** In `src/trading_platform/ai/models/profitability.py`, refactor the class to use `RandomForestRegressor`, update type hints, and initialize the new model class in `fit`.

4.  [ ] **Implement Regression Target:** In the `fit` method, change the target to `y = df["r_multiple"].values`.

5.  [ ] **Remove `predict_proba` Method:** Delete the `predict_proba` method from `ProfitabilityModel` and remove its corresponding tests.

6.  [ ] **Implement Risk Feature Extraction:** In the `_extract_features` method, ensure `initial_stop_loss_pips` is added to the list of features.

## Part 2: Refactor `PerformanceDiagnosticModel` to be Adaptable

7.  [ ] **Create Test for Adaptable Target:** In `tests/ai/models/test_performance_diagnostic.py`, add `test_can_fit_with_pnl_target` to verify the model can be initialized with `target_metric='pnl'`.

8.  [ ] **Implement Adaptable `__init__`:** In `src/trading_platform/ai/models/performance_diagnostic.py`, modify `__init__` to accept `target_metric: str = 'r_multiple'`.

9.  [ ] **Implement Dynamic `fit` Method:** In the `fit` method, replace hardcoded `"r_multiple"` references with `self.target_metric` for validation checks and target assignment.

## Part 3: Refactor `ModelRegistry` for Advanced Training & Analysis

10. [ ] **Create Test for Segregated Training:** In `tests/ai/models/test_registry.py`, write `test_train_all_diagnostic_models_segregates_by_risk`. Assert that training on mixed data produces models with distinct keys (e.g., `_rmultiple`, `_pnl_with_risk`, `_pnl_no_risk`).

11. [ ] **Implement Segregated Training:** In `src/trading_platform/ai/models/registry.py`, refactor `train_all_diagnostic_models` to partition the data based on `r_multiple`'s presence and train the three distinct model sub-types.

12. [ ] **Create Tests for Context-Aware Guardrail:** In `test_registry.py`, add tests for `analyze_performance_regime` that assert a `ValueError` is raised if a model is used on the wrong type of data (e.g., a `_no_risk` model used on data that has `r_multiple` values).

13. [ ] **Implement `analyze_performance_regime`:** In `registry.py`, create the new `analyze_performance_regime` method, which includes the logic to load the correct model sub-type and validate that the input data matches the model's training context.

## Part 4: Implement Lookahead Bias Guardrail

14. [ ] **Create Test for Date Recording:** In `tests/ai/models/test_profitability.py` and `test_performance_diagnostic.py`, add a `test_fit_records_training_date_range` to assert that `model.training_start_date_` and `model.training_end_date_` are set after fitting.

15. [ ] **Implement Date Recording:** In the `fit` method of both `profitability.py` and `performance_diagnostic.py`, add logic to find the min/max of the `entry_time` column and store them as attributes on the model instance.

16. [ ] **Create Test for Date Persistence:** Add a test to ensure the new date attributes are correctly saved and loaded with the model via `save()` and `load()`.

17. [ ] **Implement Date Persistence:** In both model files, update the `save` and `load` methods to include `training_start_date_` and `training_end_date_` in the serialized dictionary.

18. [ ] **Create Test for Lookahead Guardrail:** In `test_registry.py`, add `test_predict_profitability_raises_lookahead_error`. This test must assert that calling `predict_profitability` with data dated *before* the model's `training_end_date_` raises a `ValueError`.

19. [ ] **Implement Lookahead Guardrail:** In `registry.py`, modify `predict_profitability` and `analyze_performance_regime`. Add a check at the beginning of each method to compare the input data's timestamps against the model's `training_end_date_` and raise a clear `ValueError` if an overlap is detected.

## Part 5: Update Documentation and Downstream Code

20. [ ] **Update All Docstrings:** Update docstrings for all modified classes (`ProfitabilityModel`, `PerformanceDiagnosticModel`, `ModelRegistry`) to reflect new logic, parameters, and guardrails.

21. [ ] **Identify and Refactor Downstream Code:** Search for usages of `predict_profitability` and `predict_profitability_proba`. Update all logic to handle the new `r_multiple` float output.

## Part 6: (Optional but Recommended) Implement Confidence Intervals

22. [ ] **Create Test for Confidence Interval Method:** In `test_profitability.py`, add a test for a new `predict_with_confidence` method, asserting the output is a DataFrame with the correct columns (`prediction`, `std`, etc.).

23. [ ] **Implement `predict_with_confidence`:** In `profitability.py`, add the new method to calculate a prediction and standard deviation from the estimators in the `RandomForestRegressor`.
