#!/usr/bin/env python3
"""
Phase 8: Low Volatility Filter Simulation

Investigates the impact of ignoring trades when ATR Percentile > 50.
"""

from pathlib import Path

import pandas as pd

# Configuration
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "artifacts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Target Run ID
TARGET_RUN_ID = "mean_reversion_model_generation_bb_with_risk_15min_0000_EURUSD"
TRAINING_END = "2021-12-31"


def calculate_dd_metrics(df):
    if len(df) == 0:
        return 0, 0

    df = df.copy()
    df["equity"] = df["r_multiple"].cumsum()
    df["peak"] = df["equity"].cummax()
    df["drawdown"] = df["equity"] - df["peak"]
    df["in_dd"] = df["drawdown"] < 0

    # DD Duration
    if not df["in_dd"].any():
        return 0, 0

    df["dd_id"] = (df["in_dd"] != df["in_dd"].shift()).cumsum()
    dd_groups = df[df["in_dd"]].groupby("dd_id")

    max_days = 0
    for _, group in dd_groups:
        days = (group["entry_time"].max() - group["entry_time"].min()).days
        if days > max_days:
            max_days = days

    return df["drawdown"].min(), max_days


def main():
    print(f"Analyzing Low Vol Filter for: {TARGET_RUN_ID}")

    # Load trades
    trades = pd.read_parquet(
        "data/dvc/processed/training_sets/master_trade_log.parquet"
    )
    trades["entry_time"] = pd.to_datetime(trades["entry_time"])

    # Filter OOS
    df_all = (
        trades[
            (trades["run_id"] == TARGET_RUN_ID) & (trades["entry_time"] > TRAINING_END)
        ]
        .sort_values("entry_time")
        .copy()
    )

    # ATR Column
    atr_col = "context_at_entry_global_features_15min_atr_percentile_100"

    # Filter Low Vol (< 50)
    df_low = df_all[df_all[atr_col] < 50].copy()

    # Metrics
    orig_dd_depth, orig_dd_days = calculate_dd_metrics(df_all)
    filt_dd_depth, filt_dd_days = calculate_dd_metrics(df_low)

    print("\n" + "=" * 60)
    print("SIMULATION RESULTS: IGNORING TRADES WITH ATR > 50")
    print("=" * 60)

    print(
        f"{'Metric':<20} | {'Original (All)':<15} | "
        f"{'Filtered (Low Vol Only)':<20} | {'Impact':<10}"
    )
    print("-" * 75)

    print(
        f"{'Trades':<20} | {len(df_all):<15,} | {len(df_low):<20,} | "
        f"-{100*(1-len(df_low)/len(df_all)):.1f}%"
    )

    win_all = (df_all["r_multiple"] > 0).mean()
    win_low = (df_low["r_multiple"] > 0).mean()
    print(
        f"{'Win Rate':<20} | {win_all:<15.1%} | {win_low:<20.1%} | "
        f"{win_low-win_all:+.1%}"
    )

    avg_all = df_all["r_multiple"].mean()
    avg_low = df_low["r_multiple"].mean()
    print(
        f"{'Avg R':<20} | {avg_all:<15.4f} | {avg_low:<20.4f} | "
        f"{avg_low-avg_all:+.4f}"
    )

    tot_all = df_all["r_multiple"].sum()
    tot_low = df_low["r_multiple"].sum()
    print(
        f"{'Total Profit (R)':<20} | {tot_all:<15.1f} | {tot_low:<20.1f} | "
        f"{tot_low-tot_all:+.1f} R"
    )

    print(
        f"{'Max DD Duration':<20} | {orig_dd_days:<15} | "
        f"{filt_dd_days:<20} | {filt_dd_days-orig_dd_days:+} days"
    )

    # Specific check on the "War Period" (Jan 2022 - Oct 2022)
    war_start = pd.Timestamp("2022-01-01", tz="UTC")
    war_end = pd.Timestamp("2022-10-31", tz="UTC")

    df_war = df_all[
        (df_all["entry_time"] >= war_start) & (df_all["entry_time"] <= war_end)
    ]
    df_war_low = df_low[
        (df_low["entry_time"] >= war_start) & (df_low["entry_time"] <= war_end)
    ]

    war_profit_all = df_war["r_multiple"].sum()
    war_profit_low = df_war_low["r_multiple"].sum()

    print("\n" + "=" * 60)
    print("IMPACT DURING 'THE WAR CHURN' (Jan-Oct 2022)")
    print("=" * 60)
    print(f"Original Profit: {war_profit_all:.1f} R")
    print(f"Filtered Profit: {war_profit_low:.1f} R")
    print(f"Difference:      {war_profit_low - war_profit_all:+.1f} R")

    # Save
    results = pd.DataFrame(
        [
            {"metric": "total_profit", "original": tot_all, "filtered": tot_low},
            {
                "metric": "max_dd_days",
                "original": orig_dd_days,
                "filtered": filt_dd_days,
            },
            {"metric": "win_rate", "original": win_all, "filtered": win_low},
        ]
    )
    results.to_csv(OUTPUT_DIR / "low_vol_simulation.csv", index=False)
    print(f"\nSaved results to {OUTPUT_DIR}/low_vol_simulation.csv")


if __name__ == "__main__":
    main()
