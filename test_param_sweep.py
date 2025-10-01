#!/usr/bin/env python3
"""Test if parameter substitution works in strategy compilation."""

import pandas as pd
import yaml
from trading_platform.strategy.yaml_strategy import compile_strategy

# Load base strategy
with open("config/strategy/ema_crossover.yaml") as f:
    strat_cfg = yaml.safe_load(f)

print("Base strategy parameters:", strat_cfg.get("parameters"))
print("Base EMA fast params:", strat_cfg["features"][0]["params"])
print("Base EMA slow params:", strat_cfg["features"][1]["params"])

# Update parameters like sweep does
strat_cfg["parameters"]["ema_fast_length"] = 10
strat_cfg["parameters"]["ema_slow_length"] = 40

print("\nUpdated strategy parameters:", strat_cfg.get("parameters"))

# Compile strategy
strat = compile_strategy(strat_cfg)

print("\nCompiled strategy parameters:", strat.parameters)
print("Compiled strategy features:", strat.features)

# Test with dummy data
df = pd.DataFrame({
    "open": [1.0] * 100,
    "high": [1.0] * 100,
    "low": [1.0] * 100,
    "close": [1.0] * 100,
    "volume": [1000] * 100,
})

# This will trigger compute_features with the parameters
sig = strat.generate_signals(df)

print("\nGenerated signals shape:", sig.shape)
print("Feature columns:", list(strat._feature_df.columns) if strat._feature_df is not None else "None")
