# Diagnostic Rules Reference

This document lists all diagnostic rules implemented in the AI module, their purpose, the brief fields they use, and the logic for triggering each rule.

---

## InefficientExitsRule
- **Purpose:** Detects if exits are systematically inefficient, leaving significant profit on the table.
- **Fields Used:** `model_analysis.avg_pnl_left_on_table_at_tp`, `trades`
- **Trigger Logic:**
    - If `avg_pnl_left_on_table_at_tp` > threshold (e.g., 10.0), triggers with summary and evidence.
    - Also checks trades for inefficient exit patterns.

## StrategyParameterOptimizationOpportunityRule
- **Purpose:** Identifies strategy parameters that are unset or suboptimal.
- **Fields Used:** `strategy_params`
- **Trigger Logic:**
    - Triggers if any value in `strategy_params` is `None`.
    - Reports which parameters are missing.

## DataQualityImpactRule
- **Purpose:** Assesses the impact of data quality issues on strategy results.
- **Fields Used:** `has_nans`, `duplicate_bars_count`, `quality_score`
- **Trigger Logic:**
    - Triggers if `has_nans` is `True` or `duplicate_bars_count` is high.
    - Calculates and reports `quality_score`.

## SignalPersistenceRule
- **Purpose:** Detects persistent signals that may indicate poor entry/exit logic.
- **Fields Used:** `signal_quality_analysis.signal_persistence_pct`
- **Trigger Logic:**
    - Triggers if `signal_persistence_pct` exceeds a defined threshold.

## LowWinRateHighTradesRule
- **Purpose:** Flags strategies with a high number of trades but a low win rate, indicating possible overtrading or poor signal quality.
- **Fields Used:** backtest_metrics.n_trades, backtest_metrics.win_rate
- **Trigger Logic:**
    - Triggers if n_trades > threshold (default 100) and win_rate < threshold (default 0.55).

## MarketRegimeMismatchRule
- **Purpose:** Identifies poor strategy performance in specific market regimes.
- **Fields Used:** regimes.{regime}.n_trades, regimes.{regime}.win_rate
- **Trigger Logic:**
    - Triggers if any regime has n_trades >= threshold (default 20) and win_rate < threshold (default 0.45).
    - Reports mismatched regimes.

---

*Add new rules below as they are implemented, following the same format.*
