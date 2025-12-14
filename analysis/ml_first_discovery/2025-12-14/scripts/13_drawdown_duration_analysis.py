#!/usr/bin/env python3
"""
Phase 6B: Drawdown Duration Analysis

This script analyzes drawdown DURATION (how long the strategy stays underwater),
which is a key metric for trader psychology and strategy viability.

The methodology doc targets ~14 days max drawdown duration.

Output:
  - artifacts/drawdown_duration_by_run.csv
  - artifacts/drawdown_duration_summary.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Configuration
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Model training cutoff
TRAINING_END = "2021-12-31"


def analyze_drawdown_duration(trades_df):
    """
    Analyze drawdown duration from a sorted DataFrame of trades.

    Returns dict with:
    - max_dd_duration_trades: Max consecutive trades in drawdown
    - max_dd_duration_days: Max calendar days in drawdown
    - avg_dd_duration_trades: Average drawdown length
    - time_in_drawdown_pct: % of time spent in drawdown
    - num_drawdown_periods: Number of separate drawdown periods
    """
    if len(trades_df) < 2:
        return {
            "max_dd_duration_trades": 0,
            "max_dd_duration_days": 0,
            "avg_dd_duration_trades": 0,
            "time_in_drawdown_pct": 0,
            "num_drawdown_periods": 0,
        }

    # Calculate cumulative R
    trades_df = trades_df.copy()
    trades_df["cum_r"] = trades_df["r_multiple"].cumsum()
    trades_df["running_max"] = trades_df["cum_r"].cummax()
    trades_df["in_drawdown"] = trades_df["cum_r"] < trades_df["running_max"]

    # Find drawdown periods
    trades_df["dd_start"] = (
        trades_df["in_drawdown"] & ~trades_df["in_drawdown"].shift(1).fillna(False)
    )
    trades_df["dd_end"] = (
        ~trades_df["in_drawdown"] & trades_df["in_drawdown"].shift(1).fillna(False)
    )

    # Assign drawdown period IDs
    trades_df["dd_period"] = trades_df["dd_start"].cumsum()
    trades_df.loc[~trades_df["in_drawdown"], "dd_period"] = 0

    # Analyze each drawdown period
    dd_durations_trades = []
    dd_durations_days = []

    for period_id in trades_df[trades_df["dd_period"] > 0]["dd_period"].unique():
        period_trades = trades_df[trades_df["dd_period"] == period_id]
        if len(period_trades) > 0:
            dd_durations_trades.append(len(period_trades))

            # Calculate days if we have entry_time
            if "entry_time" in period_trades.columns:
                start_time = period_trades["entry_time"].min()
                end_time = period_trades["entry_time"].max()
                days = (end_time - start_time).days
                dd_durations_days.append(max(days, 1))  # At least 1 day

    # Calculate metrics
    max_dd_trades = max(dd_durations_trades) if dd_durations_trades else 0
    max_dd_days = max(dd_durations_days) if dd_durations_days else 0
    avg_dd_trades = np.mean(dd_durations_trades) if dd_durations_trades else 0
    time_in_dd = trades_df["in_drawdown"].mean() * 100
    num_periods = len(dd_durations_trades)

    return {
        "max_dd_duration_trades": max_dd_trades,
        "max_dd_duration_days": max_dd_days,
        "avg_dd_duration_trades": avg_dd_trades,
        "time_in_drawdown_pct": time_in_dd,
        "num_drawdown_periods": num_periods,
    }


def main():
    print("=" * 80)
    print("PHASE 6B: DRAWDOWN DURATION ANALYSIS")
    print("=" * 80)
    print("\nMethodology target: ~14 days max drawdown duration")

    # Load trade data
    trades = pd.read_parquet(
        "data/dvc/processed/training_sets/master_trade_log.parquet"
    )
    trades["entry_time"] = pd.to_datetime(trades["entry_time"])

    # Filter to with_risk run_ids only
    valid_run_ids = [r for r in trades["run_id"].unique() if "with_risk" in r]
    trades = trades[trades["run_id"].isin(valid_run_ids)]

    # Split into train/test
    train_trades = trades[trades["entry_time"] <= TRAINING_END]
    test_trades = trades[trades["entry_time"] > TRAINING_END]

    print(f"\nTotal trades: {len(trades):,}")
    print(f"  Training period (2018-2021): {len(train_trades):,}")
    print(f"  Out-of-sample (2022-2023): {len(test_trades):,}")

    # Analyze by run_id
    print("\n" + "=" * 80)
    print("DRAWDOWN DURATION BY RUN_ID (Out-of-Sample Only)")
    print("=" * 80)

    run_results = []

    for run_id in valid_run_ids:
        # Use out-of-sample trades only
        run_trades = test_trades[test_trades["run_id"] == run_id].sort_values(
            "entry_time"
        )
        if len(run_trades) < 20:
            continue

        archetype = (
            "mean_reversion" if "mean_reversion" in run_id else "trend_following"
        )

        # Basic metrics
        n_trades = len(run_trades)
        win_rate = (run_trades["r_multiple"] > 0).mean()
        avg_r = run_trades["r_multiple"].mean()
        total_r = run_trades["r_multiple"].sum()

        # Drawdown duration metrics
        dd_metrics = analyze_drawdown_duration(run_trades)

        run_results.append(
            {
                "run_id": run_id,
                "archetype": archetype,
                "n_trades": n_trades,
                "win_rate": win_rate,
                "avg_r": avg_r,
                "total_r": total_r,
                **dd_metrics,
            }
        )

    run_df = pd.DataFrame(run_results)
    run_df.to_csv(OUTPUT_DIR / "drawdown_duration_by_run.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'drawdown_duration_by_run.csv'}")

    # Summary by archetype
    print("\n" + "=" * 80)
    print("DRAWDOWN DURATION SUMMARY BY ARCHETYPE (Out-of-Sample)")
    print("=" * 80)

    summary_results = []

    for archetype in run_df["archetype"].unique():
        arch_data = run_df[run_df["archetype"] == archetype]

        print(f"\n--- {archetype} ({len(arch_data)} runs) ---")

        # Duration in trades
        print("\n  Duration in TRADES:")
        print(f"    Max DD duration: {arch_data['max_dd_duration_trades'].max():.0f}")
        print(f"    Avg max DD duration: {arch_data['max_dd_duration_trades'].mean():.1f}")
        print(f"    Min max DD duration: {arch_data['max_dd_duration_trades'].min():.0f}")

        # Duration in days
        print("\n  Duration in DAYS:")
        print(f"    Max DD duration: {arch_data['max_dd_duration_days'].max():.0f}")
        print(f"    Avg max DD duration: {arch_data['max_dd_duration_days'].mean():.1f}")
        print(f"    Min max DD duration: {arch_data['max_dd_duration_days'].min():.0f}")

        # Time in drawdown
        print("\n  Time in Drawdown:")
        print(f"    Avg % time in DD: {arch_data['time_in_drawdown_pct'].mean():.1f}%")
        print(f"    Max % time in DD: {arch_data['time_in_drawdown_pct'].max():.1f}%")

        # Compare to 14-day target
        runs_under_14_days = (arch_data["max_dd_duration_days"] <= 14).sum()
        runs_under_30_days = (arch_data["max_dd_duration_days"] <= 30).sum()
        total_runs = len(arch_data)

        print(f"\n  vs 14-day target:")
        print(f"    Runs with max DD <= 14 days: {runs_under_14_days}/{total_runs} ({runs_under_14_days/total_runs*100:.1f}%)")
        print(f"    Runs with max DD <= 30 days: {runs_under_30_days}/{total_runs} ({runs_under_30_days/total_runs*100:.1f}%)")

        summary_results.append(
            {
                "archetype": archetype,
                "n_runs": len(arch_data),
                "max_dd_duration_days_worst": arch_data["max_dd_duration_days"].max(),
                "max_dd_duration_days_avg": arch_data["max_dd_duration_days"].mean(),
                "max_dd_duration_trades_worst": arch_data["max_dd_duration_trades"].max(),
                "max_dd_duration_trades_avg": arch_data["max_dd_duration_trades"].mean(),
                "avg_time_in_drawdown_pct": arch_data["time_in_drawdown_pct"].mean(),
                "pct_runs_under_14_days": runs_under_14_days / total_runs * 100,
                "pct_runs_under_30_days": runs_under_30_days / total_runs * 100,
            }
        )

    summary_df = pd.DataFrame(summary_results)
    summary_df.to_csv(OUTPUT_DIR / "drawdown_duration_summary.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'drawdown_duration_summary.csv'}")

    # Aggregate analysis (all trades combined per archetype)
    print("\n" + "=" * 80)
    print("AGGREGATE DRAWDOWN DURATION (All OOS Trades Combined)")
    print("=" * 80)

    for archetype in test_trades["strategy_archetype"].unique():
        arch_trades = test_trades[test_trades["strategy_archetype"] == archetype]
        arch_trades = arch_trades.sort_values("entry_time")

        dd_metrics = analyze_drawdown_duration(arch_trades)

        print(f"\n--- {archetype} ({len(arch_trades):,} trades) ---")
        print(f"  Max DD duration: {dd_metrics['max_dd_duration_days']} days")
        print(f"  Max DD duration: {dd_metrics['max_dd_duration_trades']} trades")
        print(f"  Avg DD duration: {dd_metrics['avg_dd_duration_trades']:.1f} trades")
        print(f"  Time in drawdown: {dd_metrics['time_in_drawdown_pct']:.1f}%")
        print(f"  Number of DD periods: {dd_metrics['num_drawdown_periods']}")

    # Key insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)

    print("""
1. DRAWDOWN DURATION vs TARGET (14 days):
   - Check how many runs meet the 14-day target
   - If most runs exceed this, strategy may not be suitable for day trading

2. TIME IN DRAWDOWN:
   - High % means equity curve is underwater most of the time
   - Target: < 40-50% time in drawdown

3. TRADES vs DAYS:
   - More trades = faster recovery potential
   - But also more opportunities to extend drawdown

4. RECOMMENDATIONS:
   - If max DD duration > 30 days consistently, consider:
     a) Tighter stop losses
     b) Regime-based position sizing
     c) Pausing after N consecutive losses
     d) Accepting this is a longer-term strategy
""")


if __name__ == "__main__":
    main()
