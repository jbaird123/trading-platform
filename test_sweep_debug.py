#!/usr/bin/env python3
"""Debug why parameter sweep produces identical results."""

import pandas as pd
import yaml
from copy import deepcopy
from trading_platform.strategy.yaml_strategy import compile_strategy

# Load base strategy
with open("config/strategy/ema_crossover.yaml") as f:
    base_cfg = yaml.safe_load(f)

# Create simple trending data
df = pd.DataFrame({
    "open": [1.0 + i*0.0001 for i in range(200)],
    "high": [1.0 + i*0.0001 + 0.0001 for i in range(200)],
    "low": [1.0 + i*0.0001 - 0.0001 for i in range(200)],
    "close": [1.0 + i*0.0001 for i in range(200)],
    "volume": [1000] * 200,
})

# Test two parameter combinations
params_list = [
    {"ema_fast_length": 10, "ema_slow_length": 40},
    {"ema_fast_length": 16, "ema_slow_length": 60},
]

for params in params_list:
    # Exactly how sweep does it
    scfg = deepcopy(base_cfg)
    strategy_params = dict(scfg.get("parameters") or {})
    strategy_params.update(params)
    scfg["parameters"] = strategy_params

    print(f"\n=== Testing params: {params} ===")
    print(f"Config parameters: {scfg['parameters']}")

    strat = compile_strategy(scfg)
    print(f"Compiled parameters: {strat.parameters}")

    sig = strat.generate_signals(df)

    # Count signals
    vc = sig.value_counts()
    print(f"Signal value_counts: {vc.to_dict()}")

    # Check crossovers manually
    if strat._feature_df is not None:
        ema_fast = strat._feature_df["ema_fast"]
        ema_slow = strat._feature_df["ema_slow"]

        cross_above = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        cross_below = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

        print(f"Manual crossover count - above: {cross_above.sum()}, below: {cross_below.sum()}")
        print(f"EMA fast last 3: {ema_fast.tail(3).values}")
        print(f"EMA slow last 3: {ema_slow.tail(3).values}")
