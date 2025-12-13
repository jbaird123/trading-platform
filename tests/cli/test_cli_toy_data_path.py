# Validates: [SYS-1.7.2]
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from trading_platform.cli import cmd_run_backtest
from trading_platform.strategy.yaml_strategy import CompiledStrategy


def _dummy_strategy() -> CompiledStrategy:
    return CompiledStrategy(
        name="dummy",
        features=[],
        overlays=[],
        long_entry_blocks=[],
        long_exit_blocks=[],
        short_entry_blocks=[],
        short_exit_blocks=[],
        parameters={},
    )


def test_cmd_run_backtest_toy_data_path(tmp_path: Path, monkeypatch) -> None:
    """Test CLI can run backtest with config.

    Note: run_backtest() now owns data loading from config.data_request.
    This test mocks run_backtest to focus on CLI artifact generation.
    """
    from unittest.mock import MagicMock, patch

    import pandas as pd

    monkeypatch.setattr("trading_platform.core.paths.RUNS_DIR", tmp_path)

    # Create mock data
    mock_df = pd.DataFrame(
        {
            "open": [1, 2],
            "high": [1, 2],
            "low": [1, 2],
            "close": [1, 2],
            "volume": [1, 1],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC"),
    )

    cfg = {
        "user_id": "toy_user",
        "runs_dir": str(tmp_path),
        "initial_cash": 1000,
        "instrument": {"symbol": "EURUSD", "timeframe": "1H"},
        "data_request": {"symbol": "EURUSD", "timeframe": "1H"},
        "strategy": {
            "strategy_name": "S",
            "long_entry_rules": [
                {
                    "any_of": [
                        {
                            "condition": "is_above",
                            "left": {"field": "close"},
                            "right": {"value": 1.5},
                        }
                    ]
                }
            ],
            "long_exit_rules": [
                {
                    "any_of": [
                        {
                            "condition": "is_below",
                            "left": {"field": "close"},
                            "right": {"value": 1.5},
                        }
                    ]
                }
            ],
        },
    }
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(cfg))
    ns = Namespace(demo=False, user="toy_user", config=str(p))

    # Mock run_backtest to return expected structure
    mock_strat = MagicMock()
    mock_strat.name = "S"
    mock_strat._feature_df = mock_df
    mock_strat.generate_signals.return_value = pd.Series(
        [None, None], index=mock_df.index
    )

    with patch("trading_platform.cli.run_backtest") as mock_backtest, patch(
        "trading_platform.cli.compile_strategy"
    ) as mock_compile:
        mock_compile.return_value = mock_strat
        mock_backtest.return_value = {
            "trades": [],
            "equity_curve": [],
            "skipped": [],
            "strategy_name": "S",
            "initial_capital": 1000,
            "compiled_strategy": mock_strat,
            "feature_enriched_df": mock_df,
            "market_data": mock_df,
            "data_handler": None,
        }
        rc = cmd_run_backtest(ns)
    assert rc == 0


def test_cmd_run_backtest_demo_flag(tmp_path: Path) -> None:
    ns = Namespace(demo=True, user="demo_user", config=None)
    rc = cmd_run_backtest(ns)
    assert rc == 0
