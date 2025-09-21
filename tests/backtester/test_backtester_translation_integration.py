# Validates: [BT-7.2]

import pandas as pd
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def test_backtester_with_rem_pips_stop_loss():
    """
    Tests that the Backtester, via the RiskExitManager, correctly handles a
    native 'pips'-based stop-loss rule.
    """
    # 1. Configuration with a native REM rule
    config = RunConfig(
        rem_config={"stop_loss": {"pips": 50}},
        instrument={"pip_location": 0.0001},  # For EUR_USD style
    )
    rem = RiskExitManager(config=config.rem_config or {})

    # 2. Market data where a 50-pip stop will be hit
    entry_price = 1.20000
    stop_price = entry_price - (50 * 0.0001)  # 1.19500

    market_data = pd.DataFrame(
        [
            {"open": 1.1900, "high": 1.1950, "low": 1.1850, "close": entry_price},
            {"open": 1.2010, "high": 1.2020, "low": stop_price, "close": 1.1960},
            {"open": 1.1960, "high": 1.1980, "low": 1.1940, "close": 1.1970},
        ],
        index=pd.to_datetime(
            [
                "2023-01-01 10:00",
                "2023-01-01 11:00",
                "2023-01-01 12:00",
            ]
        ).tz_localize("UTC"),
    )
    market_data["volume"] = 100

    # 3. A signal to trigger entry
    signals = pd.Series(["long", "long", "long"], index=market_data.index)

    # 4. A dummy strategy object
    strategy = CompiledStrategy(
        name="dummy",
        overlays=[],
        features=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )

    # 5. Run backtest
    trades = run_backtest(
        market_data=market_data,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
    )

    # 6. Assertions
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop-loss"
    assert trade.exit_price == stop_price
