# Profitability Threshold Analysis Summary

This note captures the latest feature-combo experiments, recommended logistic
thresholds, and the resulting trade-level impact. All metrics use the enriched
master trade log (train: 2018-01-01 – 2021-12-31, test: 2022-01-01 onward).

## Recommended Thresholds

| Context | Feature Combo | Threshold | Trade Coverage | Mean R Lift | Win Rate Lift |
| --- | --- | --- | --- | --- | --- |
| 5min_trend_following | structure+momentum | 0.50 | 56% | +0.001 | +0.019 |
| 15min_trend_following | volatility | 0.60 | 2.3% | +0.216 | +0.136 |
| 1H_trend_following | volatility | 0.70 | 4.8% | +0.620 | +0.045 |
| 4H_trend_following | structure+momentum | 0.40 | 47% | +0.096 | +0.037 |
| 1D_trend_following | calendar | 0.60 | 29% | +1.251 | +0.286 |

> Source: `analysis/rmm/featureset_trial/selected_combos/threshold_recommendations.csv`

## Equity Impact

The logistic filter was replayed on the 2022–2023 holdout set and compared
against the unfiltered baseline.

| Context | Baseline Final Equity | Filtered Final Equity | Trades Kept | Total Trades | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5min_trend_following | 482.96 | 286.75 | 21,056 | 37,576 | 56.0% |
| 15min_trend_following | -240.74 | 54.89 | 280 | 12,271 | 2.3% |
| 1H_trend_following | -332.85 | 75.31 | 147 | 3,087 | 4.8% |
| 4H_trend_following | 93.33 | 79.94 | 371 | 784 | 47.3% |
| 1D_trend_following | 30.85 | 61.34 | 42 | 147 | 28.6% |

> Source: `analysis/rmm/featureset_trial/selected_combos/equity_summary.csv`

Key observations:

* **1D calendar** threshold delivers the largest lift (+1.25 mean R, +0.29 win rate)
  while still capturing ~29% of trades.
* **1H volatility** filter remains high value, flipping equity positive with a
  small set of trades (~5% coverage).
* **15min volatility** now identifies high-conviction trades (mean R +0.22) but
  only keeps ~2% of flow; ideal as a "must trade" overlay.
* **5min structure+momentum** shows improved win rate but still light lift,
  suggesting a two-tier threshold or additional micro-volatility predicates.
* **4H structure+momentum** offers moderate improvement; further higher-timeframe
  alignment features may boost separation.

### 5min Variant Exploration

- **GradientBoostingClassifier** with balanced sample weights provides the best
  separation among tested models. At `τ = 0.55` it keeps ~27% of trades with
  mean R ≈ 0.026 (+0.013 over baseline). Logistic and RF variants continue to
  underperform.
- Two-stage gating with the gradient boosting probabilities shows promise:
  combining `τ ≥ 0.55` with `prior_return > 0` yields mean R ≈ 0.068 across
  15% of trades; requiring full trend alignment (`alignment_full`) gives mean R
  ≈ 0.066 with 17% coverage.
- Recommended next step is to add the gradient boosting classifier as an
  auxiliary profitability model for 5min runs and validate the `τ = 0.55`
  momentum/alignment gate in a replay before promoting it to production.

## Follow-Up Work

1. **Portfolio Replay:** Integrate the thresholds into a higher-level replay
   (equity + drawdown + Sharpe) before altering production configs.
2. **Context-Specific Tuning:** Investigate multi-tier thresholds and richer
   features for the 5min and 4H contexts.
3. **Config Wiring:** Once validated, feed the threshold table into the
   profitability gating phase so the live pipeline can apply consistent
   probability cut-offs.
