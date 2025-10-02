"""Debug: Generate signals for 20/80 params and count them."""

import json
import yaml
import pandas as pd
from pathlib import Path
from trading_platform.strategy.yaml_strategy import compile_strategy
from trading_platform.data.loader import load_instrument_data

# Load the strategy config
strat_cfg = yaml.safe_load(Path("config/strategy/ema_crossover.yaml").read_text())

# Override parameters to 20/80
strat_cfg["parameters"] = {
    "ema_fast_length": 20,
    "ema_slow_length": 80,
    "slope_filter": False
}

# Load data
df = load_instrument_data("EUR_USD", "1H", "2013-01-01", "2025-09-26")
print(f"Data shape: {df.shape}")
print(f"Data period: {df.index.min()} to {df.index.max()}")

# Compile strategy and generate signals
strat = compile_strategy(strat_cfg)
signals = strat.generate_signals(df)

print(f"\nSignals shape: {signals.shape}")
print(f"Signal value counts:")
print(signals.value_counts())

# Check for entry signals specifically
entry_signals = signals[signals.isin(["enter_long", "enter_short"])]
print(f"\nEntry signals: {len(entry_signals)}")
print(f"  enter_long: {(signals == 'enter_long').sum()}")
print(f"  enter_short: {(signals == 'enter_short').sum()}")
