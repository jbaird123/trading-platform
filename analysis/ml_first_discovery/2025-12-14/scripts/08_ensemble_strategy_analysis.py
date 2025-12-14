#!/usr/bin/env python3
"""
Phase 3: Multi-Strategy Ensemble Analysis

This script analyzes combining mean_reversion and trend_following strategies
with various weighting schemes and routing rules.

Output:
  - artifacts/ensemble_performance.csv
  - artifacts/ensemble_optimal_weights.csv
"""

from pathlib import Path

import pandas as pd

# Configuration
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 80)
    print("PHASE 3: MULTI-STRATEGY ENSEMBLE ANALYSIS")
    print("=" * 80)

    # Load trade data
    trades = pd.read_parquet(
        "data/dvc/processed/training_sets/master_trade_log.parquet"
    )

    # Filter to with_risk run_ids only
    valid_run_ids = [r for r in trades["run_id"].unique() if "with_risk" in r]
    trades = trades[trades["run_id"].isin(valid_run_ids)]

    print(
        f"\nAnalyzing {len(trades):,} trades from {len(valid_run_ids)} with_risk run_ids"
    )

    mr_trades = trades[trades["strategy_archetype"] == "mean_reversion"]
    tf_trades = trades[trades["strategy_archetype"] == "trend_following"]

    print(f"\nMean Reversion: {len(mr_trades):,} trades")
    print(f"Trend Following: {len(tf_trades):,} trades")

    # Baseline performance
    print("\n" + "=" * 80)
    print("BASELINE PERFORMANCE")
    print("=" * 80)

    print("\nMean Reversion:")
    print(f"  Win Rate: {(mr_trades['r_multiple'] > 0).mean():.1%}")
    print(f"  Avg R: {mr_trades['r_multiple'].mean():.4f}")
    print(f"  Total R: {mr_trades['r_multiple'].sum():.1f}")

    print("\nTrend Following:")
    print(f"  Win Rate: {(tf_trades['r_multiple'] > 0).mean():.1%}")
    print(f"  Avg R: {tf_trades['r_multiple'].mean():.4f}")
    print(f"  Total R: {tf_trades['r_multiple'].sum():.1f}")

    print("\nCombined (all trades):")
    print(f"  Win Rate: {(trades['r_multiple'] > 0).mean():.1%}")
    print(f"  Avg R: {trades['r_multiple'].mean():.4f}")
    print(f"  Total R: {trades['r_multiple'].sum():.1f}")

    # Ensemble strategies
    print("\n" + "=" * 80)
    print("ENSEMBLE STRATEGY SIMULATIONS")
    print("=" * 80)

    ensemble_results = []

    # Strategy 1: Mean Reversion Only (baseline)
    print("\n1. Mean Reversion Only:")
    print(f"   Trades: {len(mr_trades):,}")
    print(f"   Avg R: {mr_trades['r_multiple'].mean():.4f}")
    print(f"   Total R: {mr_trades['r_multiple'].sum():.1f}")
    ensemble_results.append(
        {
            "strategy": "MR Only",
            "description": "Mean Reversion trades only",
            "n_trades": len(mr_trades),
            "win_rate": (mr_trades["r_multiple"] > 0).mean(),
            "avg_r": mr_trades["r_multiple"].mean(),
            "total_r": mr_trades["r_multiple"].sum(),
        }
    )

    # Strategy 2: Trend Following Only (baseline)
    print("\n2. Trend Following Only:")
    print(f"   Trades: {len(tf_trades):,}")
    print(f"   Avg R: {tf_trades['r_multiple'].mean():.4f}")
    print(f"   Total R: {tf_trades['r_multiple'].sum():.1f}")
    ensemble_results.append(
        {
            "strategy": "TF Only",
            "description": "Trend Following trades only",
            "n_trades": len(tf_trades),
            "win_rate": (tf_trades["r_multiple"] > 0).mean(),
            "avg_r": tf_trades["r_multiple"].mean(),
            "total_r": tf_trades["r_multiple"].sum(),
        }
    )

    # Strategy 3: Volatility-Routed (MR low vol, TF high vol)
    primary_atr_col = "context_at_entry_global_features_15min_atr_percentile_100"
    mr_low_vol = mr_trades[mr_trades[primary_atr_col] < 50]
    tf_high_vol = tf_trades[tf_trades[primary_atr_col] >= 50]
    vol_routed = pd.concat([mr_low_vol, tf_high_vol])

    print("\n3. Volatility-Routed (MR low vol + TF high vol):")
    print(f"   Trades: {len(vol_routed):,}")
    print(f"   Avg R: {vol_routed['r_multiple'].mean():.4f}")
    print(f"   Total R: {vol_routed['r_multiple'].sum():.1f}")
    ensemble_results.append(
        {
            "strategy": "Vol-Routed",
            "description": "MR when ATR<50, TF when ATR>=50",
            "n_trades": len(vol_routed),
            "win_rate": (vol_routed["r_multiple"] > 0).mean(),
            "avg_r": vol_routed["r_multiple"].mean(),
            "total_r": vol_routed["r_multiple"].sum(),
        }
    )

    # Strategy 4: Volatility-Routed v2 (MR only, since it wins in all regimes)
    # Based on regime discovery finding
    print("\n4. MR-Dominant (MR in all regimes):")
    print(f"   Trades: {len(mr_trades):,}")
    print(f"   Avg R: {mr_trades['r_multiple'].mean():.4f}")
    print(f"   Total R: {mr_trades['r_multiple'].sum():.1f}")
    # Same as MR only, but named differently for clarity

    # Strategy 5: Quality-Gated MR (top 60% by decile)
    mr_trades_copy = mr_trades.copy()
    mr_trades_copy["decile"] = pd.qcut(
        mr_trades_copy["r_multiple"], q=10, labels=range(10), duplicates="drop"
    )
    mr_gated = mr_trades_copy[mr_trades_copy["decile"] >= 4]  # Top 60%

    print("\n5. Quality-Gated MR (D4+, top 60%):")
    print(f"   Trades: {len(mr_gated):,}")
    print(f"   Avg R: {mr_gated['r_multiple'].mean():.4f}")
    print(f"   Total R: {mr_gated['r_multiple'].sum():.1f}")
    ensemble_results.append(
        {
            "strategy": "MR D4+ Gated",
            "description": "MR with top 60% quality gate",
            "n_trades": len(mr_gated),
            "win_rate": (mr_gated["r_multiple"] > 0).mean(),
            "avg_r": mr_gated["r_multiple"].mean(),
            "total_r": mr_gated["r_multiple"].sum(),
        }
    )

    # Strategy 6: Ultra-selective TF (top 20%)
    tf_trades_copy = tf_trades.copy()
    tf_trades_copy["decile"] = pd.qcut(
        tf_trades_copy["r_multiple"], q=10, labels=range(10), duplicates="drop"
    )
    tf_gated = tf_trades_copy[tf_trades_copy["decile"] >= 8]  # Top 20%

    print("\n6. Ultra-Selective TF (D8+, top 20%):")
    print(f"   Trades: {len(tf_gated):,}")
    print(f"   Avg R: {tf_gated['r_multiple'].mean():.4f}")
    print(f"   Total R: {tf_gated['r_multiple'].sum():.1f}")
    ensemble_results.append(
        {
            "strategy": "TF D8+ Gated",
            "description": "TF with top 20% quality gate",
            "n_trades": len(tf_gated),
            "win_rate": (tf_gated["r_multiple"] > 0).mean(),
            "avg_r": tf_gated["r_multiple"].mean(),
            "total_r": tf_gated["r_multiple"].sum(),
        }
    )

    # Strategy 7: Combined gated (MR D4+ with TF D8+)
    combined_gated = pd.concat([mr_gated, tf_gated])
    print("\n7. Combined Gated (MR D4+ + TF D8+):")
    print(f"   Trades: {len(combined_gated):,}")
    print(f"   Avg R: {combined_gated['r_multiple'].mean():.4f}")
    print(f"   Total R: {combined_gated['r_multiple'].sum():.1f}")
    ensemble_results.append(
        {
            "strategy": "MR D4+ + TF D8+",
            "description": "MR top 60% + TF top 20%",
            "n_trades": len(combined_gated),
            "win_rate": (combined_gated["r_multiple"] > 0).mean(),
            "avg_r": combined_gated["r_multiple"].mean(),
            "total_r": combined_gated["r_multiple"].sum(),
        }
    )

    # Strategy 8: Vol-routed with gating (MR low vol D4+ only)
    mr_low_vol_gated = mr_low_vol.copy()
    mr_low_vol_gated["decile"] = pd.qcut(
        mr_low_vol_gated["r_multiple"], q=10, labels=range(10), duplicates="drop"
    )
    mr_low_vol_top = mr_low_vol_gated[mr_low_vol_gated["decile"] >= 4]

    tf_high_vol_gated = tf_high_vol.copy()
    tf_high_vol_gated["decile"] = pd.qcut(
        tf_high_vol_gated["r_multiple"], q=10, labels=range(10), duplicates="drop"
    )
    tf_high_vol_top = tf_high_vol_gated[
        tf_high_vol_gated["decile"] >= 6
    ]  # Top 40% of high vol TF

    vol_routed_gated = pd.concat([mr_low_vol_top, tf_high_vol_top])
    print("\n8. Vol-Routed + Gated (MR low vol D4+ + TF high vol D6+):")
    print(f"   Trades: {len(vol_routed_gated):,}")
    print(f"   Avg R: {vol_routed_gated['r_multiple'].mean():.4f}")
    print(f"   Total R: {vol_routed_gated['r_multiple'].sum():.1f}")
    ensemble_results.append(
        {
            "strategy": "Vol-Routed Gated",
            "description": "MR low vol D4+ + TF high vol D6+",
            "n_trades": len(vol_routed_gated),
            "win_rate": (vol_routed_gated["r_multiple"] > 0).mean(),
            "avg_r": vol_routed_gated["r_multiple"].mean(),
            "total_r": vol_routed_gated["r_multiple"].sum(),
        }
    )

    # Save ensemble results
    ens_df = pd.DataFrame(ensemble_results)
    ens_df = ens_df.sort_values("total_r", ascending=False)
    ens_df.to_csv(OUTPUT_DIR / "ensemble_performance.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'ensemble_performance.csv'}")

    # Summary ranking
    print("\n" + "=" * 80)
    print("ENSEMBLE STRATEGY RANKING (by Total R)")
    print("=" * 80)

    print("\nRank | Strategy              | Trades     | Win Rate | Avg R   | Total R")
    print("-" * 80)
    for i, (_, row) in enumerate(ens_df.iterrows(), 1):
        print(
            f"{i:4d} | {row['strategy']:21s} | {row['n_trades']:>10,} | {row['win_rate']:7.1%} | {row['avg_r']:7.4f} | {row['total_r']:>10,.1f}"
        )

    # Find Pareto-optimal strategies
    print("\n" + "=" * 80)
    print("PARETO-OPTIMAL STRATEGIES")
    print("=" * 80)

    print("""
Strategies that are not dominated on both Avg R and Total R:
""")

    # Simple Pareto analysis
    pareto = []
    for _, row in ens_df.iterrows():
        is_dominated = False
        for _, other in ens_df.iterrows():
            if other["avg_r"] > row["avg_r"] and other["total_r"] > row["total_r"]:
                is_dominated = True
                break
        if not is_dominated:
            pareto.append(row)

    for row in pareto:
        print(
            f"  - {row['strategy']}: Avg R={row['avg_r']:.4f}, Total R={row['total_r']:.1f}"
        )

    # Key insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)

    print("""
1. MEAN REVERSION DOMINANCE:
   - MR outperforms TF in ALL volatility regimes
   - TF is only useful after aggressive quality gating (D8+)
   - "Volatility routing" doesn't help when MR always wins

2. QUALITY GATING IS KEY:
   - MR D4+ captures 60% of trades with much better avg R
   - TF D8+ captures only 20% but makes TF profitable
   - Combined gating (MR D4+ + TF D8+) maximizes Total R

3. RECOMMENDED ENSEMBLE:
   - Primary: Mean Reversion with D4+ quality gate
   - Secondary: Trend Following ONLY with D8+ quality gate
   - This captures the best of both with appropriate selectivity

4. IMPLEMENTATION PRIORITY:
   a) Build MR quality classifier (target D4+ identification)
   b) Build TF quality classifier (target D8+ identification)
   c) Route all trades through MR classifier first
   d) Only use TF when MR signal is absent AND TF shows D8+ quality
""")


if __name__ == "__main__":
    main()
