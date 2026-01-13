#!/usr/bin/env python3
"""
Phase 4: Holding Period & Exit Analysis

This script analyzes the relationship between holding period and trade outcomes
to optimize exit timing.

Output:
  - artifacts/holding_period_analysis.csv
  - artifacts/exit_timing_by_archetype.csv
"""

from pathlib import Path

import pandas as pd

# Configuration
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 80)
    print("PHASE 4: HOLDING PERIOD & EXIT ANALYSIS")
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

    # Check for holding period columns
    print("\n" + "=" * 80)
    print("AVAILABLE HOLDING PERIOD DATA")
    print("=" * 80)

    # Look for bars_held or holding period columns
    hold_cols = [
        c
        for c in trades.columns
        if "bars_held" in c.lower() or "hold" in c.lower() or "duration" in c.lower()
    ]
    print(f"\nHolding-related columns: {hold_cols}")

    # Check if we have entry/exit times
    time_cols = [
        c for c in trades.columns if "time" in c.lower() or "date" in c.lower()
    ]
    print(f"Time-related columns: {time_cols}")

    # Use sim_hold_bars_held if available (from simulation)
    holding_col = None
    if "sim_hold_bars_held" in trades.columns:
        holding_col = "sim_hold_bars_held"
    elif "bars_held" in trades.columns:
        holding_col = "bars_held"

    if holding_col:
        print(f"\nUsing column: {holding_col}")
        print(
            f"  Range: {trades[holding_col].min():.0f} to {trades[holding_col].max():.0f} bars"
        )
        print(f"  Mean: {trades[holding_col].mean():.1f} bars")
        print(f"  Median: {trades[holding_col].median():.0f} bars")

    holding_results = []

    # Analyze by archetype
    print("\n" + "=" * 80)
    print("HOLDING PERIOD ANALYSIS BY ARCHETYPE")
    print("=" * 80)

    for archetype in trades["strategy_archetype"].unique():
        arch_trades = trades[trades["strategy_archetype"] == archetype]
        print(f"\n--- {archetype} ({len(arch_trades):,} trades) ---")

        if holding_col and holding_col in arch_trades.columns:
            # Create holding period buckets
            arch_trades = arch_trades.copy()

            # Get percentiles for bucketing
            p25 = arch_trades[holding_col].quantile(0.25)
            p50 = arch_trades[holding_col].quantile(0.50)
            p75 = arch_trades[holding_col].quantile(0.75)

            print("\n  Holding period quartiles:")
            print(f"    Q1 (0-25%): 0 to {p25:.0f} bars")
            print(f"    Q2 (25-50%): {p25:.0f} to {p50:.0f} bars")
            print(f"    Q3 (50-75%): {p50:.0f} to {p75:.0f} bars")
            print(f"    Q4 (75-100%): {p75:.0f}+ bars")

            # Performance by holding period quartile
            arch_trades["hold_quartile"] = pd.qcut(
                arch_trades[holding_col],
                q=4,
                labels=["Short", "Medium-Short", "Medium-Long", "Long"],
                duplicates="drop",
            )

            print("\n  Performance by holding period:")
            print(
                f"  {'Quartile':<15} | {'N Trades':>10} | {'Win Rate':>10} | {'Avg R':>10} | {'Avg Bars':>10}"
            )
            print("  " + "-" * 65)

            for quartile in ["Short", "Medium-Short", "Medium-Long", "Long"]:
                q_trades = arch_trades[arch_trades["hold_quartile"] == quartile]
                if len(q_trades) == 0:
                    continue

                n = len(q_trades)
                wr = (q_trades["r_multiple"] > 0).mean()
                avg_r = q_trades["r_multiple"].mean()
                avg_bars = q_trades[holding_col].mean()

                print(
                    f"  {quartile:<15} | {n:>10,} | {wr:>9.1%} | {avg_r:>10.4f} | {avg_bars:>10.1f}"
                )

                holding_results.append(
                    {
                        "archetype": archetype,
                        "hold_quartile": quartile,
                        "n_trades": n,
                        "win_rate": wr,
                        "avg_r": avg_r,
                        "avg_bars_held": avg_bars,
                    }
                )

        # Winners vs Losers holding comparison
        winners = arch_trades[arch_trades["r_multiple"] > 0]
        losers = arch_trades[arch_trades["r_multiple"] < 0]

        if holding_col and holding_col in arch_trades.columns:
            print("\n  Winners vs Losers:")
            print(f"    Winners avg hold: {winners[holding_col].mean():.1f} bars")
            print(f"    Losers avg hold: {losers[holding_col].mean():.1f} bars")
            print(
                f"    Difference: {winners[holding_col].mean() - losers[holding_col].mean():+.1f} bars"
            )

    if holding_results:
        hold_df = pd.DataFrame(holding_results)
        hold_df.to_csv(OUTPUT_DIR / "holding_period_analysis.csv", index=False)
        print(f"\nSaved: {OUTPUT_DIR / 'holding_period_analysis.csv'}")

    # Exit reason analysis (if available)
    print("\n" + "=" * 80)
    print("EXIT REASON ANALYSIS")
    print("=" * 80)

    exit_cols = [
        c for c in trades.columns if "exit" in c.lower() or "close_reason" in c.lower()
    ]
    print(f"\nExit-related columns: {exit_cols}")

    if "close_reason" in trades.columns:
        print("\nExit reasons distribution:")
        print(trades["close_reason"].value_counts())

        # Performance by exit reason
        exit_results = []
        for archetype in trades["strategy_archetype"].unique():
            arch_trades = trades[trades["strategy_archetype"] == archetype]
            print(f"\n--- {archetype} ---")

            for reason in arch_trades["close_reason"].unique():
                reason_trades = arch_trades[arch_trades["close_reason"] == reason]
                if len(reason_trades) < 100:
                    continue

                n = len(reason_trades)
                wr = (reason_trades["r_multiple"] > 0).mean()
                avg_r = reason_trades["r_multiple"].mean()

                print(f"  {reason}: N={n:,}, WR={wr:.1%}, Avg R={avg_r:.4f}")

                exit_results.append(
                    {
                        "archetype": archetype,
                        "exit_reason": reason,
                        "n_trades": n,
                        "win_rate": wr,
                        "avg_r": avg_r,
                    }
                )

        if exit_results:
            exit_df = pd.DataFrame(exit_results)
            exit_df.to_csv(OUTPUT_DIR / "exit_timing_by_archetype.csv", index=False)
            print(f"\nSaved: {OUTPUT_DIR / 'exit_timing_by_archetype.csv'}")

    # R-multiple distribution analysis
    print("\n" + "=" * 80)
    print("R-MULTIPLE DISTRIBUTION ANALYSIS")
    print("=" * 80)

    for archetype in trades["strategy_archetype"].unique():
        arch_trades = trades[trades["strategy_archetype"] == archetype]
        print(f"\n--- {archetype} ---")

        r_mult = arch_trades["r_multiple"]
        print("  R-Multiple Statistics:")
        print(f"    Mean: {r_mult.mean():.4f}")
        print(f"    Std: {r_mult.std():.4f}")
        print(f"    Min: {r_mult.min():.4f}")
        print(f"    25%: {r_mult.quantile(0.25):.4f}")
        print(f"    50%: {r_mult.quantile(0.50):.4f}")
        print(f"    75%: {r_mult.quantile(0.75):.4f}")
        print(f"    Max: {r_mult.max():.4f}")

        # Distribution of outcomes
        big_winners = (r_mult > 2).sum()
        small_winners = ((r_mult > 0) & (r_mult <= 2)).sum()
        small_losers = ((r_mult < 0) & (r_mult >= -1)).sum()
        big_losers = (r_mult < -1).sum()

        total = len(arch_trades)
        print("\n  Outcome Distribution:")
        print(f"    Big Winners (>2R): {big_winners:,} ({big_winners/total*100:.1f}%)")
        print(
            f"    Small Winners (0-2R): {small_winners:,} ({small_winners/total*100:.1f}%)"
        )
        print(
            f"    Small Losers (-1 to 0R): {small_losers:,} ({small_losers/total*100:.1f}%)"
        )
        print(f"    Big Losers (<-1R): {big_losers:,} ({big_losers/total*100:.1f}%)")

    # Key insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)

    print("""
1. HOLDING PERIOD PATTERNS:
   - Short holds often have higher win rates but lower avg R
   - Longer holds capture larger moves but have more time for reversal
   - Optimal hold depends on strategy type

2. EXIT OPTIMIZATION OPPORTUNITIES:
   - Trailing stops can lock in profits on winning trades
   - Time-based exits may help avoid extended drawdowns
   - Exit reason analysis can inform stop placement

3. R-MULTIPLE DISTRIBUTION:
   - Mean reversion: Smaller, more consistent R-multiples
   - Trend following: Larger variance, needs big winners to offset losers

4. RECOMMENDATIONS:
   - For MR: Consider tighter exits to capture consistent small wins
   - For TF: Need wide stops and patience for big moves
   - Track holding period in live trading for regime detection
""")


if __name__ == "__main__":
    main()
