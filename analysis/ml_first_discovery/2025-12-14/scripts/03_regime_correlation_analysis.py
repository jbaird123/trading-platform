#!/usr/bin/env python3
"""
Phase 1.3: Regime Correlation Analysis

This script analyzes how strategy performance varies by volatility regime
(ATR percentile) and trading session.

Output:
  - artifacts/regime_performance_by_atr.csv
  - artifacts/regime_performance_by_session.csv
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
    print("PHASE 1.3: REGIME CORRELATION ANALYSIS")
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

    # Find ATR percentile columns
    atr_pct_cols = [
        c for c in trades.columns if "atr_percentile" in c and "context_at_entry" in c
    ]
    print(f"\nFound ATR percentile columns: {len(atr_pct_cols)}")

    # Use 15min ATR percentile as primary (most available across timeframes)
    primary_atr_col = "context_at_entry_global_features_15min_atr_percentile_100"
    if primary_atr_col not in trades.columns:
        # Fall back to 1h
        primary_atr_col = "context_at_entry_global_features_1h_atr_percentile_100"

    print(f"Using primary ATR column: {primary_atr_col}")

    # Create volatility regime buckets
    trades["vol_regime"] = pd.cut(
        trades[primary_atr_col],
        bins=[0, 25, 50, 75, 100],
        labels=["Very Low (0-25)", "Low (25-50)", "High (50-75)", "Very High (75-100)"],
    )

    # Binary volatility regime
    trades["vol_regime_binary"] = trades[primary_atr_col].apply(
        lambda x: "Low Vol (ATR<50)" if x < 50 else "High Vol (ATR≥50)"
    )

    # Analysis by volatility regime and archetype
    print("\n" + "=" * 80)
    print("PERFORMANCE BY VOLATILITY REGIME")
    print("=" * 80)

    regime_results = []

    for archetype in trades["strategy_archetype"].unique():
        arch_trades = trades[trades["strategy_archetype"] == archetype]

        print(f"\n--- {archetype} ---")

        for regime in [
            "Very Low (0-25)",
            "Low (25-50)",
            "High (50-75)",
            "Very High (75-100)",
        ]:
            regime_trades = arch_trades[arch_trades["vol_regime"] == regime]
            if len(regime_trades) == 0:
                continue

            n = len(regime_trades)
            win_rate = (regime_trades["r_multiple"] > 0).mean()
            avg_r = regime_trades["r_multiple"].mean()
            total_r = regime_trades["r_multiple"].sum()

            print(f"  {regime}: N={n:,}, WR={win_rate:.1%}, Avg R={avg_r:.3f}")

            regime_results.append(
                {
                    "archetype": archetype,
                    "regime": regime,
                    "n_trades": n,
                    "win_rate": win_rate,
                    "avg_r": avg_r,
                    "total_r": total_r,
                }
            )

    regime_df = pd.DataFrame(regime_results)
    regime_df.to_csv(OUTPUT_DIR / "regime_performance_by_atr.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'regime_performance_by_atr.csv'}")

    # Binary regime summary
    print("\n" + "=" * 80)
    print("BINARY VOLATILITY REGIME SUMMARY")
    print("=" * 80)

    for archetype in trades["strategy_archetype"].unique():
        arch_trades = trades[trades["strategy_archetype"] == archetype]

        print(f"\n--- {archetype} ---")

        for regime in ["Low Vol (ATR<50)", "High Vol (ATR≥50)"]:
            regime_trades = arch_trades[arch_trades["vol_regime_binary"] == regime]
            if len(regime_trades) == 0:
                continue

            n = len(regime_trades)
            win_rate = (regime_trades["r_multiple"] > 0).mean()
            avg_r = regime_trades["r_multiple"].mean()

            print(f"  {regime}: N={n:,}, WR={win_rate:.1%}, Avg R={avg_r:.3f}")

    # Session analysis (if session columns exist)
    print("\n" + "=" * 80)
    print("PERFORMANCE BY TRADING SESSION")
    print("=" * 80)

    session_cols = [
        c for c in trades.columns if "forex_session" in c and "context_at_entry" in c
    ]
    print(f"Found session columns: {session_cols}")

    session_results = []

    if session_cols:
        # Determine session from one-hot columns
        def get_session(row):
            for col in session_cols:
                if row[col] == 1:
                    return col.split("_")[-1]  # e.g., "london", "newyork"
            return "other"

        # Check if these are one-hot or float
        sample_vals = trades[session_cols[0]].unique()[:10]
        print(f"Sample session values: {sample_vals}")

        # If float, use thresholds
        if trades[session_cols[0]].dtype in [np.float64, np.float32]:
            # Create session labels based on which session is active
            for archetype in trades["strategy_archetype"].unique():
                arch_trades = trades[trades["strategy_archetype"] == archetype]

                print(f"\n--- {archetype} ---")

                for col in session_cols:
                    session_name = col.replace("context_at_entry_global_features_", "")

                    # Filter to when this session is active (value > 0.5)
                    active = arch_trades[arch_trades[col] > 0.5]
                    if len(active) < 100:
                        continue

                    n = len(active)
                    win_rate = (active["r_multiple"] > 0).mean()
                    avg_r = active["r_multiple"].mean()

                    print(
                        f"  {session_name}: N={n:,}, WR={win_rate:.1%}, Avg R={avg_r:.3f}"
                    )

                    session_results.append(
                        {
                            "archetype": archetype,
                            "session": session_name,
                            "n_trades": n,
                            "win_rate": win_rate,
                            "avg_r": avg_r,
                        }
                    )

    if session_results:
        session_df = pd.DataFrame(session_results)
        session_df.to_csv(OUTPUT_DIR / "regime_performance_by_session.csv", index=False)
        print(f"\nSaved: {OUTPUT_DIR / 'regime_performance_by_session.csv'}")

    # Key findings
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)

    # Find best regime for each archetype
    if len(regime_df) > 0:
        for archetype in regime_df["archetype"].unique():
            arch_data = regime_df[regime_df["archetype"] == archetype]
            best = arch_data.loc[arch_data["avg_r"].idxmax()]
            print(f"\n{archetype}:")
            print(f"  Best regime: {best['regime']}")
            print(f"  Win rate: {best['win_rate']:.1%}")
            print(f"  Avg R: {best['avg_r']:.3f}")

    # Volatility routing analysis
    print("\n" + "=" * 80)
    print("VOLATILITY-BASED ROUTING ANALYSIS")
    print("=" * 80)

    # What if we routed MR to low vol, TF to high vol?
    mr_low_vol = trades[
        (trades["strategy_archetype"] == "mean_reversion")
        & (trades["vol_regime_binary"] == "Low Vol (ATR<50)")
    ]
    tf_high_vol = trades[
        (trades["strategy_archetype"] == "trend_following")
        & (trades["vol_regime_binary"] == "High Vol (ATR≥50)")
    ]

    combined = pd.concat([mr_low_vol, tf_high_vol])

    print("\nVol-Routed Strategy (MR low vol + TF high vol):")
    print(f"  Total trades: {len(combined):,}")
    print(f"  Coverage: {len(combined) / len(trades) * 100:.1f}%")
    print(f"  Win rate: {(combined['r_multiple'] > 0).mean():.1%}")
    print(f"  Avg R: {combined['r_multiple'].mean():.4f}")
    print(f"  Total R: {combined['r_multiple'].sum():.1f}")

    # Compare to baseline
    print("\nBaseline (all trades):")
    print(f"  Total trades: {len(trades):,}")
    print(f"  Win rate: {(trades['r_multiple'] > 0).mean():.1%}")
    print(f"  Avg R: {trades['r_multiple'].mean():.4f}")
    print(f"  Total R: {trades['r_multiple'].sum():.1f}")

    # Lift
    baseline_avg_r = trades["r_multiple"].mean()
    routed_avg_r = combined["r_multiple"].mean()
    lift = routed_avg_r - baseline_avg_r
    lift_pct = lift / baseline_avg_r * 100 if baseline_avg_r != 0 else 0

    print(f"\nLift from vol routing: {lift:+.4f} R ({lift_pct:+.1f}%)")


if __name__ == "__main__":
    main()
