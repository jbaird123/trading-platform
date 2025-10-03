"""Tests to achieve 100% coverage for cli.py."""

from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from trading_platform.cli import cmd_run_backtest




def test_cli_data_request_with_all_filters():
    """Test CLI with data_request that has timeframe, start, and end filtering."""
    args = Mock(
        config="test_config.yaml",
        demo=False,
        last_days=None,
        limit=None,
        overrides=None,
    )
    mock_run_config = {
        "data_request": {
            "symbol": "EUR_USD",
            "timeframe": "1H",
            "start": "2023-01-02",
            "end": "2023-01-02",
        },
        "strategy_path": "strategy.yaml",
    }
    mock_strategy_config = {
        "strategy_name": "test_strategy",
        "long_entry_rules": [
            {"all_of": [{"condition": "is_above", "left": "close", "right": 1}]}
        ],
        "long_exit_rules": [
            {"all_of": [{"condition": "is_below", "left": "close", "right": 1}]}
        ],
    }

    with patch(
        "trading_platform.cli._load_config",
        side_effect=[mock_run_config, mock_strategy_config],
    ), patch(
        "trading_platform.cli.RunConfig.model_validate", return_value=Mock()
    ), patch(
        "trading_platform.cli.initialize_run", return_value=Path("test_run")
    ), patch("trading_platform.cli.load_instrument_data") as mock_load_data, patch(
        "trading_platform.cli.resample_ohlc"
    ) as mock_resample, patch(
        "trading_platform.cli.run_backtest"
    ) as mock_run_backtest, patch("trading_platform.cli.finalize_run"), patch(
        "builtins.print"
    ):
        mock_df = pd.DataFrame(
            {"close": [1.0, 2.0, 3.0]},
            index=pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"], utc=True),
        )
        mock_load_data.return_value = (mock_df, [])
        mock_resample.return_value = mock_df

        cmd_run_backtest(args)

        mock_run_backtest.assert_called_once()
        filtered_df = mock_run_backtest.call_args.kwargs["market_data"]

        assert len(filtered_df) == 1
        assert filtered_df.index[0] == pd.to_datetime("2023-01-02", utc=True)


def test_cli_no_data_request_uses_toy_data():
    """Test CLI when no data_request is provided - should use toy data."""
    args = Mock(
        config="test_config.yaml",
        demo=False,
        last_days=None,
        limit=None,
        overrides=None,
    )
    mock_run_config = {
        "strategy_path": "strategy.yaml",
    }
    mock_strategy_config = {
        "strategy_name": "test_strategy",
        "long_entry_rules": [
            {"all_of": [{"condition": "is_above", "left": "close", "right": 1}]}
        ],
        "long_exit_rules": [
            {"all_of": [{"condition": "is_below", "left": "close", "right": 1}]}
        ],
    }

    with patch(
        "trading_platform.cli._load_config",
        side_effect=[mock_run_config, mock_strategy_config],
    ), patch(
        "trading_platform.cli.RunConfig.model_validate", return_value=Mock()
    ), patch(
        "trading_platform.cli.initialize_run", return_value=Path("test_run")
    ), patch("trading_platform.cli.load_instrument_data") as mock_load_data, patch(
        "trading_platform.cli.run_backtest", return_value=(Mock(), Mock(), Mock())
    ), patch("trading_platform.cli.finalize_run"), patch("builtins.print"):
        result = cmd_run_backtest(args)
        assert result == 0
        mock_load_data.assert_not_called()
