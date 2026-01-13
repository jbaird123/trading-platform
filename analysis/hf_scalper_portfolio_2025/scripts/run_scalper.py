#!/usr/bin/env python3
"""
High-Frequency Scalper Prototype (The "2-Week" Solution)

Strategy:
- Timeframe: 1 Minute
- Logic: Mean Reversion (Rubber Band)
- Entry: Close < Lower BB(20, 2.5) AND RSI(2) < 10
- Exit: Close > Middle BB (Revert to Mean) OR Stop Loss

Focus: Minimizing Drawdown Duration.
"""

from pathlib import Path

import pandas as pd

# Configuration
RAW_DATA_PATH = Path(
    "data/dvc/raw/full/eurusd/eurusd_interval_minute_1_20130101_20250823.csv"
)
OUTPUT_DIR = Path("workspace/experiments/hf_scalper")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Strategy Parameters
RSI_PERIOD = 2
RSI_OVERSOLD = 5  # Optimized from 10
BB_PERIOD = 20
BB_STD = 3.0  # Optimized from 2.5
STOP_LOSS_PIPS = 10  # Optimized from 20
COST_PER_TRADE = 0.5  # pips (spread + comms)


def load_data(path, start_date="2022-01-01", end_date="2022-10-31"):
    print(f"Loading data from {path}...")
    # Load only necessary columns for speed
    df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
    df = df.sort_index()

    # Filter for the "War Period" by default
    df = df[(df.index >= start_date) & (df.index <= end_date)].copy()
    print(f"Loaded {len(df):,} bars ({start_date} to {end_date})")
    return df


def calculate_indicators(df):
    print("Calculating indicators...")

    # RSI(2)
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # Bollinger Bands (20, 2.5)
    df["bb_mid"] = df["close"].rolling(window=BB_PERIOD).mean()
    df["bb_std"] = df["close"].rolling(window=BB_PERIOD).std()
    df["bb_lower"] = df["bb_mid"] - (BB_STD * df["bb_std"])
    df["bb_upper"] = df["bb_mid"] + (BB_STD * df["bb_std"])

    return df.dropna()


def run_backtest(df):
    print("Running backtest loop...")

    trades = []
    position = None  # None or dict with 'entry_price', 'entry_time', 'stop_loss'

    # Vectorized signal generation (faster than loop) would be ideal,
    # but loop is safer for precise state management (stops/exits).
    # Given 1m bars, we'll iterate.

    closes = df["close"].values
    times = df.index
    rsi = df["rsi"].values
    bb_lower = df["bb_lower"].values
    bb_mid = df["bb_mid"].values

    # Pip value conv (approx for EURUSD)
    PIP = 0.0001

    for i in range(len(df)):
        if i < 1:
            continue

        current_close = closes[i]
        current_time = times[i]

        # Check Exit
        if position:
            # 1. Take Profit (Mean Reversion)
            # Exit if price touches/crosses Middle Band
            if current_close > bb_mid[i]:
                pnl = (current_close - position["entry_price"]) / PIP - COST_PER_TRADE
                trades.append(
                    {
                        "entry_time": position["entry_time"],
                        "exit_time": current_time,
                        "pnl_pips": pnl,
                        "duration_bars": i - position["idx"],
                        "exit_reason": "TP_Mean",
                    }
                )
                position = None

            # 2. Stop Loss
            elif current_close < position["stop_loss"]:
                pnl = (
                    position["stop_loss"] - position["entry_price"]
                ) / PIP - COST_PER_TRADE  # Slippage assumed at stop
                trades.append(
                    {
                        "entry_time": position["entry_time"],
                        "exit_time": current_time,
                        "pnl_pips": pnl,
                        "duration_bars": i - position["idx"],
                        "exit_reason": "SL_Hard",
                    }
                )
                position = None

        # Check Entry (Long Only for now)
        elif not position:
            # Logic: Close < LoBB AND RSI < Oversold
            if (current_close < bb_lower[i]) and (rsi[i] < RSI_OVERSOLD):
                # Valid setup. Enter at CLOSE of this bar (approx)
                position = {
                    "entry_price": current_close,
                    "entry_time": current_time,
                    "stop_loss": current_close - (STOP_LOSS_PIPS * PIP),
                    "idx": i,
                }

    return pd.DataFrame(trades)


def analyze_performance(trades):
    if len(trades) == 0:
        print("No trades generated.")
        return

    print("\n" + "=" * 40)
    print("PERFORMANCE REPORT: HF SCALPER")
    print("=" * 40)

    # Basic Stats
    n_trades = len(trades)
    win_rate = (trades["pnl_pips"] > 0).mean()
    total_pips = trades["pnl_pips"].sum()
    avg_trade = trades["pnl_pips"].mean()

    print(f"Trades: {n_trades:,} ({n_trades/10:.1f} per month approx)")
    print(f"Win Rate: {win_rate:.1%}")
    print(f"Total Pips: {total_pips:.1f}")
    print(f"Avg Pips/Trade: {avg_trade:.2f}")

    # Drawdown Duration Analysis
    trades["equity"] = trades["pnl_pips"].cumsum()
    trades["peak"] = trades["equity"].cummax()
    trades["drawdown"] = trades["equity"] - trades["peak"]
    trades["in_dd"] = trades["drawdown"] < 0

    # Calculate duration of each DD period
    if trades["in_dd"].any():
        trades["dd_id"] = (trades["in_dd"] != trades["in_dd"].shift()).cumsum()
        dd_stats = (
            trades[trades["in_dd"]]
            .groupby("dd_id")
            .agg(start_time=("entry_time", "min"), end_time=("exit_time", "max"))
        )
        dd_stats["duration"] = (dd_stats["end_time"] - dd_stats["start_time"]).dt.days

        max_dd_days = dd_stats["duration"].max()
        avg_dd_days = dd_stats["duration"].mean()

        print("\nDrawdown Duration Metrics:")
        print(f"  Max Duration: {max_dd_days} days")
        print(f"  Avg Duration: {avg_dd_days:.1f} days")

        # Check against target
        if max_dd_days < 14:
            print("\n✅ SUCCESS: Max Drawdown < 14 Days!")
        else:
            print("\n❌ FAILURE: Max Drawdown > 14 Days.")

    else:
        print("\n✅ PERFECT RUN: Zero Drawdown!")

    # Save
    trades.to_csv(OUTPUT_DIR / "hf_scalper_trades.csv", index=False)
    print(f"\nSaved trades to {OUTPUT_DIR}/hf_scalper_trades.csv")


def main():
    df = load_data(RAW_DATA_PATH)
    df = calculate_indicators(df)
    trades = run_backtest(df)
    analyze_performance(trades)


if __name__ == "__main__":
    main()
