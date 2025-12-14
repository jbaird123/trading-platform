#!/usr/bin/env python3
"""
Portfolio Aggregator for HF Scalper Campaign.
Reads individual run results from a Campaign and aggregates them
into a Portfolio Equity Curve.
"""

import sys

# ... (rest of imports)
from pathlib import Path

import pandas as pd

# Directory where standalone runs are output
RUNS_DIR = Path("workspace/runs/hf_scalper_portfolio")


def load_standalone_runs():
    if not RUNS_DIR.exists():
        print(f"Error: Runs directory not found: {RUNS_DIR}")
        sys.exit(1)

    print(f"Scanning {RUNS_DIR} for runs...")
    # Recursively find all directories that contain a trades.csv file
    run_dirs = [p.parent for p in RUNS_DIR.rglob("trades.csv")]
    all_trades = []

    print(f"Found {len(run_dirs)} runs with trade data.")

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

    max_dd_duration_days = 0
    dd_start_idx = -1
    dd_end_idx = -1

    for i, group in dd_groups:
        if group.index[0] in drawdown[in_dd].index:
            duration = group.index[-1] - group.index[0]
            if duration.days > max_dd_duration_days:
                max_dd_duration_days = duration.days
                dd_start_idx = equity.index.get_loc(group.index[0])
                dd_end_idx = equity.index.get_loc(group.index[-1])

    print("\nDRAWDOWN METRICS")
    print(f"Max DD Duration: {max_dd_duration_days} Calendar Days")
    if max_dd_duration_days > 0:
        start_ts = equity.index[dd_start_idx]
        end_ts = equity.index[dd_end_idx]
        print(f"Longest DD Period: {start_ts} to {end_ts}")
        # Approx trading days (5/7)
        est_trading_days = int(max_dd_duration_days * 5 / 7)
        print(f"(~{est_trading_days} Trading Days)")
    else:
        est_trading_days = 0  # No drawdown, so 0 trading days

    print("\nBENCHMARK COMPARISON")
    print(f"Research: ~28 Trading Days | Production: ~{est_trading_days} Trading Days")
    print(
        "Result: PASS (Within variance)"
        if est_trading_days <= 35
        else "Result: CAUTION (Deviation > 20%)"
    )


if __name__ == "__main__":
    # No arguments needed for standalone version
    df = load_standalone_runs()
    analyze_portfolio(df)
