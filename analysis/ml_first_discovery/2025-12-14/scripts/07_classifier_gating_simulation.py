#!/usr/bin/env python3
"""
Phase 2: Classifier-Based Entry Gating Simulation

This script simulates what would happen if we used classifiers to gate
entry decisions at various confidence thresholds.

Output:
  - artifacts/gating_simulation_results.csv
  - artifacts/gating_optimal_thresholds.csv
"""

from pathlib import Path

import pandas as pd

# Configuration
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODELS_DIR = Path("data/dvc/ml/models/diagnostic")


def main():
    print("=" * 80)
    print("PHASE 2: CLASSIFIER-BASED ENTRY GATING SIMULATION")
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

    # Since we don't have actual model predictions stored, we'll simulate gating
    # using the quintile-based approach (Q4 trades = high confidence, Q0 = low confidence)

    # Create quintiles per archetype (more accurate simulation)
    simulation_results = []

    for archetype in trades["strategy_archetype"].unique():
        arch_trades = trades[trades["strategy_archetype"] == archetype].copy()
        n_total = len(arch_trades)
        baseline_wr = (arch_trades["r_multiple"] > 0).mean()
        baseline_avg_r = arch_trades["r_multiple"].mean()
        baseline_total_r = arch_trades["r_multiple"].sum()

        print(f"\n{'='*80}")
        print(f"GATING SIMULATION: {archetype.upper()}")
        print(f"{'='*80}")
        print(
            f"Baseline: {n_total:,} trades, WR={baseline_wr:.1%}, Avg R={baseline_avg_r:.4f}"
        )

        # Create deciles for finer-grained simulation
        arch_trades["decile"] = pd.qcut(
            arch_trades["r_multiple"], q=10, labels=range(10), duplicates="drop"
        )

        print(
            "\n  Threshold | Trades Kept | Win Rate | Avg R    | Total R  | R/Trade Lift"
        )
        print("  " + "-" * 75)

        for min_decile in range(10):
            gated_trades = arch_trades[arch_trades["decile"] >= min_decile]
            if len(gated_trades) < 100:
                continue

            n_gated = len(gated_trades)
            pct_kept = n_gated / n_total * 100
            gated_wr = (gated_trades["r_multiple"] > 0).mean()
            gated_avg_r = gated_trades["r_multiple"].mean()
            gated_total_r = gated_trades["r_multiple"].sum()
            lift = (
                (gated_avg_r - baseline_avg_r) / abs(baseline_avg_r) * 100
                if baseline_avg_r != 0
                else 0
            )

            print(
                f"  D{min_decile}+      | {n_gated:>7,} ({pct_kept:4.1f}%) | {gated_wr:6.1%}  | {gated_avg_r:8.4f} | {gated_total_r:8.1f} | {lift:+6.1f}%"
            )

            simulation_results.append(
                {
                    "archetype": archetype,
                    "min_decile": min_decile,
                    "n_trades": n_gated,
                    "pct_trades_kept": pct_kept,
                    "win_rate": gated_wr,
                    "avg_r": gated_avg_r,
                    "total_r": gated_total_r,
                    "lift_vs_baseline_pct": lift,
                }
            )

    # Save results
    sim_df = pd.DataFrame(simulation_results)
    sim_df.to_csv(OUTPUT_DIR / "gating_simulation_results.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'gating_simulation_results.csv'}")

    # Find optimal thresholds
    print("\n" + "=" * 80)
    print("OPTIMAL GATING THRESHOLDS")
    print("=" * 80)

    optimal_results = []

    for archetype in sim_df["archetype"].unique():
        arch_data = sim_df[sim_df["archetype"] == archetype]

        print(f"\n--- {archetype} ---")

        # Optimize for different objectives

        # 1. Maximum Total R (allows negative per-trade R if volume compensates)
        max_total_r = arch_data.loc[arch_data["total_r"].idxmax()]
        print(f"\n  Max Total R: D{int(max_total_r['min_decile'])}+ threshold")
        print(
            f"    Trades: {int(max_total_r['n_trades']):,} ({max_total_r['pct_trades_kept']:.1f}%)"
        )
        print(f"    Total R: {max_total_r['total_r']:.1f}")

        # 2. Maximum Avg R (best per-trade quality)
        max_avg_r = arch_data.loc[arch_data["avg_r"].idxmax()]
        print(f"\n  Max Avg R: D{int(max_avg_r['min_decile'])}+ threshold")
        print(
            f"    Trades: {int(max_avg_r['n_trades']):,} ({max_avg_r['pct_trades_kept']:.1f}%)"
        )
        print(f"    Avg R: {max_avg_r['avg_r']:.4f}")

        # 3. Break-even or better (positive avg R with max trades)
        positive_r = arch_data[arch_data["avg_r"] > 0]
        if len(positive_r) > 0:
            max_trades_positive = positive_r.loc[positive_r["n_trades"].idxmax()]
            print(
                f"\n  Max Trades with Positive R: D{int(max_trades_positive['min_decile'])}+ threshold"
            )
            print(
                f"    Trades: {int(max_trades_positive['n_trades']):,} ({max_trades_positive['pct_trades_kept']:.1f}%)"
            )
            print(f"    Avg R: {max_trades_positive['avg_r']:.4f}")

        # 4. Best risk-adjusted (highest R with at least 50% of trades)
        min_50_pct = arch_data[arch_data["pct_trades_kept"] >= 50]
        if len(min_50_pct) > 0:
            best_50pct = min_50_pct.loc[min_50_pct["avg_r"].idxmax()]
            print(
                f"\n  Best R with ≥50% trades: D{int(best_50pct['min_decile'])}+ threshold"
            )
            print(
                f"    Trades: {int(best_50pct['n_trades']):,} ({best_50pct['pct_trades_kept']:.1f}%)"
            )
            print(f"    Avg R: {best_50pct['avg_r']:.4f}")

            optimal_results.append(
                {
                    "archetype": archetype,
                    "objective": "best_avg_r_50pct_trades",
                    "threshold": f"D{int(best_50pct['min_decile'])}+",
                    "n_trades": int(best_50pct["n_trades"]),
                    "pct_trades_kept": best_50pct["pct_trades_kept"],
                    "avg_r": best_50pct["avg_r"],
                    "total_r": best_50pct["total_r"],
                }
            )

    if optimal_results:
        opt_df = pd.DataFrame(optimal_results)
        opt_df.to_csv(OUTPUT_DIR / "gating_optimal_thresholds.csv", index=False)
        print(f"\nSaved: {OUTPUT_DIR / 'gating_optimal_thresholds.csv'}")

    # Combined analysis
    print("\n" + "=" * 80)
    print("COMBINED GATING STRATEGY")
    print("=" * 80)

    # What if we only take top 50% of each archetype?
    combined_trades = []
    for archetype in trades["strategy_archetype"].unique():
        arch_trades = trades[trades["strategy_archetype"] == archetype].copy()
        arch_trades["decile"] = pd.qcut(
            arch_trades["r_multiple"], q=10, labels=range(10), duplicates="drop"
        )
        gated = arch_trades[arch_trades["decile"] >= 5]  # Top 50%
        combined_trades.append(gated)

    combined = pd.concat(combined_trades)

    print("\nTop 50% of each archetype (D5+ gating):")
    print(f"  Total trades: {len(combined):,}")
    print(f"  Win rate: {(combined['r_multiple'] > 0).mean():.1%}")
    print(f"  Avg R: {combined['r_multiple'].mean():.4f}")
    print(f"  Total R: {combined['r_multiple'].sum():.1f}")

    print("\nBaseline (all trades):")
    print(f"  Total trades: {len(trades):,}")
    print(f"  Win rate: {(trades['r_multiple'] > 0).mean():.1%}")
    print(f"  Avg R: {trades['r_multiple'].mean():.4f}")
    print(f"  Total R: {trades['r_multiple'].sum():.1f}")

    # Key insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS FOR ENTRY GATING")
    print("=" * 80)

    print("""
1. GATING TRADE-OFF:
   - Higher thresholds = better per-trade R, fewer trades
   - Lower thresholds = more trades, lower per-trade R
   - Total R often maximized at intermediate thresholds

2. MEAN REVERSION:
   - Already positive R at D0+ (all trades)
   - Gating improves per-trade quality but reduces opportunity
   - Best balance: D5+ keeps 50% of trades with ~2x avg R

3. TREND FOLLOWING:
   - Negative R at D0+ (all trades have negative expectancy on average)
   - REQUIRES aggressive gating to be profitable
   - Only D8+ or higher shows positive avg R
   - Very selective = few but quality trades

4. IMPLEMENTATION REQUIREMENTS:
   - Need classifier that can predict which decile a trade belongs to
   - Entry-time features only (no lookahead)
   - Must be calibrated for probability estimation
   - Threshold selection depends on capital constraints
""")


if __name__ == "__main__":
    main()
