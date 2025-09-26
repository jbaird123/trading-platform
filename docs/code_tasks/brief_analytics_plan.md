# Brief Analytics Implementation Plan

**Objective:** This document provides a precise, test-first implementation plan for a developer to add advanced analytics sections to the `brief.json` output. The developer must follow these tasks in the specified sequence to ensure correctness and 100% test coverage.

---

## 1. Implement Stationarity Analysis ([JSON-F.4])

- [ ] **1.1. Add Dependency:** Add the `statsmodels` library to the project by running the command: `poetry add statsmodels`.

- [ ] **1.2. Create Module Files:** Create the following two empty files:
    1.  `src/trading_platform/reporting/analytics.py`
    2.  `tests/reporting/test_analytics.py`

- [ ] **1.3. Create Test for `compute_stationarity`:** In `tests/reporting/test_analytics.py`, add a test function `test_compute_stationarity`. This test should import the (not-yet-existing) `compute_stationarity` function, pass it a mock list of `Trade` objects, and assert that the function returns a dictionary with the expected keys (`adf_p_value`, `kpss_p_value`) and value types. The test is expected to fail.

- [ ] **1.4. Implement `compute_stationarity`:** In `src/trading_platform/reporting/analytics.py`, create the function `compute_stationarity(trades: list[Trade]) -> dict` to make the test from step 1.3 pass. The function must:
    - Extract the PnL from each trade.
    - If there are fewer than 20 trades, return an empty dictionary.
    - Use `statsmodels.tsa.stattools.adfuller` and `statsmodels.tsa.stattools.kpss` on the PnL series.
    - Return a dictionary with the results, e.g., `{"adf_p_value": 0.04, "kpss_p_value": 0.1}`.

- [ ] **1.5. Create Test for Brief Integration:** In `tests/reporting/test_brief.py`, add a test to `TestGenerateBrief` that asserts that the generated brief contains a `stationarity` key with the structure defined in step 1.4 when mock trades are provided. This test is expected to fail.

- [ ] **1.6. Integrate into Brief:** In `src/trading_platform/reporting/brief.py`, import `compute_stationarity` and call it within the `generate_brief` function. Assign the result to the `stationarity` key in the output dictionary to make the test from step 1.5 pass.

## 2. Implement Feature Analysis ([JSON-F.5] & [JSON-F.6])

- [ ] **2.1. Create Test for `compute_feature_analysis`:** In `tests/reporting/test_analytics.py`, add a test `test_compute_feature_analysis`. This test should pass mock trades with `context_at_entry` data to the (not-yet-existing) `compute_feature_analysis` function and assert that the returned dictionary contains a correctly calculated correlation matrix.

- [ ] **2.2. Implement `compute_feature_analysis`:** In `src/trading_platform/reporting/analytics.py`, create the function `compute_feature_analysis(trades: list[Trade]) -> dict` to make the test from step 2.1 pass. The function must:
    - Extract `context_at_entry` from each trade.
    - Convert the list of contexts to a pandas DataFrame.
    - Calculate the Pearson correlation matrix using `.corr()`.
    - Return the result in a dictionary: `{"feature_correlation_matrix": {...}}`.

- [ ] **2.3. Create Test for Brief Integration:** In `tests/reporting/test_brief.py`, add a test to assert that the generated brief contains a `feature_analysis` key with the expected structure.

- [ ] **2.4. Integrate into Brief:** In `src/trading_platform/reporting/brief.py`, import and call `compute_feature_analysis` within `generate_brief` and assign the result to the `feature_analysis` key.

## 3. Implement Remaining Analytics Functions

- [ ] **3.1. Apply Test-First Pattern for All Remaining Functions:** For each of the features below, the developer must repeat the exact same test-first, two-stage integration pattern used in sections 1 and 2:
    1.  **Write a failing unit test** for the new function in `test_analytics.py`.
    2.  **Implement the function** in `analytics.py` to make the unit test pass.
    3.  **Write a failing integration test** in `test_brief.py` to check for the new key in the final brief.
    4.  **Integrate the function** into `generate_brief` in `brief.py` to make the integration test pass.

- [ ] **3.2. Function: `compute_activity`**
    - **Logic:** Calculates `average_trades_per_day`.
    - **Brief Key:** `activity`

- [ ] **3.3. Function: `compute_timing_buckets`**
    - **Logic:** Calculates aggregate PnL and win-rate grouped by `hour_of_day` and `day_of_week` from trade entry times.
    - **Brief Key:** `timing_buckets`

- [ ] **3.4. Function: `compute_contrasts`**
    - **Logic:** Calculates detailed performance metrics (`n_trades`, `win_rate`, `avg_win`, etc.) for `long_trades` and `short_trades` separately.
    - **Brief Key:** `contrasts`

- [ ] **3.5. Function: `compute_stop_tp_candidates`**
    - **Logic:** Calculates the 25th, 50th, and 75th percentiles of the `mfe_currency` and `mae_currency` distributions across all trades.
    - **Brief Key:** `stop_tp_candidates`
