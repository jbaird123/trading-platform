# Profitability Model Regressor Refactor Plan (v2)

This document outlines the tasks required to refactor the `ProfitabilityModel` from a binary classifier to a regressor, and to harden both it and the `PerformanceDiagnosticModel` against data that lacks a defined risk. This plan incorporates feedback to improve validation, documentation, and downstream compatibility.

**Developer:** Before starting, create a new branch named `feature/refactor-profitability-model`.

---

## Part 1: Refactor `ProfitabilityModel` to a Regressor

1.  [ ] **Create Failing Test for Missing `r_multiple`:** In `tests/ai/models/test_profitability.py`, add a new test `test_fit_raises_error_on_missing_r_multiple`. This test should create a sample DataFrame where `r_multiple` is `np.nan` and assert that `model.fit()` raises a `ValueError` with a message about missing historical `r_multiple` values.

2.  [ ] **Create Failing Test for Invalid `initial_stop_loss_pips`:** In the same test file, add `test_fit_raises_error_on_invalid_stop_loss`. This test should check for both `np.nan` and non-positive (`<= 0`) values in the `initial_stop_loss_pips` column and assert that `model.fit()` raises a `ValueError` with a message about requiring a valid stop loss > 0.

3.  [ ] **Implement Strict Validation in `fit`:** In `src/trading_platform/ai/models/profitability.py`, modify the `fit` method. After filtering the `df` by context, add the following validation logic:
    ```python
    if df["r_multiple"].isnull().any():
        raise ValueError(
            f"Training failed for {self.timeframe}_{self.archetype}: "
            f"Cannot train without historical 'r_multiple' values. "
            f"Found {df['r_multiple'].isnull().sum()} missing values."
        )

    if df["initial_stop_loss_pips"].isnull().any() or (df["initial_stop_loss_pips"] <= 0).any():
        n_null = df["initial_stop_loss_pips"].isnull().sum()
        n_invalid = (df["initial_stop_loss_pips"] <= 0).sum()
        raise ValueError(
            f"Training failed for {self.timeframe}_{self.archetype}: "
            f"All trades must have a valid 'initial_stop_loss_pips' > 0. "
            f"Found {n_null} null and {n_invalid} invalid values."
        )
    ```

4.  [ ] **Implement `RandomForestRegressor`:** In `src/trading_platform/ai/models/profitability.py`, refactor the class to use `RandomForestRegressor`. This includes changing the import, updating the type hint for `self.model`, and initializing `RandomForestRegressor` in the `fit` method.

5.  [ ] **Implement Regression Target:** In the `fit` method of `profitability.py`, change the target variable creation to `y = df["r_multiple"].values`.

6.  [ ] **Remove `predict_proba` Method:** In `src/trading_platform/ai/models/profitability.py`, delete the entire `predict_proba` method.

7.  [ ] **Implement Risk Feature Extraction:** In the `_extract_features` method of `profitability.py`, ensure the `initial_stop_loss_pips` feature is correctly extracted. The final line of the method must be `return df[features].copy()` to construct the feature DataFrame.

## Part 2: Harden `PerformanceDiagnosticModel`

8.  [ ] **Create Failing Test for Missing `r_multiple`:** In `tests/ai/models/test_performance_diagnostic.py`, add a new test `test_fit_raises_error_on_missing_r_multiple`. It should assert that `model.fit()` raises a `ValueError` if any row is missing an `r_multiple`.

9.  [ ] **Implement Strict Check in `PerformanceDiagnosticModel`:** In `src/trading_platform/ai/models/performance_diagnostic.py`, modify the `fit` method. Replace the existing `dropna()` call with the stricter check:
    ```python
    if df["r_multiple"].isnull().any():
        raise ValueError(
            f"Training failed for {self.timeframe}_{self.archetype}: The "
            f"PerformanceDiagnosticModel requires all trades to have a defined "
            f"'r_multiple'. Found {df['r_multiple'].isnull().sum()} missing values."
        )
    ```
    Ensure subsequent code in the method uses `df` instead of the old `df_clean` variable.

## Part 3: Update `ModelRegistry`

10. [ ] **Remove `predict_profitability_proba`:** In `src/trading_platform/ai/models/registry.py`, delete the entire `predict_profitability_proba` method. Update any corresponding tests in `tests/ai/models/test_registry.py` to assert this method no longer exists.

11. [ ] **Create Failing Test for Prediction Guardrail:** In `tests/ai/models/test_registry.py`, add a new test `test_predict_profitability_raises_error_on_missing_risk`. This test should call `registry.predict_profitability` with input data `X` that is missing or contains invalid (`NaN`, `<= 0`) values in the `initial_stop_loss_pips` column. Assert that a `ValueError` is raised.

12. [ ] **Implement Prediction Guardrail:** In `src/trading_platform/ai/models/registry.py`, modify the `predict_profitability` method to include the improved guardrail at the beginning:
    ```python
    if "initial_stop_loss_pips" not in X.columns:
        raise ValueError(
            "Cannot predict R-multiple: The input data must include "
            "the 'initial_stop_loss_pips' column."
        )

    if X["initial_stop_loss_pips"].isnull().any() or (X["initial_stop_loss_pips"] <= 0).any():
        n_null = X["initial_stop_loss_pips"].isnull().sum()
        n_invalid = (X["initial_stop_loss_pips"] <= 0).sum()
        raise ValueError(
            f"Cannot predict R-multiple: All trades must have a valid "
            f"'initial_stop_loss_pips' > 0. Found {n_null} null and "
            f"{n_invalid} invalid values."
        )
    ```

## Part 4: Update Documentation

13. [ ] **Update `ProfitabilityModel` Docstrings:** In `src/trading_platform/ai/models/profitability.py`, update the class and method docstrings to reflect the change to a regressor that predicts `r_multiple`. Ensure the main class docstring clearly explains the new target and features.

14. [ ] **Update Project READMEs:** Search for and update any `README.md` files within the `src/trading_platform/ai/` directory that refer to the `ProfitabilityModel` as a classifier. Change the description to reflect the new regression approach.

## Part 5: Update Downstream Dependencies

15. [ ] **Identify and Refactor Downstream Code:** Search the codebase for usages of `predict_profitability` and the now-deleted `predict_profitability_proba`.
    *   Update any code that used the old probability output (e.g., `if prob_profitable > 0.6`).
    *   The new logic should use the predicted R-multiple (e.g., `if predicted_r_multiple > 1.5`).
    *   Pay special attention to files like `strategy/ai_strategy.py` and `ai/inference_client.py` if they exist.

## Part 6: (Optional but Recommended) Implement Confidence Intervals

16. [ ] **Create Test for Confidence Interval Method:** In `tests/ai/models/test_profitability.py`, add a new test `test_predict_with_confidence_returns_correct_shape`.
    *   This test should fit a model, call a new `predict_with_confidence` method, and assert that the output is a DataFrame containing the columns `["prediction", "std", "lower_bound", "upper_bound"]`.

17. [ ] **Implement `predict_with_confidence`:** In `src/trading_platform/ai/models/profitability.py`, add the new method as described in the feedback. This method will get the predictions from each individual tree in the forest to calculate a mean and standard deviation.
    ```python
    def predict_with_confidence(self, X: pd.DataFrame) -> pd.DataFrame:
        """Predict R-multiple with confidence intervals.

        Returns:
            DataFrame with columns:
            - prediction: Mean predicted R-multiple
            - std: Standard deviation across trees
            - lower_bound: prediction - 2*std
            - upper_bound: prediction + 2*std
        """
        if self.model is None or self.imputer is None:
            raise ValueError("Model not fitted. Call fit() first.")

        X_features = self._extract_features(X)
        X_aligned = self._align_features(X_features)
        X_imputed = self.imputer.transform(X_aligned)

        all_tree_predictions = np.array([
            tree.predict(X_imputed)
            for tree in self.model.estimators_
        ])

        predictions = all_tree_predictions.mean(axis=0)
        std = all_tree_predictions.std(axis=0)

        return pd.DataFrame({
            "prediction": predictions,
            "std": std,
            "lower_bound": predictions - 2 * std,
            "upper_bound": predictions + 2 * std
        }, index=X.index)
    ```
