# Brief Analytics Test Failures Implementation Plan

**Objective:** This document provides a precise, test-first implementation plan for a developer to fix the test failures related to the integration of new analytics sections into the `brief.json` output. The developer must follow these tasks in the specified sequence to ensure correctness and 100% test coverage.

**Branch:** `fix/brief-analytics-schema`

---

## 1. Update Brief JSON Schema

- [x] **1.1. Update `docs/schemas/brief.schema.json`:** Add definitions for all the new analytics sections. The new properties must be added to the main `properties` object in the schema.

    - **`activity`:**
      ```json
      "activity": {
          "type": "object",
          "description": "Trading activity metrics.",
          "properties": {
              "average_trades_per_day": {
                  "type": "number",
                  "description": "Average number of trades executed per day over the backtest period."
              }
          }
      },
      ```

    - **`timing_buckets`:**
      ```json
      "timing_buckets": {
          "type": "object",
          "description": "Performance metrics bucketed by time of trade entry.",
          "properties": {
              "hour_of_day": {
                  "type": "object",
                  "description": "Performance metrics grouped by the hour of the day (UTC)."
              },
              "day_of_week": {
                  "type": "object",
                  "description": "Performance metrics grouped by the day of the week (0=Monday)."
              }
          }
      },
      ```

    - **`contrasts`:**
      ```json
      "contrasts": {
          "type": "object",
          "description": "Performance comparison between long and short trades.",
          "properties": {
              "long_trades": {
                  "type": "object",
                  "description": "Performance metrics for long trades."
              },
              "short_trades": {
                  "type": "object",
                  "description": "Performance metrics for short trades."
              }
          }
      },
      ```

    - **`stop_tp_candidates`:**
      ```json
      "stop_tp_candidates": {
          "type": "object",
          "description": "Suggested stop-loss and take-profit levels based on MFE/MAE analysis.",
          "properties": {
              "mfe_percentiles": {
                  "type": "object",
                  "description": "Percentiles of Maximum Favorable Excursion (MFE) in currency terms."
              },
              "mae_percentiles": {
                  "type": "object",
                  "description": "Percentiles of Maximum Adverse Excursion (MAE) in currency terms."
              }
          }
      },
      ```

    - **`stationarity`:**
      ```json
      "stationarity": {
          "type": "object",
          "description": "Stationarity tests on the PnL series.",
          "properties": {
              "adf_p_value": {
                  "type": "number",
                  "description": "P-value from the Augmented Dickey-Fuller test. A low p-value (< 0.05) suggests the series is stationary."
              },
              "kpss_p_value": {
                  "type": "number",
                  "description": "P-value from the KPSS test. A high p-value (> 0.05) suggests the series is stationary."
              }
          }
      },
      ```

    - **`feature_analysis`:**
      ```json
      "feature_analysis": {
          "type": "object",
          "description": "Analysis of features from trade entry contexts.",
          "properties": {
              "feature_correlation_matrix": {
                  "type": "object",
                  "description": "Pearson correlation matrix of all numerical features available at trade entry."
              }
          }
      }
      ```

## 2. Verify Fixes

- [ ] **2.1. Run Tests:** Execute `poetry run pytest` and confirm that all tests now pass. The schema updates should resolve the `ValueError` and `jsonschema.ValidationError` failures.
