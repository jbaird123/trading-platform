# Brief Completion Implementation Plan

**Objective:** This document provides a precise, ordered set of tasks for a developer to implement the remaining data sections of the `brief.json`, ensuring that no placeholder fields remain.

---

## 1. Task: Implement Stationarity Analysis ([JSON-F.4])

- [ ] **1.1. Add Dependency:** Add the `statsmodels` library to the project by running the command: `poetry add statsmodels`.
- [ ] **1.2. Create Analytics Module:** Create a new file at `src/trading_platform/reporting/analytics.py`.
- [ ] **1.3. Implement `compute_stationarity`:** In `analytics.py`, create a function `compute_stationarity(trades: list[Trade]) -> dict`. This function must:
    - Extract the PnL from each trade into a list.
    - If the list has fewer than 20 trades, return an empty dictionary.
    - Use `statsmodels.tsa.stattools.adfuller` to perform the Augmented Dickey-Fuller test on the PnL series.
    - Use `statsmodels.tsa.stattools.kpss` to perform the KPSS test on the PnL series.
    - Return a dictionary containing the results, e.g., `{"adf_p_value": 0.04, "kpss_p_value": 0.1}`.
- [ ] **1.4. Integrate into Brief:** Modify `src/trading_platform/reporting/brief.py`. Import `compute_stationarity` and call it inside the `generate_brief` function. The result should be assigned to the `stationarity` key in the `base` dictionary, replacing the empty placeholder.
- [ ] **1.5. Add Tests:** Create a new test file at `tests/reporting/test_analytics.py`. Add a test function `test_compute_stationarity` that provides a mock list of `Trade` objects and asserts that the function returns a dictionary with the expected keys and value types.

## 2. Task: Implement Feature Analysis ([JSON-F.5] & [JSON-F.6])

- [ ] **2.1. Add Dependency:** Ensure `pandas` is a project dependency. If not, run `poetry add pandas`.
- [ ] **2.2. Implement `compute_feature_analysis`:** In `src/trading_platform/reporting/analytics.py`, create a function `compute_feature_analysis(trades: list[Trade]) -> dict`. This function must:
    - Extract the `context_at_entry` dictionary from each trade.
    - If no trades have this context, return an empty dictionary.
    - Convert the list of context dictionaries into a pandas DataFrame.
    - Calculate the Pearson correlation matrix of the numeric columns using `.corr()`.
    - Convert the resulting DataFrame to a dictionary and return it inside a parent dictionary, e.g., `{"feature_correlation_matrix": {...}}`.
- [ ] **2.3. Integrate into Brief:** In `src/trading_platform/reporting/brief.py`, import and call `compute_feature_analysis` within `generate_brief`. Assign the result to the `feature_analysis` key, replacing the placeholder.
- [ ] **2.4. Add Tests:** In `tests/reporting/test_analytics.py`, add a test `test_compute_feature_analysis`. Use mock trades with `context_at_entry` data and assert that the correlation matrix is calculated correctly.

## 3. Task: Implement Activity Metrics

- [ ] **3.1. Implement `compute_activity`:** In `src/trading_platform/reporting/analytics.py`, create a function `compute_activity(trades: list[Trade]) -> dict`. This function must:
    - If no trades are provided, return an empty dictionary.
    - Calculate the total duration of the trading period in days (from the first trade's entry time to the last trade's exit time).
    - Calculate the average number of trades per day (`len(trades) / total_days`).
    - Return a dictionary, e.g., `{"average_trades_per_day": 2.5}`.
- [ ] **3.2. Integrate into Brief:** In `src/trading_platform/reporting/brief.py`, import and call `compute_activity` within `generate_brief`. Assign the result to the `activity` key.
- [ ] **3.3. Add Tests:** In `tests/reporting/test_analytics.py`, add a test `test_compute_activity` with mock trades spanning a known duration and assert the `average_trades_per_day` is correct.

## 4. Task: Implement Timing Buckets Analysis

- [ ] **4.1. Implement `compute_timing_buckets`:** In `src/trading_platform/reporting/analytics.py`, create `compute_timing_buckets(trades: list[Trade]) -> dict`. This function must:
    - Create two dictionaries: `by_hour_of_day` and `by_day_of_week`.
    - Iterate through each trade and use its `entry_time` to bucket it into the correct hour (0-23) and day (0-6).
    - For each bucket, calculate aggregate metrics: `n_trades`, `total_pnl`, and `win_rate`.
    - Return a dictionary containing both sub-dictionaries, e.g., `{"by_hour_of_day": {...}, "by_day_of_week": {...}}`.
- [ ] **4.2. Integrate into Brief:** In `src/trading_platform/reporting/brief.py`, import and call `compute_timing_buckets` within `generate_brief`. Assign the result to the `timing_buckets` key.
- [ ] **4.3. Add Tests:** In `tests/reporting/test_analytics.py`, add `test_compute_timing_buckets`. Use mock trades with various entry times and assert that the hourly and daily buckets contain the correct aggregate statistics.

## 5. Task: Implement Long/Short Contrasts

- [ ] **5.1. Implement `compute_contrasts`:** In `src/trading_platform/reporting/analytics.py`, create `compute_contrasts(trades: list[Trade]) -> dict`. This function must:
    - Separate trades into two lists: `long_trades` and `short_trades`.
    - For each list, calculate a sub-dictionary of metrics: `n_trades`, `win_rate`, `avg_win`, `avg_loss`, `max_win`, `max_loss`.
    - Return a dictionary containing both sub-dictionaries: `{"long": {...}, "short": {...}}`.
- [ ] **5.2. Integrate into Brief:** In `src/trading_platform/reporting/brief.py`, import and call `compute_contrasts` within `generate_brief`. Assign the result to the `contrasts` key.
- [ ] **5.3. Add Tests:** In `tests/reporting/test_analytics.py`, add `test_compute_contrasts`. Use a mix of mock long and short trades and assert that the metrics in each category are correct.

## 6. Task: Implement Stop-Loss / Take-Profit Candidate Analysis

- [ ] **6.1. Implement `compute_stop_tp_candidates`:** In `src/trading_platform/reporting/analytics.py`, create `compute_stop_tp_candidates(trades: list[Trade]) -> dict`. This function must:
    - For all trades, extract `mfe_currency` (Maximum Favorable Excursion) and `mae_currency` (Maximum Adverse Excursion) into separate lists.
    - Calculate the 25th, 50th, and 75th percentiles of the `mae_currency` distribution. These are the stop-loss candidates.
    - Calculate the 25th, 50th, and 75th percentiles of the `mfe_currency` distribution. These are the take-profit candidates.
    - Return a dictionary containing these results, e.g., `{"stop_loss_by_mae_percentile": {"p25": 10.5, ...}, "take_profit_by_mfe_percentile": {"p25": 15.0, ...}}`.
- [ ] **6.2. Integrate into Brief:** In `src/trading_platform/reporting/brief.py`, import and call `compute_stop_tp_candidates` within `generate_brief`. Assign the result to the `stop_tp_candidates` key.
- [ ] **6.3. Add Tests:** In `tests/reporting/test_analytics.py`, add `test_compute_stop_tp_candidates`. Use mock trades with known MFE/MAE values and assert that the calculated percentiles are correct.
