#!/usr/bin/env python3
"""
Portfolio Aggregator for HF Scalper Campaign.
Reads individual run results from a Campaign and aggregates them
into a Portfolio Equity Curve.
"""

import argparse
import sys

# ... (rest of imports)
from pathlib import Path

import pandas as pd


def load_campaign_runs(campaign_id: str):
    campaign_dir = Path("data/campaigns") / campaign_id / "runs"
    if not campaign_dir.exists():
        print(f"Error: Campaign directory not found: {campaign_dir}")
        sys.exit(1)

    all_trades = []
    run_dirs = [d for d in campaign_dir.iterdir() if d.is_dir()]

    print(f"Found {len(run_dirs)} runs in {campaign_id}")

    for run_dir in run_dirs:
        trades_file = run_dir / "trades.csv"
        if not trades_file.exists():
            print(f"Warning: No trades.csv in {run_dir.name}, skipping.")
            continue

        # Infer pair name from run dir (usually has hash, but maybe metadata?)
        # For now, just load it.
        try:
            df = pd.read_csv(trades_file, parse_dates=["entry_time", "exit_time"])
            df["run_id"] = run_dir.name
            all_trades.append(df)
        except Exception as e:
            print(f"Error reading {trades_file}: {e}")

    if not all_trades:
        print("No trades found across any runs.")
        return pd.DataFrame()

    return pd.concat(all_trades, ignore_index=True)


def analyze_portfolio(trades_df: pd.DataFrame):
    if trades_df.empty:
        return

    # Use 'exit_time' for PnL realization
    trades_df = trades_df.sort_values("exit_time")
    trades_df.set_index("exit_time", inplace=True)

    # Metric: Realized PnL (Cash)
    # Ensure column exists
    if "pnl" not in trades_df.columns and "realized_pnl" in trades_df.columns:
        trades_df["pnl"] = trades_df["realized_pnl"]

    if "pnl" not in trades_df.columns:
        print("Error: 'pnl' or 'realized_pnl' column missing in trades.csv")
        return

    # 1. win Rate
    win_rate = (trades_df["pnl"] > 0).mean()
    total_pnl = trades_df["pnl"].sum()
    n_trades = len(trades_df)

    print("\n" + "=" * 50)
    print("PORTFOLIO AGGREGATION REPORT")
    print("=" * 50)
    print(f"Total Trades: {n_trades:,}")
    print(f"Win Rate:     {win_rate:.1%}")
    print(f"Total PnL:    {total_pnl:,.2f}")

    # 2. Equity Curve (Hourly)
    hourly_pnl = trades_df["pnl"].resample("1h").sum().fillna(0)
    equity = hourly_pnl.cumsum()

    # 3. Drawdown Duration
    peak = equity.cummax()
    drawdown = equity - peak
    in_dd = drawdown < 0

    dd_id = (in_dd != in_dd.shift()).cumsum()
    dd_groups = equity.groupby(dd_id)

    max_duration_days = 0
    max_dd_start = None
    max_dd_end = None

    for _, group in dd_groups:
        if group.index[0] in drawdown[in_dd].index:
            duration = group.index[-1] - group.index[0]
            if duration.days > max_duration_days:
                max_duration_days = duration.days
                max_dd_start = group.index[0]
                max_dd_end = group.index[-1]

    print("\nDRAWDOWN METRICS")
    print(f"Max DD Duration: {max_duration_days} days")
    if max_dd_start:
        print(f"Longest DD Period: {max_dd_start} to {max_dd_end}")

    if max_duration_days < 14:
        print("\n✅ PASSED: Duration < 14 Days")
    else:
        print("\n❌ FAILED: Duration > 14 Days")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "campaign_id", help="Campaign ID (folder name in data/campaigns)"
    )
    args = parser.parse_args()

    df = load_campaign_runs(args.campaign_id)
    analyze_portfolio(df)
