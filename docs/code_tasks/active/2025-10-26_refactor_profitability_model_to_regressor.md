# Profitability and Diagnostic Model Refactor Plan (v3)

This document outlines the tasks required to refactor the `ProfitabilityModel` to a regressor and evolve the `PerformanceDiagnosticModel` into a flexible, multi-target tool. This plan ensures strict, context-aware data validation for both training and analysis.

**Developer:** Before starting, create a new branch named `feature/refactor-ml-models-v3`.

---

## Part 1: Refactor `ProfitabilityModel` (Prediction Engine)

1.  [ ] **Create Failing Tests for Strict Validation:** In `tests/ai/models/test_profitability.py`, add:
    *   `test_fit_raises_error_on_missing_r_multiple`: Asserts `model.fit()` raises `ValueError` when `r_multiple` is `np.nan`.
    *   `test_fit_raises_error_on_invalid_stop_loss`: Asserts `model.fit()` raises `ValueError` when `initial_stop_loss_pips` is `np.nan` or `<= 0`.

2.  [ ] **Implement Strict Validation in `fit`:** In `src/trading_platform/ai/models/profitability.py`, modify the `fit` method. After context filtering, add the strict validation logic that raises detailed `ValueError` exceptions if `r_multiple` is null or `initial_stop_loss_pips` is null or non-positive.

3.  [ ] **Implement `RandomForestRegressor`:** In `src/trading_platform/ai/models/profitability.py`, refactor the class to use `RandomForestRegressor`. This includes changing the import, updating `self.model` type hints, and initializing `RandomForestRegressor`.

4.  [ ] **Implement Regression Target:** In the `fit` method, change the target to `y = df["r_multiple"].values`.

5.  [ ] **Remove `predict_proba` Method:** Delete the `predict_proba` method from `ProfitabilityModel` and any corresponding tests.

6.  [ ] **Implement Risk Feature Extraction:** In the `_extract_features` method, ensure `initial_stop_loss_pips` is added to the list of features to be used by the model.

## Part 2: Refactor `PerformanceDiagnosticModel` to be Adaptable

7.  [ ] **Create Test for Adaptable Target:** In `tests/ai/models/test_performance_diagnostic.py`, add a test `test_can_fit_with_pnl_target`. It should initialize the model with `target_metric='pnl'`, fit it on valid data, and succeed.

8.  [ ] **Implement Adaptable `__init__`:** In `src/trading_platform/ai/models/performance_diagnostic.py`, modify the `__init__` method to accept a new parameter, `target_metric: str = 'r_multiple'`, and store it as `self.target_metric`.

9.  [ ] **Implement Dynamic `fit` Method:** In the `fit` method, replace all hardcoded references to `"r_multiple"` with `self.target_metric`. This applies to the strict `isnull()` check and the target variable assignment (`y = self._create_quintile_target(df[self.target_metric].values)`).

## Part 3: Refactor `ModelRegistry` for Advanced Training & Analysis

10. [ ] **Create Test for Segregated Training:** In `tests/ai/models/test_registry.py`, write `test_train_all_diagnostic_models_segregates_by_risk`. Provide a mixed DataFrame (trades with and without `r_multiple`). Assert that `registry.train_all_diagnostic_models` creates and registers models with distinct keys reflecting the three sub-types: `_rmultiple`, `_pnl_with_risk`, and `_pnl_no_risk`.

11. [ ] **Implement Segregated Training:** In `src/trading_platform/ai/models/registry.py`, refactor `train_all_diagnostic_models`. It must:
    *   Partition the input DataFrame into `with_risk_df` (`r_multiple` is not null) and `no_risk_df` (`r_multiple` is null).
    *   Train an `r_multiple` model on `with_risk_df`.
    *   Train a `pnl` model on `with_risk_df`.
    *   Train a `pnl` model on `no_risk_df`.
    *   Use a new keying scheme for registration (e.g., `{timeframe}_{archetype}_{metric}_{risk_context}`).

12. [ ] **Create Tests for Context-Aware Guardrail:** In `test_registry.py`, add tests for a new `analyze_performance_regime` method. Create tests that assert:
    *   Using a `_no_risk` model on data *with* an `r_multiple` raises a `ValueError`.
    *   Using an `_rmultiple` model on data *without* an `r_multiple` raises a `ValueError`.
    *   Using a model on the correct data type succeeds.

13. [ ] **Implement `analyze_performance_regime`:** In `registry.py`, create a new method `analyze_performance_regime(self, trades_df, timeframe, archetype, analysis_type)`.
    *   It must derive the model key from the parameters.
    *   It must implement the context-aware guardrail, checking the `trades_df` to ensure its `r_multiple` status matches the requirement of the loaded model.
    *   If valid, it calls `model.predict()` and returns the analysis.

14. [ ] **Implement Prediction Guardrail for `ProfitabilityModel`:** In `predict_profitability` in `registry.py`, implement the guardrail that raises a `ValueError` if the input data `X` is missing a valid `initial_stop_loss_pips > 0`.

## Part 4: Update Documentation and Downstream Code

15. [ ] **Update All Docstrings:** Update the class and method docstrings for all modified classes (`ProfitabilityModel`, `PerformanceDiagnosticModel`, `ModelRegistry`) to reflect the new logic, parameters, and return values.

16. [ ] **Identify and Refactor Downstream Code:** Search the codebase for usages of `predict_profitability` and `predict_profitability_proba`. Update all logic that consumes the model's output to handle the new `r_multiple` float output instead of a probability.

## Part 5: (Optional but Recommended) Implement Confidence Intervals

17. [ ] **Create Test for Confidence Interval Method:** In `tests/ai/models/test_profitability.py`, add a test for a new `predict_with_confidence` method. Assert the output is a DataFrame with the correct columns (`prediction`, `std`, etc.).

18. [ ] **Implement `predict_with_confidence`:** In `src/trading_platform/ai/models/profitability.py`, add the new method. It should use the predictions from each individual tree in the `RandomForestRegressor` to calculate a mean and standard deviation for the final prediction.
