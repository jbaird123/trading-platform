"""Tests to achieve 100% coverage for cli.py line 96."""

from unittest.mock import Mock, patch

from trading_platform.cli import cmd_run_backtest


def test_cli_data_request_with_start_end_filtering(tmp_path):
    """Test CLI with data_request that has start/end filtering - covers line 96."""

    # Create mock args
    args = Mock()
    args.demo = False
    args.config = "test_config.yaml"
    args.output_dir = None  # No output_dir override

    # Mock run config (no strategy embedded)
    mock_run_config = {
        "data_request": {
            "symbol": "EUR_USD",
            "start": "2023-01-01",
            "end": "2023-01-02",  # This should trigger the line 96 branch
        },
        "user_id": "test",
        "runs_dir": "runs",
        "initial_cash": 100000,
        "position_size": 1000,
        "instrument": {"symbol": "EUR_USD"},
        "strategy_path": "config/strategy/ema_crossover.yaml",
    }

    # Mock strategy config (separate from run config)
    mock_strategy = {
        "strategy_name": "test_strategy",
        "long_entry_rules": [
            {
                "all_of": [
                    {
                        "condition": "cross_above",
                        "left": {"field": "close"},
                        "right": {"value": 1.1},
                    }
                ]
            }
        ],
        "long_exit_rules": [
            {
                "all_of": [
                    {
                        "condition": "cross_below",
                        "left": {"field": "close"},
                        "right": {"value": 1.0},
                    }
                ]
            }
        ],
    }

    # Create a side_effect function to return different configs based on path
    def load_config_side_effect(path):
        if "strategy" in str(path):
            return mock_strategy
        else:
            return mock_run_config

    with patch(
        "trading_platform.cli._load_config", side_effect=load_config_side_effect
    ), patch(
        "trading_platform.cli.RunConfig.model_validate", return_value=Mock()
    ), patch(
        "trading_platform.cli.initialize_run", return_value=tmp_path / "test_run"
    ), patch(
        "trading_platform.cli.run_backtest", return_value=(Mock(), Mock(), Mock())
    ), patch("trading_platform.cli.finalize_run"), patch("builtins.print"):
        # jsonschema patch removed - no longer used for validation
        result = cmd_run_backtest(args)
        assert result == 0
