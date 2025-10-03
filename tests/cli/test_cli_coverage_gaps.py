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
    ), patch("trading_platform.cli.DataHandler", autospec=True) as mock_data_handler, patch(
        "trading_platform.cli.run_backtest"
    ) as mock_run_backtest, patch("trading_platform.cli.finalize_run"), patch(
        "builtins.print"
    ):
        mock_df = pd.DataFrame(
            {"close": [1.0, 2.0, 3.0]},
            index=pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"], utc=True),
        )
        # Simulate the filtered DataFrame that the DataHandler would return
        filtered_df_mock = mock_df.loc[mock_df.index == "2023-01-02"]
        mock_instance = mock_data_handler.return_value
        mock_instance.get_data.return_value = filtered_df_mock
        mock_instance.data_quality_flags = []

        cmd_run_backtest(args)

        mock_run_backtest.assert_called_once()
        filtered_df_result = mock_run_backtest.call_args.kwargs["market_data"]

        assert len(filtered_df_result) == 1
        assert filtered_df_result.index[0] == pd.to_datetime("2023-01-02", utc=True)


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
    ), patch("trading_platform.cli.DataHandler") as mock_data_handler, patch(
        "trading_platform.cli.run_backtest", return_value=(Mock(), Mock(), Mock())
    ), patch("trading_platform.cli.finalize_run"), patch("builtins.print"):
        result = cmd_run_backtest(args)
        assert result == 0
        mock_data_handler.assert_not_called()
