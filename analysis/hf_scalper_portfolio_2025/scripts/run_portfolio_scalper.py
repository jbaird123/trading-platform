#!/usr/bin/env python3
"""
Multi-Pair Portfolio Scalper (The "Diversified" Solution)

Strategy:
- Run Optimized HF-MR on 4 un-correlated pairs.
- Sum the PnL to create a Portfolio Equity Curve.
- Measure if Diversification reduces Max Drawdown Duration < 14 Days.

Pairs:
1. EURUSD (Base)
2. AUDUSD (Commodity)
3. GBPJPY (Vol/Cross)
4. USDJPY (Rates)
"""

from multiprocessing import Pool
from pathlib import Path

import pandas as pd

# Configuration
DATA_DIR = Path("data/dvc/raw/full")
OUTPUT_DIR = Path("workspace/experiments/hf_scalper")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Optimized MR Parameters
RSI_PERIOD = 2
RSI_OVERSOLD = 5
BB_PERIOD = 20
BB_STD = 3.0
STOP_LOSS_PIPS = 10
COST_PER_TRADE = 0.5  # pips

PAIRS = {
    "eurusd": {
        "file": "eurusd/eurusd_interval_minute_1_20130101_20250823.csv",
        "pip": 0.0001,
    },
    "audusd": {
        "file": "audusd/audusd_interval_minute_1_20130101_20250823.csv",
        "pip": 0.0001,
    },
    "gbpjpy": {
        "file": "gbpjpy/gbpjpy_interval_minute_1_20130101_20250823.csv",
        "pip": 0.01,
    },
    "usdjpy": {
        "file": "usdjpy/usdjpy_interval_minute_1_20130101_20250823.csv",
        "pip": 0.01,
    },
}


def process_pair(pair_name):
    config = PAIRS[pair_name]
    path = DATA_DIR / config["file"]
    pip_val = config["pip"]

    print(f"[{pair_name}] Loading data...")
    df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
    df = df.sort_index()

    # Filter War Period
    df = df[(df.index >= "2022-01-01") & (df.index <= "2022-10-31")].copy()

    # Indicators
    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # BB
    df["bb_mid"] = df["close"].rolling(window=BB_PERIOD).mean()
    df["bb_std"] = df["close"].rolling(window=BB_PERIOD).std()
    df["bb_lower"] = df["bb_mid"] - (BB_STD * df["bb_std"])

    df = df.dropna()

    # Backtest Loop
    trades = []
    position = None

    closes = df["close"].values
    times = df.index
    rsi = df["rsi"].values
    bb_lower = df["bb_lower"].values
    bb_mid = df["bb_mid"].values

    for i in range(len(df)):
        current_close = closes[i]
        current_time = times[i]

        if position:
            # TP
            if current_close > bb_mid[i]:
                pnl_pips = (
                    current_close - position["entry_price"]
                ) / pip_val - COST_PER_TRADE
                trades.append(
                    {"exit_time": current_time, "pnl": pnl_pips, "pair": pair_name}
                )
                position = None
            # SL
            elif current_close < position["stop_loss"]:
                pnl_pips = (
                    position["stop_loss"] - position["entry_price"]
                ) / pip_val - COST_PER_TRADE
                trades.append(
                    {"exit_time": current_time, "pnl": pnl_pips, "pair": pair_name}
                )
                position = None

        elif not position:
            if (current_close < bb_lower[i]) and (rsi[i] < RSI_OVERSOLD):
                position = {
                    "entry_price": current_close,
                    "stop_loss": current_close - (STOP_LOSS_PIPS * pip_val),
                }

    print(f"[{pair_name}] Generated {len(trades)} trades")
    return trades


def main():
    # Run pairs in parallel
    print("Starting Portfolio Backtest (2022 War Period)...")
    with Pool(len(PAIRS)) as p:
        results = p.map(process_pair, list(PAIRS.keys()))

    all_trades = []
    for res in results:
        all_trades.extend(res)

    if not all_trades:
        print("No trades generated across portfolio.")
        return

    # Create Trades DataFrame
    trades_df = pd.DataFrame(all_trades)
    trades_df = trades_df.sort_values("exit_time")

    # Aggregate PnL (Daily Resampling for Drawdown Calc)
    # We use hourly resolution for finer drawdown detail
    trades_df.set_index("exit_time", inplace=True)

    # Portfolio Statistics
    total_trades = len(trades_df)
    total_pnl = trades_df["pnl"].sum()
    win_rate = (trades_df["pnl"] > 0).mean()

    print("\n" + "=" * 40)
    print("PORTFOLIO PERFORMANCE REPORT")
    print("=" * 40)
    print(f"Pairs: {', '.join(PAIRS.keys())}")
    print(f"Total Trades: {total_trades:,} ({total_trades/10:.1f}/month)")
    print(f"Win Rate: {win_rate:.1%}")
    print(f"Total Pips: {total_pnl:.1f}")

    # Construct Equity Curve (Resampled to Hourly)
    # Allows analyzing "Time in Drawdown" properly
    hourly_pnl = trades_df["pnl"].resample("1h").sum().fillna(0)
    equity = hourly_pnl.cumsum()

    peak = equity.cummax()
    drawdown = equity - peak
    in_dd = drawdown < 0

    # Drawdown Duration
    dd_id = (in_dd != in_dd.shift()).cumsum()

    # Filter usually puts "not in dd" as a group too, we need only "in_dd"
    # But since 0 duration is fine, we just want max duration of "True" blocks

    # Iterate groups to find duration
    # (Faster way using timestamps)
    dd_groups = equity.groupby(dd_id)

    print("\nCalculating Max Drawdown Duration...")
    longest_dd_days = 0

    for _, group in dd_groups:
        if (
            group.index[0] in drawdown[in_dd].index
        ):  # Check if this group is actually a drawdown
            duration = group.index[-1] - group.index[0]
            if duration.days > longest_dd_days:
                longest_dd_days = duration.days

    print(f"\nPortfolio Max Drawdown Duration: {longest_dd_days} days")

    if longest_dd_days < 14:
        print("✅ SUCCESS: Portfolio Drawdown < 14 Days!")
    else:
        print("❌ FAILURE: Portfolio Drawdown > 14 Days.")

    # Save
    trades_df.to_csv(OUTPUT_DIR / "portfolio_trades.csv")
    print(f"\nSaved portfolio trades to {OUTPUT_DIR}/portfolio_trades.csv")


if __name__ == "__main__":
    main()
