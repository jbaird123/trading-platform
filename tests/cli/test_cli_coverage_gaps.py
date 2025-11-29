"""Tests to achieve 100% coverage for cli.py."""

from unittest.mock import Mock, patch

import pandas as pd
from trading_platform.cli import cmd_run_backtest


def test_cli_data_request_with_all_filters(tmp_path):
    """Test CLI with data_request that has timeframe, start, and end filtering.

    Note: run_backtest() now owns data loading from config.data_request.
    This test verifies the CLI calls run_backtest with the config.
    """
    args = Mock(
        config="test_config.yaml",
        demo=False,
        last_days=None,
        limit=None,
        overrides=None,
    )
    mock_run_config = {
        "data_request": {
            "symbol": "EURUSD",
            "timeframe": "1H",
            "start": "2023-01-02",
            "end": "2023-01-02",
        },
        "strategy": {
            "strategy_name": "test_strategy",
            "long_entry_rules": [
                {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"field": "close"},
                            "right": {"value": 1},
                        }
                    ]
                }
            ],
            "long_exit_rules": [
                {
                    "all_of": [
                        {
                            "condition": "is_below",
                            "left": {"field": "close"},
                            "right": {"value": 1},
                        }
                    ]
                }
            ],
        },
    }

    mock_df = pd.DataFrame(
        {"close": [1.0, 2.0, 3.0]},
        index=pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"], utc=True),
    )

    with patch(
        "trading_platform.cli._load_config",
        return_value=mock_run_config,
    ), patch(
        "trading_platform.cli.RunConfig.model_validate", return_value=Mock()
    ), patch(
        "trading_platform.cli.initialize_run", return_value=tmp_path / "test_run"
    ), patch(
        "trading_platform.cli.DataHandler", autospec=True
    ) as mock_data_handler, patch(
        "trading_platform.cli.run_backtest"
    ) as mock_run_backtest, patch("trading_platform.cli.finalize_run"), patch(
        "builtins.print"
    ):
        # Mock DataHandler for CLI's RMM/walk-forward needs (if any)
        mock_instance = mock_data_handler.return_value
        mock_instance.get_data.return_value = mock_df
        mock_instance.data_quality_flags = []

        # run_backtest now returns dict with market_data for downstream use
        mock_run_backtest.return_value = {
            "trades": [],
            "equity_curve": [],
            "skipped": [],
            "strategy_name": "test_strategy",
            "initial_capital": 100000,
            "compiled_strategy": Mock(
                name="test_strategy",
                _feature_df=mock_df,
                generate_signals=Mock(
                    return_value=pd.Series([None] * 3, index=mock_df.index)
                ),
            ),
            "feature_enriched_df": mock_df,
            "market_data": mock_df,
            "data_handler": mock_instance,
        }

        cmd_run_backtest(args)

        # Verify run_backtest was called (it now owns data loading)
        mock_run_backtest.assert_called_once()
        # market_data is no longer a parameter - run_backtest loads it internally
        assert "market_data" not in mock_run_backtest.call_args.kwargs


def test_cli_no_data_request_uses_toy_data(tmp_path):
    """Test CLI when no data_request is provided - should use toy data."""
    args = Mock(
        config="test_config.yaml",
        demo=False,
        last_days=None,
        limit=None,
        overrides=None,
    )
    mock_run_config = {
        "strategy": {
            "strategy_name": "test_strategy",
            "long_entry_rules": [
                {
                    "all_of": [
                        {
                            "condition": "is_above",
                            "left": {"field": "close"},
                            "right": {"value": 1},
                        }
                    ]
                }
            ],
            "long_exit_rules": [
                {
                    "all_of": [
                        {
                            "condition": "is_below",
                            "left": {"field": "close"},
                            "right": {"value": 1},
                        }
                    ]
                }
            ],
        },
    }

    with patch(
        "trading_platform.cli._load_config",
        return_value=mock_run_config,
    ), patch(
        "trading_platform.cli.RunConfig.model_validate", return_value=Mock()
    ), patch(
        "trading_platform.cli.initialize_run", return_value=tmp_path / "test_run"
    ), patch("trading_platform.cli.DataHandler") as mock_data_handler, patch(
        "trading_platform.cli.run_backtest", return_value=(Mock(), Mock(), Mock())
    ), patch("trading_platform.cli.finalize_run"), patch("builtins.print"):
        result = cmd_run_backtest(args)
        assert result == 0
        mock_data_handler.assert_not_called()
