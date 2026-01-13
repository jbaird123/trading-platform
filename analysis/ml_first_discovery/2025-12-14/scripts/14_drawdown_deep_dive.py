#!/usr/bin/env python3
"""
Phase 7: Drawdown Deep Dive - The "Why so long?" Analysis

Investigates why a high-frequency (2000+ trades), high-win-rate (60%)
Mean Reversion strategy suffers from >200 day drawdowns.

Hypothesis:
The strategy profits in Low Volatility but bleeds/stagnates in High Volatility.
"""

from pathlib import Path

import pandas as pd

# Configuration
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Target Run ID (The one showing 282 days DD)
TARGET_RUN_ID = "mean_reversion_model_generation_bb_with_risk_15min_0000_EURUSD"
TRAINING_END = "2021-12-31"


def main():
    print(f"analyzing run: {TARGET_RUN_ID}")

    # Load trades
    trades = pd.read_parquet(
        "data/dvc/processed/training_sets/master_trade_log.parquet"
    )
    trades["entry_time"] = pd.to_datetime(trades["entry_time"])

    # Filter for target run and OOS period
    run_trades = trades[
        (trades["run_id"] == TARGET_RUN_ID) & (trades["entry_time"] > TRAINING_END)
    ].copy()

    run_trades = run_trades.sort_values("entry_time")

    if len(run_trades) == 0:
        print("No trades found for run_id!")
        return

    # Calculate Equity Curve
    run_trades["equity"] = run_trades["r_multiple"].cumsum()
    run_trades["peak"] = run_trades["equity"].cummax()
    run_trades["drawdown"] = run_trades["equity"] - run_trades["peak"]

    # Identify the Longest Drawdown Period
    run_trades["in_dd"] = run_trades["drawdown"] < 0
    run_trades["dd_id"] = (run_trades["in_dd"] != run_trades["in_dd"].shift()).cumsum()

    dd_periods = (
        run_trades[run_trades["in_dd"]]
        .groupby("dd_id")
        .agg(
            start_time=("entry_time", "min"),
            end_time=("entry_time", "max"),
            duration_days=("entry_time", lambda x: (x.max() - x.min()).days),
            depth=("drawdown", "min"),
            avg_atr_pct=(
                "context_at_entry_global_features_15min_atr_percentile_100",
                "mean",
            ),
        )
        .sort_values("duration_days", ascending=False)
    )

    print("\nTop 5 Longest Drawdowns:")
    print(dd_periods.head(5).to_string())

    longest_dd = dd_periods.iloc[0]

    print("\nAnatomy of the Longest Drawdown:")
    print(f"Start: {longest_dd['start_time']}")
    print(f"End: {longest_dd['end_time']}")
    print(f"Duration: {longest_dd['duration_days']} days")
    print(f"Avg Volatility (ATR Pct): {longest_dd['avg_atr_pct']:.1f}%")

    # Compare with Winning Periods
    winning_periods = run_trades[~run_trades["in_dd"]]
    if len(winning_periods) > 0:
        avg_win_vol = winning_periods[
            "context_at_entry_global_features_15min_atr_percentile_100"
        ].mean()
        print(f"Avg Volatility during New Highs: {avg_win_vol:.1f}%")

    # Analyze Win Rate inside the Drawdown
    in_longest_dd = run_trades[
        (run_trades["entry_time"] >= longest_dd["start_time"])
        & (run_trades["entry_time"] <= longest_dd["end_time"])
    ]

    dd_wr = (in_longest_dd["r_multiple"] > 0).mean()
    dd_avg_r = in_longest_dd["r_multiple"].mean()

    print(f"\nInside the Longest Drawdown ({len(in_longest_dd)} trades):")
    print(f"Win Rate: {dd_wr:.1%} (Normal: 60%)")
    print(f"Avg R: {dd_avg_r:.4f} (Normal: 0.05)")

    # Payoff Ratio Analysis
    avg_win = in_longest_dd[in_longest_dd["r_multiple"] > 0]["r_multiple"].mean()
    avg_loss = in_longest_dd[in_longest_dd["r_multiple"] <= 0]["r_multiple"].mean()
    print(f"Avg Win: {avg_win:.2f} R")
    print(f"Avg Loss: {avg_loss:.2f} R")

    # Save results
    output_rows = [
        {"metric": "Longest DD Duration", "value": longest_dd["duration_days"]},
        {"metric": "DD Win Rate", "value": dd_wr},
        {"metric": "DD Avg R", "value": dd_avg_r},
        {"metric": "DD Avg Volatility", "value": longest_dd["avg_atr_pct"]},
    ]
    output_df = pd.DataFrame(output_rows)
    output_df.to_csv(OUTPUT_DIR / "drawdown_deep_dive.csv", index=False)
    print(f"\nSaved analysis to {OUTPUT_DIR}/drawdown_deep_dive.csv")


if __name__ == "__main__":
    main()
