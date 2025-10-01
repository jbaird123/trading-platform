#!/usr/bin/env python3
"""Simplified test - just check if EMAs differ with different params."""

import pandas as pd
from trading_platform.strategy.features import compute_features

# Create simple test data
df = pd.DataFrame({
    "close": [1.0 + i*0.001 for i in range(200)],  # Trending data
})

# Feature spec with variable substitution
features_spec = [
    {"name": "ema_fast", "type": "EMA", "params": {"length": "${ema_fast_length}"}, "source": "close"},
    {"name": "ema_slow", "type": "EMA", "params": {"length": "${ema_slow_length}"}, "source": "close"},
]

# Test 1: 12/50 parameters
params1 = {"ema_fast_length": 12, "ema_slow_length": 50}
df1 = compute_features(df, features_spec, params1)

# Test 2: 10/40 parameters
params2 = {"ema_fast_length": 10, "ema_slow_length": 40}
df2 = compute_features(df, features_spec, params2)

print("Params 1 (12/50) - EMA fast last 5 values:")
print(df1["ema_fast"].tail(5).values)

print("\nParams 2 (10/40) - EMA fast last 5 values:")
print(df2["ema_fast"].tail(5).values)

print(f"\nEMAs are different: {not (df1['ema_fast'].values == df2['ema_fast'].values).all()}")

# Check crossovers
cross_above_1 = (df1["ema_fast"] > df1["ema_slow"]) & (df1["ema_fast"].shift(1) <= df1["ema_slow"].shift(1))
cross_above_2 = (df2["ema_fast"] > df2["ema_slow"]) & (df2["ema_fast"].shift(1) <= df2["ema_slow"].shift(1))

print(f"\nParams 1 crossovers: {cross_above_1.sum()}")
print(f"Params 2 crossovers: {cross_above_2.sum()}")
print(f"Crossovers are different: {cross_above_1.sum() != cross_above_2.sum()}")
