#!/usr/bin/env python3
"""
Trend Following Scalper Prototype (The "Hedge")

Strategy:
- Timeframe: 1 Minute
- Logic: Donchian Breakout
- Entry: Close > 20-bar High AND ADX(14) > 25 AND Close > EMA(200)
- Exit: Trailing Stop (Low of last 5 bars) OR Hard Stop (20 pips)

Focus: Profiting during High Volatility / Trending periods (Jan-Oct 2022).
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Configuration
RAW_DATA_PATH = Path(
    "data/dvc/raw/full/eurusd/eurusd_interval_minute_1_20130101_20250823.csv"
)
OUTPUT_DIR = Path("workspace/experiments/hf_scalper")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Strategy Parameters
BREAKOUT_PERIOD = 20
ADX_PERIOD = 14
ADX_THRESH = 25
EMA_PERIOD = 200
TRAILING_STOP_BARS = 5
HARD_STOP_PIPS = 20
COST_PER_TRADE = 0.5  # pips (spread + comms)
PIP = 0.0001


def load_data(path, start_date="2022-01-01", end_date="2022-10-31"):
    print(f"Loading data from {path}...")
    df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
    df = df.sort_index()

    # Filter for the "War Period"
    df = df[(df.index >= start_date) & (df.index <= end_date)].copy()
    print(f"Loaded {len(df):,} bars ({start_date} to {end_date})")
    return df


def calculate_indicators(df):
    print("Calculating indicators...")

    # Donchian Channels (20)
    df["donchian_high"] = df["high"].rolling(window=BREAKOUT_PERIOD).max().shift(1)
    # Using shift(1) to avoid lookahead bias (breakout of *previous* N bars)

    # EMA(200)
    df["ema_200"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()

    # ADX(14)
    high_diff = df["high"].diff()
    low_diff = -df["low"].diff()

    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)

    tr1 = pd.DataFrame(high_diff).abs()
    tr2 = (df["high"] - df["close"].shift(1)).abs()
    tr3 = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Fix NaN propagation
    tr = tr.bfill()
    plus_dm = pd.Series(plus_dm, index=df.index).bfill()
    minus_dm = pd.Series(minus_dm, index=df.index).bfill()

    # Smooth ATR, +DI, -DI (Wilder's Smoothing)
    # Approx using ewm(alpha=1/period)
    atr = tr.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean() / atr)

    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    df["adx"] = dx.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()

    # Trailing Stop Helper (Low of last 5 bars)
    df["trailing_low"] = df["low"].rolling(window=TRAILING_STOP_BARS).min().shift(1)

    return df.dropna()


def run_backtest(df):
    print("Running backtest loop...")

    trades = []
    position = None

    closes = df["close"].values
    times = df.index
    lows = df["low"].values

    # Indicator arrays
    donchian_high = df["donchian_high"].values
    ema_200 = df["ema_200"].values
    adx = df["adx"].values
    trailing_low = df["trailing_low"].values

    for i in range(len(df)):
        if i < 20:
            continue

        current_close = closes[i]
        current_time = times[i]

        # Check Exit
        if position:
            # 1. Trailing Stop (Dynamic)
            # Stop moves up to the Low of last 5 bars IF it is higher than current stop
            new_trail = trailing_low[i]
            if new_trail > position["stop_loss"]:
                position["stop_loss"] = new_trail

            # Check if Hit Stop (Hard or Trailing)
            # We check Low of current bar vs Stop
            if lows[i] < position["stop_loss"]:
                exit_price = position["stop_loss"]  # Assumed execution
                pnl = (exit_price - position["entry_price"]) / PIP - COST_PER_TRADE
                trades.append(
                    {
                        "entry_time": position["entry_time"],
                        "exit_time": current_time,
                        "pnl_pips": pnl,
                        "duration_bars": i - position["idx"],
                        "exit_reason": "SL_Trail",
                    }
                )
                position = None

        # Check Entry (Long Only)
        elif not position:
            # Logic: Close > Donchian High AND ADX > 25 AND Close > EMA
            if (
                (current_close > donchian_high[i])
                and (adx[i] > ADX_THRESH)
                and (current_close > ema_200[i])
            ):
                # Valid Breakout
                position = {
                    "entry_price": current_close,
                    "entry_time": current_time,
                    "stop_loss": current_close - (HARD_STOP_PIPS * PIP),
                    "idx": i,
                }

    return pd.DataFrame(trades)


def analyze_performance(trades):
    if len(trades) == 0:
        print("No trades generated.")
        return

    print("\n" + "=" * 40)
    print("PERFORMANCE REPORT: TREND SCALPER")
    print("=" * 40)

    n_trades = len(trades)
    win_rate = (trades["pnl_pips"] > 0).mean()
    total_pips = trades["pnl_pips"].sum()
    avg_trade = trades["pnl_pips"].mean()

    print(f"Trades: {n_trades:,} ({n_trades/10:.1f} per month approx)")
    print(f"Win Rate: {win_rate:.1%}")
    print(f"Total Pips: {total_pips:.1f}")
    print(f"Avg Pips/Trade: {avg_trade:.2f}")

    # Drawdown
    trades["equity"] = trades["pnl_pips"].cumsum()
    trades["peak"] = trades["equity"].cummax()
    trades["drawdown"] = trades["equity"] - trades["peak"]
    trades["in_dd"] = trades["drawdown"] < 0

    max_dd_days = 0
    if trades["in_dd"].any():
        trades["dd_id"] = (trades["in_dd"] != trades["in_dd"].shift()).cumsum()
        groups = trades[trades["in_dd"]].groupby("dd_id")
        max_dd_days = (
            groups["exit_time"].max() - groups["entry_time"].min()
        ).dt.days.max()

    print(f"\nMax Drawdown Duration: {max_dd_days} days")

    # Save
    trades.to_csv(OUTPUT_DIR / "trend_scalper_trades.csv", index=False)
    print(f"\nSaved trades to {OUTPUT_DIR}/trend_scalper_trades.csv")


def main():
    df = load_data(RAW_DATA_PATH)
    df = calculate_indicators(df)
    trades = run_backtest(df)
    analyze_performance(trades)


if __name__ == "__main__":
    main()
