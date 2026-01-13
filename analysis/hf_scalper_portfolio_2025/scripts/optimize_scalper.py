#!/usr/bin/env python3
"""
HF Scalper Optimization (Grid Search)

Goal: Find parameters that minimize Max Drawdown Duration below 14 days.
Parameters: BB Deviation, RSI Threshold, Stop Loss.
"""

import itertools
from pathlib import Path

import pandas as pd

# Configuration
RAW_DATA_PATH = Path(
    "data/dvc/raw/full/eurusd/eurusd_interval_minute_1_20130101_20250823.csv"
)
OUTPUT_DIR = Path("workspace/experiments/hf_scalper")
COST_PER_TRADE = 0.5  # pips
PIP = 0.0001


def load_data():
    print("Loading data...")
    df = pd.read_csv(RAW_DATA_PATH, parse_dates=["timestamp"], index_col="timestamp")
    df = df.sort_index()
    # "War Period" Stress Test
    df = df[(df.index >= "2022-01-01") & (df.index <= "2022-10-31")].copy()
    return df


def calculate_params(df, rsi_period=2, bb_period=20, bb_std=2.5):
    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # BB
    df["bb_std_val"] = df["close"].rolling(window=bb_period).std()
    df["bb_mid"] = df["close"].rolling(window=bb_period).mean()
    # We calculate bands dynamically in loop to support variable STD if needed,
    # but for grid search, fixed STD per run is fine.
    # Note: Optimization trick - pre-calculate columns for each STD?
    # For now, we'll just run full calc in loop or re-calc per process.
    return df


def run_strategy(args):
    df, params = args
    bb_std, rsi_thresh, stop_loss_pips = params

    # Calculate Bands for this specific STD
    lower = df["bb_mid"] - (bb_std * df["bb_std_val"])
    mid = df["bb_mid"]

    closes = df["close"].values
    times = df.index
    rsi = df["rsi"].values
    bb_lower = lower.values
    bb_mid = mid.values

    trades = []
    position = None

    for i in range(len(df)):
        if i < 20:
            continue

        close = closes[i]

        if position:
            # TP: Mid Band
            if close > bb_mid[i]:
                pnl = (close - position["entry_price"]) / PIP - COST_PER_TRADE
                trades.append(
                    {
                        "pnl": pnl,
                        "entry_time": position["entry_time"],
                        "exit_time": times[i],
                    }
                )
                position = None
            # SL: Fixed
            elif close < position["stop_loss"]:
                pnl = (
                    position["stop_loss"] - position["entry_price"]
                ) / PIP - COST_PER_TRADE
                trades.append(
                    {
                        "pnl": pnl,
                        "entry_time": position["entry_time"],
                        "exit_time": times[i],
                    }
                )
                position = None

        elif not position:
            # Entry: Close < Lower AND RSI < Thresh
            if (close < bb_lower[i]) and (rsi[i] < rsi_thresh):
                position = {
                    "entry_price": close,
                    "entry_time": times[i],
                    "stop_loss": close - (stop_loss_pips * PIP),
                }

    # Calculate Metrics
    if not trades:
        return params, 0, 0, 999

    res_df = pd.DataFrame(trades)
    res_df["equity"] = res_df["pnl"].cumsum()
    res_df["peak"] = res_df["equity"].cummax()
    res_df["dd"] = res_df["equity"] - res_df["peak"]
    res_df["in_dd"] = res_df["dd"] < 0

    max_dd_days = 0
    if res_df["in_dd"].any():
        res_df["dd_id"] = (res_df["in_dd"] != res_df["in_dd"].shift()).cumsum()
        groups = res_df[res_df["in_dd"]].groupby("dd_id")
        max_dd_days = (
            groups["exit_time"].max() - groups["entry_time"].min()
        ).dt.days.max()

    total_pips = res_df["pnl"].sum()
    n_trades = len(res_df)

    return params, n_trades, total_pips, max_dd_days


def main():
    df = load_data()
    # Pre-calc base indicators
    df = calculate_params(df)

    # Parameter Grid
    bb_stds = [2.0, 2.5, 3.0]
    rsi_threshs = [5, 10, 15]
    stop_losses = [10, 15, 20, 25]

    combinations = list(itertools.product(bb_stds, rsi_threshs, stop_losses))
    print(f"Testing {len(combinations)} combinations...")

    # Run Grid Search (Sequential for simplicity, multiprocessing if needed)
    results = []
    for combo in combinations:
        res = run_strategy((df, combo))
        results.append(res)
        print(f"Params: {combo} -> Pips: {res[2]:.1f}, Max DD Days: {res[3]}")

    # Sort by Max DD Days (Ascending), then Total Pips (Descending)
    results.sort(key=lambda x: (x[3], -x[2]))

    print("\n" + "=" * 60)
    print("TOP 5 CONFIGURATIONS (Lowest Drawdown Duration)")
    print("=" * 60)
    print(
        f"{'BB':<5} {'RSI':<5} {'SL':<5} | {'Trades':<8} "
        f"{'Pips':<10} {'Max DD Days':<12}"
    )
    for i in range(min(5, len(results))):
        p, n, pips, dd = results[i]
        print(f"{p[0]:<5} {p[1]:<5} {p[2]:<5} | {n:<8} {pips:<10.1f} {dd:<12}")

    # Save
    pd.DataFrame(
        [
            {
                "bb": r[0][0],
                "rsi": r[0][1],
                "sl": r[0][2],
                "trades": r[1],
                "pips": r[2],
                "max_dd_days": r[3],
            }
            for r in results
        ]
    ).to_csv(OUTPUT_DIR / "optimization_results.csv", index=False)
    print(f"\nSaved to {OUTPUT_DIR}/optimization_results.csv")


if __name__ == "__main__":
    main()
