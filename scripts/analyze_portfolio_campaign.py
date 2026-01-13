#!/usr/bin/env python3
"""
Portfolio Aggregator for HF Scalper Campaign.
Reads individual run results from a Campaign and aggregates them
into a Portfolio Equity Curve.
"""

import sys
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

        try:
            df = pd.read_csv(trades_file, parse_dates=["entry_time", "exit_time"])
            df["run_id"] = run_dir.name
            all_trades.append(df)
        except Exception as e:
            print(f"Error reading {trades_file}: {e}")

    if not all_trades:
        print("No trades found across any runs.")
        return pd.DataFrame()

    # Normalization Logic
    # 1. Extract USDJPY price series for conversion
    usdjpy_df = pd.DataFrame()
    for df in all_trades:
        if "USDJPY" in df["symbol"].iloc[0]:
            usdjpy_df = df[["exit_time", "exit_price"]].copy()
            usdjpy_df = usdjpy_df.sort_values("exit_time").set_index("exit_time")
            break

    # Sort usdjpy for asof lookup
    if not usdjpy_df.empty:
        usdjpy_df = usdjpy_df[~usdjpy_df.index.duplicated(keep="first")]

    final_trades = []

    for df in all_trades:
        symbol = df["symbol"].iloc[0]

        # Ensure 'pnl' column exists
        if "pnl" not in df.columns and "realized_pnl" in df.columns:
            df["pnl"] = df["realized_pnl"]

        # Normalize JPY
        if "JPY" in symbol:
            if symbol == "USDJPY":
                # Direct conversion: JPY / (JPY/USD) = USD
                # 400 JPY / 115.00 = 3.47 USD
                df["pnl"] = df["pnl"] / df["exit_price"]
                if "cost_currency" in df.columns:
                    df["cost_currency"] = df["cost_currency"] / df["exit_price"]
            else:
                # Cross rate: JPY / USDJPY = USD
                # We need to lookup USDJPY rate at exit_time
                if not usdjpy_df.empty:
                    # Use merge_asof to find nearest USDJPY price
                    temp_df = df.copy()
                    temp_df = temp_df.sort_values("exit_time")

                    merged = pd.merge_asof(
                        temp_df,
                        usdjpy_df["exit_price"].rename("usdjpy_rate"),
                        left_on="exit_time",
                        right_index=True,
                        direction="nearest",
                        tolerance=pd.Timedelta("1h"),
                    )

                    # Fill missing rates with average (fallback)
                    avg_rate = (
                        usdjpy_df["exit_price"].mean() if not usdjpy_df.empty else 130.0
                    )
                    merged["usdjpy_rate"] = merged["usdjpy_rate"].fillna(avg_rate)

                    df = merged.copy()
                    df["pnl"] = df["pnl"] / df["usdjpy_rate"]
                    if "cost_currency" in df.columns:
                        df["cost_currency"] = df["cost_currency"] / df["usdjpy_rate"]
                else:
                    # Fallback if no USDJPY data found
                    print(
                        f"Warning: No USDJPY data for {symbol}. Using fixed 130.0 rate."
                    )
                    df["pnl"] = df["pnl"] / 130.0

        final_trades.append(df)

    return pd.concat(final_trades, ignore_index=True)


def analyze_portfolio(trades_df: pd.DataFrame):
    if trades_df.empty:
        return

    # Use 'exit_time' for PnL realization
    trades_df = trades_df.sort_values("exit_time")
    trades_df.set_index("exit_time", inplace=True)

    # Metric: Realized PnL (Cash)
    if "pnl" not in trades_df.columns:
        print("Error: 'pnl' column missing in trades.csv")
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
