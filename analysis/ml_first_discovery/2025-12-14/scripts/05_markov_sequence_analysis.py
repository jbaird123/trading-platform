#!/usr/bin/env python3
"""
Phase 1.5: Markov Sequence Analysis (Trade Dependencies)

CRITICAL: This script analyzes each run_id SEPARATELY to get accurate
streak and Markov statistics. Aggregating across run_ids produces
invalid results (see Section 3B of methodology).

Output:
  - artifacts/markov_analysis_by_run.csv
  - artifacts/markov_summary_by_campaign.csv
  - artifacts/streak_analysis.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Configuration
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def calc_max_streak(arr, value):
    """Calculate maximum consecutive streak of a value."""
    max_len = 0
    current = 0
    for v in arr:
        if v == value:
            current += 1
            max_len = max(max_len, current)
        else:
            current = 0
    return max_len


def markov_analysis(sequence):
    """Analyze Markov transition probabilities for trade outcomes."""
    transitions = {"WW": 0, "WL": 0, "LW": 0, "LL": 0}

    for i in range(len(sequence) - 1):
        curr = "W" if sequence.iloc[i] else "L"
        next_ = "W" if sequence.iloc[i + 1] else "L"
        transitions[curr + next_] += 1

    total_w = transitions["WW"] + transitions["WL"]
    total_l = transitions["LW"] + transitions["LL"]

    p_win_given_win = transitions["WW"] / total_w if total_w > 0 else 0
    p_win_given_loss = transitions["LW"] / total_l if total_l > 0 else 0
    p_loss_given_loss = transitions["LL"] / total_l if total_l > 0 else 0

    return {
        "ww": transitions["WW"],
        "wl": transitions["WL"],
        "lw": transitions["LW"],
        "ll": transitions["LL"],
        "P(W|W)": p_win_given_win,
        "P(W|L)": p_win_given_loss,
        "P(L|L)": p_loss_given_loss,
        "momentum_effect": p_win_given_win - p_win_given_loss,
    }


def main():
    print("=" * 80)
    print("PHASE 1.5: MARKOV SEQUENCE ANALYSIS")
    print("=" * 80)
    print("\nCRITICAL: Analyzing each run_id SEPARATELY (not aggregated)")

    # Load data
    trades = pd.read_parquet(
        "data/dvc/processed/training_sets/master_trade_log.parquet"
    )

    # Filter to with_risk run_ids only
    all_run_ids = trades["run_id"].unique()
    valid_run_ids = [r for r in all_run_ids if "with_risk" in r]
    no_risk_run_ids = [r for r in all_run_ids if "no_risk" in r]

    print(f"\nTotal run_ids: {len(all_run_ids)}")
    print(f"  with_risk: {len(valid_run_ids)} (will analyze)")
    print(f"  no_risk: {len(no_risk_run_ids)} (excluded - no r_multiple)")

    # Analyze each run_id separately
    results = []

    for run_id in valid_run_ids:
        run_trades = (
            trades[trades["run_id"] == run_id]
            .sort_values("entry_time")
            .reset_index(drop=True)
        )
        is_win = run_trades["r_multiple"] > 0

        if len(run_trades) < 10:
            continue

        markov = markov_analysis(is_win)
        max_loss_streak = calc_max_streak(is_win.values, False)
        max_win_streak = calc_max_streak(is_win.values, True)

        # Expected max streak if independent: ~log(n) / log(1/p)
        n = len(run_trades)
        win_rate = is_win.mean()
        p_loss = 1 - win_rate
        expected_max_loss = np.log(n) / np.log(1 / p_loss) if 0 < p_loss < 1 else 0
        expected_max_win = np.log(n) / np.log(1 / win_rate) if 0 < win_rate < 1 else 0

        # Extract timeframe from run_id
        timeframe = "unknown"
        for tf in ["5min", "15min", "1H", "4H", "1D"]:
            if tf.lower() in run_id.lower():
                timeframe = tf
                break

        results.append(
            {
                "run_id": run_id,
                "campaign_id": run_trades["campaign_id"].iloc[0],
                "strategy_archetype": run_trades["strategy_archetype"].iloc[0],
                "timeframe": timeframe,
                "n_trades": n,
                "win_rate": win_rate,
                "max_loss_streak": max_loss_streak,
                "max_win_streak": max_win_streak,
                "expected_max_loss_streak": expected_max_loss,
                "expected_max_win_streak": expected_max_win,
                "loss_streak_ratio": max_loss_streak / expected_max_loss
                if expected_max_loss > 0
                else 0,
                "win_streak_ratio": max_win_streak / expected_max_win
                if expected_max_win > 0
                else 0,
                **markov,
            }
        )

    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_DIR / "markov_analysis_by_run.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'markov_analysis_by_run.csv'}")

    # Summary statistics
    print("\n" + "=" * 80)
    print(f"SUMMARY ACROSS {len(df)} RUN_IDs")
    print("=" * 80)

    print("\nOverall Statistics:")
    print(f"  Total trades analyzed: {df['n_trades'].sum():,}")
    print(f"  Avg win rate: {df['win_rate'].mean():.1%}")
    print(f"  Avg max loss streak: {df['max_loss_streak'].mean():.1f}")
    print(f"  Max max loss streak: {df['max_loss_streak'].max():.0f}")
    print(
        f"  Avg expected max loss streak: {df['expected_max_loss_streak'].mean():.1f}"
    )
    print(f"  Avg streak ratio: {df['loss_streak_ratio'].mean():.2f}x")

    print("\nMarkov Transition Probabilities:")
    print(f"  Avg P(W|W): {df['P(W|W)'].mean():.1%}")
    print(f"  Avg P(W|L): {df['P(W|L)'].mean():.1%}")
    print(f"  Avg P(L|L): {df['P(L|L)'].mean():.1%}")
    print(f"  Avg momentum effect: {df['momentum_effect'].mean():+.1%}")

    # Check if streaks are longer than expected
    longer_than_expected = (df["loss_streak_ratio"] > 1.5).sum()
    print(
        f"\n  Run_ids with loss streaks >1.5x expected: {longer_than_expected}/{len(df)}"
    )

    # Summary by strategy archetype
    print("\n" + "=" * 80)
    print("SUMMARY BY STRATEGY ARCHETYPE")
    print("=" * 80)

    for archetype in df["strategy_archetype"].unique():
        arch_df = df[df["strategy_archetype"] == archetype]
        print(f"\n--- {archetype} ({len(arch_df)} run_ids) ---")
        print(f"  Total trades: {arch_df['n_trades'].sum():,}")
        print(f"  Avg win rate: {arch_df['win_rate'].mean():.1%}")
        print(f"  Avg max loss streak: {arch_df['max_loss_streak'].mean():.1f}")
        print(f"  Max max loss streak: {arch_df['max_loss_streak'].max():.0f}")
        print(f"  Avg P(W|W): {arch_df['P(W|W)'].mean():.1%}")
        print(f"  Avg P(W|L): {arch_df['P(W|L)'].mean():.1%}")
        print(f"  Avg momentum: {arch_df['momentum_effect'].mean():+.1%}")

    # Summary by timeframe
    print("\n" + "=" * 80)
    print("SUMMARY BY TIMEFRAME")
    print("=" * 80)

    for tf in df["timeframe"].unique():
        tf_df = df[df["timeframe"] == tf]
        print(f"\n--- {tf} ({len(tf_df)} run_ids) ---")
        print(f"  Avg win rate: {tf_df['win_rate'].mean():.1%}")
        print(f"  Avg max loss streak: {tf_df['max_loss_streak'].mean():.1f}")
        print(f"  Max max loss streak: {tf_df['max_loss_streak'].max():.0f}")
        print(f"  Avg momentum: {tf_df['momentum_effect'].mean():+.1%}")

    # Campaign-level summary
    campaign_summary = (
        df.groupby("campaign_id")
        .agg(
            {
                "n_trades": "sum",
                "win_rate": "mean",
                "max_loss_streak": "max",
                "max_win_streak": "max",
                "P(W|W)": "mean",
                "P(W|L)": "mean",
                "momentum_effect": "mean",
            }
        )
        .round(4)
    )
    campaign_summary.to_csv(OUTPUT_DIR / "markov_summary_by_campaign.csv")
    print(f"\nSaved: {OUTPUT_DIR / 'markov_summary_by_campaign.csv'}")

    # Streak analysis summary
    print("\n" + "=" * 80)
    print("STREAK ANALYSIS DETAILS")
    print("=" * 80)

    # Find run_ids with longest loss streaks
    worst_streaks = df.nlargest(10, "max_loss_streak")
    print("\nTop 10 run_ids by max loss streak:")
    for _, row in worst_streaks.iterrows():
        print(f"  {row['max_loss_streak']:.0f} trades: {row['run_id'][:60]}...")
        print(
            f"    N={row['n_trades']:,}, WR={row['win_rate']:.1%}, Expected={row['expected_max_loss_streak']:.0f}, Ratio={row['loss_streak_ratio']:.2f}x"
        )

    # Save detailed streak analysis
    streak_df = df[
        [
            "run_id",
            "strategy_archetype",
            "timeframe",
            "n_trades",
            "win_rate",
            "max_loss_streak",
            "expected_max_loss_streak",
            "loss_streak_ratio",
            "max_win_streak",
            "expected_max_win_streak",
            "win_streak_ratio",
        ]
    ].copy()
    streak_df = streak_df.sort_values("max_loss_streak", ascending=False)
    streak_df.to_csv(OUTPUT_DIR / "streak_analysis.csv", index=False)
    print(f"\nSaved: {OUTPUT_DIR / 'streak_analysis.csv'}")

    # Key insight summary
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)

    avg_momentum = df["momentum_effect"].mean()
    if avg_momentum > 0.05:
        print(f"\n⚠️  POSITIVE MOMENTUM DETECTED (avg {avg_momentum:+.1%})")
        print("   P(W|W) > P(W|L): Wins tend to follow wins, losses follow losses")
        print("   Implication: Consider pausing after consecutive losses")
    elif avg_momentum < -0.05:
        print(f"\n✓ MEAN REVERSION DETECTED (avg {avg_momentum:+.1%})")
        print("   P(W|L) > P(W|W): Wins more likely after losses")
        print("   Implication: Stay consistent after losses")
    else:
        print(f"\n✓ TRADES ARE ROUGHLY INDEPENDENT (avg momentum {avg_momentum:+.1%})")
        print("   P(W|W) ≈ P(W|L): Past outcomes don't strongly predict future")

    avg_streak_ratio = df["loss_streak_ratio"].mean()
    if avg_streak_ratio > 2.0:
        print(f"\n⚠️  LOSS STREAKS ARE LONGER THAN EXPECTED ({avg_streak_ratio:.2f}x)")
        print("   Actual streaks significantly exceed random walk expectations")
        print("   Implication: Budget for longer drawdowns than naive models suggest")
    elif avg_streak_ratio < 0.75:
        print(f"\n✓ LOSS STREAKS ARE SHORTER THAN EXPECTED ({avg_streak_ratio:.2f}x)")
        print("   Good news: System shows mean-reverting behavior")
    else:
        print(f"\n✓ LOSS STREAKS ARE NEAR EXPECTED ({avg_streak_ratio:.2f}x)")


if __name__ == "__main__":
    main()
