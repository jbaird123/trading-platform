#!/usr/bin/env python3
"""
Debug script for Trend Scalper.
Prints indicator values to check if conditions are ever met.
"""

from pathlib import Path

import numpy as np
import pandas as pd

RAW_DATA_PATH = Path(
    "data/dvc/raw/full/eurusd/eurusd_interval_minute_1_20130101_20250823.csv"
)
BREAKOUT_PERIOD = 20
EMA_PERIOD = 200
ADX_PERIOD = 14


def main():
    print("Loading 2022 data for debug...")
    df = pd.read_csv(RAW_DATA_PATH, parse_dates=["timestamp"], index_col="timestamp")
    df = df.sort_index()
    # Filter 2022
    df = df[(df.index >= "2022-01-01") & (df.index <= "2022-01-05")].copy()
    print(f"Loaded {len(df)} rows")

    # Calc Indicators
    df["donchian_high"] = df["high"].rolling(window=BREAKOUT_PERIOD).max().shift(1)
    df["ema_200"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()

    # ADX Manual Calc
    high_diff = df["high"].diff()
    low_diff = -df["low"].diff()
    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)

    tr1 = float(0)
    # TR calculation was slightly redundant in previous version,
    # simplifying to standard TR
    tr1 = high_diff.abs()
    tr2 = (df["high"] - df["close"].shift(1)).abs()
    tr3 = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Fix NaN propagation for adjust=False
    tr = tr.bfill()
    plus_dm = pd.Series(plus_dm, index=df.index).bfill()
    minus_dm = pd.Series(minus_dm, index=df.index).bfill()

    atr = tr.ewm(com=ADX_PERIOD - 1, adjust=False).mean()  # Wilder's smoothing approx
    plus_di = 100 * (plus_dm.ewm(com=ADX_PERIOD - 1, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(com=ADX_PERIOD - 1, adjust=False).mean() / atr)
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    df["adx"] = dx.ewm(com=ADX_PERIOD - 1, adjust=False).mean()

    print("\nDataframe Info (Pre-DropNA):")
    print(df[["close", "donchian_high", "adx", "ema_200"]].describe())
    print("\nSample Data:")
    print(df[["close", "donchian_high", "adx"]].head(10))

    df = df.dropna()
    print(f"\nDataframe Rows (Post-DropNA): {len(df)}")

    # Check Conditions
    cond_breakout = df["close"] > df["donchian_high"]
    cond_ema = df["close"] > df["ema_200"]
    cond_adx = df["adx"] > 25

    print(f"Breakouts: {cond_breakout.sum()}")
    print(f"Above EMA: {cond_ema.sum()}")
    print(f"ADX > 25: {cond_adx.sum()}")

    combined = cond_breakout & cond_ema & cond_adx
    print(f"\nALL COMBINED (ADX>25): {combined.sum()}")

    print(
        f"ALL COMBINED (ADX>20): {(cond_breakout & cond_ema & (df['adx'] > 20)).sum()}"
    )
    print(
        f"ALL COMBINED (ADX>15): {(cond_breakout & cond_ema & (df['adx'] > 15)).sum()}"
    )


if __name__ == "__main__":
    main()
