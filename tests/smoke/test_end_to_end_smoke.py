# Validates: [SYS-1.10.2], [12) MVP Subset]
from __future__ import annotations

import json

from trading_platform.core.demo import generate_demo_run
from tests.test_helpers import get_empty_global_features_path


def test_demo_run_writes_artifacts(tmp_path):
    # Use unique user id to avoid collisions
    p = generate_demo_run(user_id="smoke_user")
    # Expect brief and report exist
    assert (p / "brief.json").exists()
    assert (p / "report.html").exists()


def test_e2e_run_with_contextual_features(tmp_path):
    """End-to-end test verifying contextual features appear in brief."""
    import pandas as pd
    from trading_platform.backtester.core import _run_backtest_simulation
    from trading_platform.core.config import RunConfig
    from trading_platform.core.run import finalize_run, initialize_run
    from trading_platform.risk_manager.core import RiskExitManager
    from trading_platform.strategy.yaml_strategy import CompiledStrategy

    # Create market data for backtest with enough bars for indicators
    # Need at least 200 bars for EMA(200), ATR(14), RSI(14)
    dates = pd.date_range("2024-01-01", periods=250, freq="1h")
    market_data = pd.DataFrame(
        {
            "open": [100.0 + i * 0.1 for i in range(250)],
            "high": [101.0 + i * 0.1 for i in range(250)],
            "low": [99.0 + i * 0.1 for i in range(250)],
            "close": [100.5 + i * 0.1 for i in range(250)],
            "volume": [1000 + i * 10 for i in range(250)],
        },
        index=dates,
    )

    # Create simple strategy
    strategy = CompiledStrategy(
        name="E2ETestStrategy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )
    strategy.generate_signals(market_data)

    # Generate signals with trades - enter after sufficient warmup
    # Total = 210 + 1 + 9 + 1 + 29 = 250
    signals = pd.Series(
        [None] * 210 + ["enter_long"] + [None] * 9 + ["exit_long"] + [None] * 29,
        index=market_data.index,
    )

    # Create config (will have default contextual features)
    # Only symbol is needed; other fields auto-populated from registry
    config = RunConfig.model_validate(
        {
            "user_id": "e2e_test",
            "run_id": "ctx_features_test",
            "instrument": {
                "symbol": "EURUSD",  # Use registered symbol
            },
        }
    )

    # Initialize run directory
    run_dir = initialize_run(config)

    # Run backtest
    rem = RiskExitManager(
        config={"stop_loss": {"type": "offset", "price_offset": 0.0010}}
    )
    result = _run_backtest_simulation(
        market_data=market_data,
        signals=signals,
        strategy=strategy,
        config=config,
        rem=rem,
        global_features_config_path=get_empty_global_features_path(),
    
    )

    # Handle return type (can be just trades or tuple with exposure/skipped)
    if isinstance(result, tuple):
        trades = result[0]
    else:
        trades = result

    # Finalize run (writes brief.json)
    meta = {"strategy_name": strategy.name, "run_id": config.run_id}
    params = strategy.parameters
    finalize_run(
        run_dir,
        meta=meta,
        params=params,
        trades=trades,
        initial_cash=config.initial_cash,
        config=config,
    )

    # Load the brief.json
    brief_path = run_dir / "brief.json"
    assert brief_path.exists(), "brief.json should exist"

    with open(brief_path) as f:
        brief = json.load(f)

    # Assert trades exist
    assert "trades" in brief
    trades_list = brief["trades"]
    assert len(trades_list) > 0, "Should have at least one trade"

    # Check first trade context structure
    first_trade = trades_list[0]
    assert "context_at_entry" in first_trade
    entry_context = first_trade["context_at_entry"]
    assert entry_context is not None, "context_at_entry should not be None"

    # Verify nested context structure with separate feature types
    assert "strategy_features" in entry_context
    assert "global_features" in entry_context

    global_features = entry_context["global_features"]

    # Verify global features (from global.yaml with timeframe prefix)
    assert "h1_atr_14" in global_features
    assert isinstance(global_features["h1_atr_14"], (int, float, type(None)))

    # Verify volume is in global features (market context)
    assert "volume" in global_features
    assert isinstance(global_features["volume"], (int, float))
