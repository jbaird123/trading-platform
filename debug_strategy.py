"""Debug test for strategy signals."""

from datetime import datetime

import pandas as pd
from trading_platform.strategy.compiler import compile_strategy

# Create same market data as test
idx = [datetime(2024, 1, 1, h) for h in range(5)]
vals = [1.0, 0.05, 1.2, 0.05, 1.4]  # high -> low -> high -> low -> high
market_data = pd.DataFrame(
    {"open": vals, "high": vals, "low": vals, "close": vals, "volume": [1] * 5},
    index=idx,
)

# Same strategy config
strategy_cfg = {
    "strategy_name": "AlternatingTest",
    "parameters": {},
    "long_entry_rules": [
        {"any_of": [{"condition": "is_above", "left": "close", "right": 0.5}]}
    ],
    "long_exit_rules": [
        {"any_of": [{"condition": "is_below", "left": "close", "right": 0.1}]}
    ],
}

strat = compile_strategy(strategy_cfg)
signals = strat.generate_signals(market_data)

print("Market data close prices:")
print(market_data["close"].tolist())
print("\nGenerated signals:")
print(signals.tolist())

# Simulate the controller logic
current_state = "flat"
orders_placed = 0

print("\nController simulation:")
print(f"Initial state: {current_state}")

for i in range(len(market_data)):
    desired = str(signals.iloc[i])
    close_price = market_data.iloc[i]["close"]
    print(
        f"Row {i}: close={close_price}, desired='{desired}', current_state='{current_state}'"
    )

    if desired != current_state:
        print(f"  -> Place order: {current_state} to {desired}")
        orders_placed += 1
        current_state = desired
        if orders_placed >= 2:
            print(f"  -> Kill switch triggered after {orders_placed} orders")
            break
    else:
        print("  -> No order needed (same state)")

print(f"\nTotal orders placed: {orders_placed}")
