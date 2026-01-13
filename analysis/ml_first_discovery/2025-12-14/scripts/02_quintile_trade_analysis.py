#!/usr/bin/env python3
"""
Phase 1.2: Quintile Trade Analysis

This script compares the characteristics of winning (Q4) vs losing (Q0) trades
to understand what separates them.

Output:
  - artifacts/quintile_comparison.csv
  - artifacts/quintile_stats_by_archetype.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Configuration
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 80)
    print("PHASE 1.2: QUINTILE TRADE ANALYSIS")
    print("=" * 80)

    # Load data
    trades = pd.read_parquet(
        "data/dvc/processed/training_sets/master_trade_log.parquet"
    )

    # Filter to with_risk run_ids only
    valid_run_ids = [r for r in trades["run_id"].unique() if "with_risk" in r]
    trades = trades[trades["run_id"].isin(valid_run_ids)]

    print(
        f"\nAnalyzing {len(trades):,} trades from {len(valid_run_ids)} with_risk run_ids"
    )

    # Create quintiles based on r_multiple
    trades["quintile"] = pd.qcut(
        trades["r_multiple"], q=5, labels=["Q0", "Q1", "Q2", "Q3", "Q4"]
    )

    # Basic quintile stats
    print("\n" + "=" * 80)
    print("QUINTILE DISTRIBUTION")
    print("=" * 80)

    quintile_stats = (
        trades.groupby("quintile")
        .agg({"r_multiple": ["count", "mean", "std", "min", "max"]})
        .round(4)
    )
    quintile_stats.columns = ["count", "mean_r", "std_r", "min_r", "max_r"]
    print(quintile_stats)

    # Compare Q0 (worst) vs Q4 (best) across key entry features
    print("\n" + "=" * 80)
    print("Q0 (WORST 20%) vs Q4 (BEST 20%) FEATURE COMPARISON")
    print("=" * 80)

    q0 = trades[trades["quintile"] == "Q0"]
    q4 = trades[trades["quintile"] == "Q4"]

    # Find context_at_entry features
    entry_features = [c for c in trades.columns if "context_at_entry" in c]

    # Compute comparison for numeric features
    comparison_results = []
    for feat in entry_features:
        if trades[feat].dtype in [np.float64, np.int64, np.float32, np.int32]:
            q0_mean = q0[feat].mean()
            q4_mean = q4[feat].mean()
            overall_mean = trades[feat].mean()
            overall_std = trades[feat].std()

            # Normalized difference (in standard deviations)
            if overall_std > 0:
                q0_z = (q0_mean - overall_mean) / overall_std
                q4_z = (q4_mean - overall_mean) / overall_std
                diff_z = q4_z - q0_z
            else:
                q0_z = q4_z = diff_z = 0

            comparison_results.append(
                {
                    "feature": feat.replace("context_at_entry_", ""),
                    "q0_mean": q0_mean,
                    "q4_mean": q4_mean,
                    "diff": q4_mean - q0_mean,
                    "q0_zscore": q0_z,
                    "q4_zscore": q4_z,
                    "diff_zscore": diff_z,
                    "abs_diff_zscore": abs(diff_z),
                }
            )

    comparison_df = pd.DataFrame(comparison_results)
    comparison_df = comparison_df.sort_values("abs_diff_zscore", ascending=False)
    comparison_df.to_csv(OUTPUT_DIR / "quintile_comparison.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'quintile_comparison.csv'}")

    # Show top 20 differentiating features
    print("\nTop 20 features that differentiate Q0 from Q4:")
    for i, (_, row) in enumerate(comparison_df.head(20).iterrows(), 1):
        direction = "↑" if row["diff_zscore"] > 0 else "↓"
        print(f"  {i:2d}. {direction} {row['abs_diff_zscore']:.3f}σ: {row['feature']}")
        print(f"      Q0={row['q0_mean']:.4f}, Q4={row['q4_mean']:.4f}")

    # Analysis by strategy archetype
    print("\n" + "=" * 80)
    print("QUINTILE ANALYSIS BY STRATEGY ARCHETYPE")
    print("=" * 80)

    archetype_results = []
    for archetype in trades["strategy_archetype"].unique():
        arch_trades = trades[trades["strategy_archetype"] == archetype]

        # Re-compute quintiles within archetype
        arch_trades = arch_trades.copy()
        arch_trades["arch_quintile"] = pd.qcut(
            arch_trades["r_multiple"], q=5, labels=["Q0", "Q1", "Q2", "Q3", "Q4"]
        )

        arch_q0 = arch_trades[arch_trades["arch_quintile"] == "Q0"]
        arch_q4 = arch_trades[arch_trades["arch_quintile"] == "Q4"]

        print(f"\n--- {archetype} ---")
        print(f"  Total trades: {len(arch_trades):,}")
        print(f"  Q0 avg R: {arch_q0['r_multiple'].mean():.4f}")
        print(f"  Q4 avg R: {arch_q4['r_multiple'].mean():.4f}")

        # Find top differentiating features for this archetype
        arch_comparison = []
        for feat in entry_features:
            if arch_trades[feat].dtype in [np.float64, np.int64, np.float32, np.int32]:
                q0_mean = arch_q0[feat].mean()
                q4_mean = arch_q4[feat].mean()
                overall_std = arch_trades[feat].std()

                if overall_std > 0:
                    diff_z = (q4_mean - q0_mean) / overall_std
                else:
                    diff_z = 0

                arch_comparison.append(
                    {
                        "archetype": archetype,
                        "feature": feat.replace("context_at_entry_", ""),
                        "q0_mean": q0_mean,
                        "q4_mean": q4_mean,
                        "diff_zscore": diff_z,
                        "abs_diff_zscore": abs(diff_z),
                    }
                )

        arch_df = pd.DataFrame(arch_comparison)
        arch_df = arch_df.sort_values("abs_diff_zscore", ascending=False)
        archetype_results.append(arch_df)

        # Show top 10 for this archetype
        print("\n  Top 10 differentiating features:")
        for i, (_, row) in enumerate(arch_df.head(10).iterrows(), 1):
            direction = "↑" if row["diff_zscore"] > 0 else "↓"
            print(
                f"    {i:2d}. {direction} {row['abs_diff_zscore']:.3f}σ: {row['feature']}"
            )

    # Combine archetype results
    if archetype_results:
        all_arch_df = pd.concat(archetype_results, ignore_index=True)
        all_arch_df.to_csv(OUTPUT_DIR / "quintile_stats_by_archetype.csv", index=False)
        print(f"\nSaved: {OUTPUT_DIR / 'quintile_stats_by_archetype.csv'}")

    # Key insight: ATR/volatility features
    print("\n" + "=" * 80)
    print("VOLATILITY FEATURE ANALYSIS (ATR)")
    print("=" * 80)

    atr_features = comparison_df[
        comparison_df["feature"].str.contains("atr", case=False)
    ]
    if len(atr_features) > 0:
        print("\nATR-related features (sorted by differentiating power):")
        for _, row in atr_features.head(15).iterrows():
            direction = "↑" if row["diff_zscore"] > 0 else "↓"
            print(f"  {direction} {row['abs_diff_zscore']:.3f}σ: {row['feature']}")
            print(f"    Q0={row['q0_mean']:.4f}, Q4={row['q4_mean']:.4f}")

    # Compare ATR percentile by archetype
    print("\n" + "=" * 80)
    print("ATR PERCENTILE: Q0 vs Q4 BY ARCHETYPE")
    print("=" * 80)

    # Find ATR percentile columns
    atr_pct_cols = [
        c for c in trades.columns if "atr_percentile" in c and "context_at_entry" in c
    ]

    for archetype in trades["strategy_archetype"].unique():
        arch_trades = trades[trades["strategy_archetype"] == archetype]
        arch_trades = arch_trades.copy()
        arch_trades["arch_quintile"] = pd.qcut(
            arch_trades["r_multiple"], q=5, labels=["Q0", "Q1", "Q2", "Q3", "Q4"]
        )

        arch_q0 = arch_trades[arch_trades["arch_quintile"] == "Q0"]
        arch_q4 = arch_trades[arch_trades["arch_quintile"] == "Q4"]

        print(f"\n--- {archetype} ---")
        for col in atr_pct_cols[:3]:  # Show first 3 timeframes
            short_name = col.replace("context_at_entry_global_features_", "")
            q0_val = arch_q0[col].mean()
            q4_val = arch_q4[col].mean()
            print(
                f"  {short_name}: Q0={q0_val:.1f}, Q4={q4_val:.1f} (diff={q4_val-q0_val:+.1f})"
            )


if __name__ == "__main__":
    main()
