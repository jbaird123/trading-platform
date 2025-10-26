# Profitability Model Regressor Refactor Plan

This document outlines the tasks required to refactor the `ProfitabilityModel` from a binary classifier to a regressor, and to harden both it and the `PerformanceDiagnosticModel` against data that lacks a defined risk.

**Developer:** Before starting, create a new branch named `feature/refactor-profitability-model`.

---

## Part 1: Refactor `ProfitabilityModel` to a Regressor

1.  [ ] **Create Failing Test for Missing Data:** In `tests/ai/models/test_profitability.py`, add a new test method `test_fit_raises_error_on_missing_r_multiple`.
    *   Inside this test, initialize a `ProfitabilityModel`.
    *   Create a sample DataFrame (e.g., from a dictionary) with all required columns, but ensure at least one row has `np.nan` for the `r_multiple` value.
    *   Use `pytest.raises` to assert that calling `model.fit(your_dataframe)` raises a `ValueError`.

2.  [ ] **Implement Strict Check in `ProfitabilityModel`:** In `src/trading_platform/ai/models/profitability.py`, modify the `fit` method.
    *   After filtering the `df` by context, add a new check:
        ```python
        if df["r_multiple"].isnull().any() or df["initial_stop_loss_pips"].isnull().any():
            raise ValueError(
                f"Training failed for {self.timeframe}_{self.archetype}: The "
                f"ProfitabilityModel requires all trades to have a defined "
                f"initial risk (stop-loss). Found trades with missing "
                f"'r_multiple' or 'initial_stop_loss_pips'. Please filter the "
                f"dataset before training."
            )
        ```

3.  [ ] **Create Failing Test for Model Type:** In `tests/ai/models/test_profitability.py`, add a new test `test_model_is_regressor`.
    *   Fit a `ProfitabilityModel` on a small, valid sample DataFrame.
    *   Assert that `isinstance(model.model, RandomForestRegressor)` is `True`. This test will fail initially.

4.  [ ] **Implement `RandomForestRegressor`:** In `src/trading_platform/ai/models/profitability.py`:
    *   Change the import from `sklearn.ensemble.RandomForestClassifier` to `from sklearn.ensemble import RandomForestRegressor`.
    *   In the `__init__` method, change the type hint for `self.model` to `RandomForestRegressor | None`.
    *   In the `fit` method, change the model initialization to `self.model = RandomForestRegressor(...)`.

5.  [ ] **Create Failing Test for Prediction Output:** In `tests/ai/models/test_profitability.py`, add a new test `test_predict_returns_continuous_values`.
    *   Fit a model on valid data.
    *   Call `model.predict(...)`.
    *   Assert that the output array's `dtype` is `float`, not `int`.

6.  [ ] **Implement Regression Target:** In `src/trading_platform/ai/models/profitability.py`, modify the `fit` method.
    *   Change the target variable creation from `y = (df["pnl"] > 0).astype(int).values` to `y = df["r_multiple"].values`.

7.  [ ] **Create Failing Test for `predict_proba`:** In `tests/ai/models/test_profitability.py`, add a new test `test_predict_proba_is_removed`.
    *   Assert that calling `model.predict_proba(...)` raises an `AttributeError`.

8.  [ ] **Remove `predict_proba` Method:** In `src/trading_platform/ai/models/profitability.py`, delete the entire `predict_proba` method.

9.  [ ] **Create Failing Test for Risk Feature:** In `tests/ai/models/test_profitability.py`, add a new test `test_fit_includes_risk_feature`.
    *   Fit a model on valid data that includes the `initial_stop_loss_pips` column.
    *   Assert that the string `"initial_stop_loss_pips"` is present in `model.feature_names_`.

10. [ ] **Implement Risk Feature Extraction:** In `src/trading_platform/ai/models/profitability.py`, modify the `_extract_features` method.
    *   Add a new step to explicitly include the risk feature:
        ```python
        # After extracting context_at_entry_* columns
        if "initial_stop_loss_pips" in df.columns:
            features.append("initial_stop_loss_pips")
        ```

## Part 2: Harden `PerformanceDiagnosticModel`

11. [ ] **Create Failing Test for Missing Data:** In `tests/ai/models/test_performance_diagnostic.py`, add a new test `test_fit_raises_error_on_missing_r_multiple`.
    *   This test should initialize a `PerformanceDiagnosticModel` and call `fit()` with a DataFrame containing `np.nan` in the `r_multiple` column.
    *   Use `pytest.raises` to assert that this call raises a `ValueError`.

12. [ ] **Implement Strict Check in `PerformanceDiagnosticModel`:** In `src/trading_platform/ai/models/performance_diagnostic.py`, modify the `fit` method.
    *   Remove the lines:
        ```python
        # Remove rows with missing r_multiple (can't classify without target)
        df_clean = df.dropna(subset=["r_multiple"]).copy()

        if len(df_clean) < 50:
            raise ValueError(...)
        ```
    *   Replace them with a single, stricter check that runs on the `df` DataFrame (after context filtering):
        ```python
        if df["r_multiple"].isnull().any():
            raise ValueError(
                f"Training failed for {self.timeframe}_{self.archetype}: The "
                f"PerformanceDiagnosticModel requires all trades to have a defined "
                f"'r_multiple'. Please filter the dataset before training."
            )
        ```
    *   Ensure subsequent code uses `df` instead of `df_clean`.

## Part 3: Update `ModelRegistry`

13. [ ] **Update Test for Removed Method:** In `tests/ai/models/test_registry.py`, locate any tests for `predict_profitability_proba`.
    *   Change the test to assert that calling `registry.predict_profitability_proba(...)` now raises an `AttributeError`.

14. [ ] **Remove Method from Registry:** In `src/trading_platform/ai/models/registry.py`, delete the entire `predict_profitability_proba` method.

15. [ ] **Create Failing Test for Prediction Guardrail:** In `tests/ai/models/test_registry.py`, add a new test `test_predict_profitability_raises_error_on_missing_risk`.
    *   Load or create a fitted `ProfitabilityModel` in the registry.
    *   Create an input DataFrame `X` for prediction that *does not* have the `initial_stop_loss_pips` column.
    *   Use `pytest.raises` to assert that `registry.predict_profitability(X, ...)` raises a `ValueError`.

16. [ ] **Implement Prediction Guardrail:** In `src/trading_platform/ai/models/registry.py`, modify the `predict_profitability` method.
    *   At the beginning of the method, add the guardrail:
        ```python
        if "initial_stop_loss_pips" not in X.columns or (X["initial_stop_loss_pips"] <= 0).any():
            raise ValueError(
                "Cannot predict R-multiple: The input data must include a valid "
                "'initial_stop_loss_pips' column with values greater than 0."
            )
        ```
    *   Update the method's return type hint from `pd.Series` to `pd.Series[float]`.
