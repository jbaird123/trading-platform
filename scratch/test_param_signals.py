#!/usr/bin/env python3
"""Test if different parameters produce different signals."""

import pandas as pd
import yaml
from trading_platform.strategy.yaml_strategy import compile_strategy
from trading_platform.data.loader import load_instrument_data

# Load data from recent run
import json
run_path = "runs/researcher/run_20251001_020346_utc"
with open(f"{run_path}/config.json") as f:
    cfg = json.load(f)

data_request = cfg["data_request"]
from pathlib import Path
df, _ = load_instrument_data(data_request, data_root=Path("data"))
print(f"Data shape: {df.shape}")

# Test with base parameters
with open("config/strategy/ema_crossover.yaml") as f:
    strat_cfg1 = yaml.safe_load(f)

strat_cfg1["parameters"]["ema_fast_length"] = 12
strat_cfg1["parameters"]["ema_slow_length"] = 50
strat1 = compile_strategy(strat_cfg1)
sig1 = strat1.generate_signals(df)

# Test with different parameters
with open("config/strategy/ema_crossover.yaml") as f:
    strat_cfg2 = yaml.safe_load(f)

strat_cfg2["parameters"]["ema_fast_length"] = 10
strat_cfg2["parameters"]["ema_slow_length"] = 40
strat2 = compile_strategy(strat_cfg2)
sig2 = strat2.generate_signals(df)

print(f"\nConfig 1 (12/50):")
print(f"  Long signals: {(sig1 == 'long').sum()}")
print(f"  Short signals: {(sig1 == 'short').sum()}")
print(f"  Neutral: {(sig1 == 'neutral').sum()}")

print(f"\nConfig 2 (10/40):")
print(f"  Long signals: {(sig2 == 'long').sum()}")
print(f"  Short signals: {(sig2 == 'short').sum()}")
print(f"  Neutral: {(sig2 == 'neutral').sum()}")

print(f"\nSignals are identical: {(sig1 == sig2).all()}")

# Check EMAs
if strat1._feature_df is not None and strat2._feature_df is not None:
    ema_fast_1 = strat1._feature_df["ema_fast"].iloc[-10:].values
    ema_fast_2 = strat2._feature_df["ema_fast"].iloc[-10:].values

    print(f"\nEMA fast (12) last value: {ema_fast_1[-1]:.5f}")
    print(f"EMA fast (10) last value: {ema_fast_2[-1]:.5f}")
    print(f"EMAs are different: {not (ema_fast_1 == ema_fast_2).all()}")
