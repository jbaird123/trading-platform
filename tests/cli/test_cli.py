"""Tests for CLI output directory argument handling."""

import argparse
import json
from pathlib import Path
from unittest.mock import patch


def test_cmd_run_backtest_uses_output_dir(tmp_path: Path) -> None:
    """Test that run-backtest accepts and uses --output-dir argument."""
    # Validates: Task 3 - CLI output directory argument

    # Create a minimal valid config
    config_path = tmp_path / "config.json"
    config = {
        "run_id": "test",
        "instrument": {"symbol": "EURUSD"},
        "strategy": {
            "strategy_name": "Test",
            "long_entry_rules": [
                {"any_of": [{"condition": "is_above", "left": "close", "right": 1.0}]}
            ],
        },
    }
    config_path.write_text(json.dumps(config))

    # Define a custom output directory
    custom_output_dir = "workspace/test_cli_runs"

    # Mock the full CLI flow to capture the RunConfig
    with patch("trading_platform.cli.initialize_run") as mock_init, patch(
        "trading_platform.cli.finalize_run"
    ), patch("trading_platform.cli.run_backtest"), patch(
        "trading_platform.cli.compile_strategy"
    ), patch("trading_platform.data.loader.load_instrument_data"):
        # Mock initialize_run to return a path
        run_path = tmp_path / "runs/test"
        run_path.mkdir(parents=True)
        mock_init.return_value = run_path

        # Simulate CLI invocation with --output-dir
        args = argparse.Namespace(
            demo=False,
            config=str(config_path),
            user="test",
            output_dir=custom_output_dir,
        )

        from trading_platform.cli import cmd_run_backtest

        cmd_run_backtest(args)

        # Verify initialize_run was called once
        assert mock_init.call_count == 1

        # Capture the RunConfig passed to initialize_run
        called_config = mock_init.call_args[0][0]

        # Assert that runs_dir is a Path object equivalent to custom dir
        assert isinstance(called_config.runs_dir, Path)
        assert str(called_config.runs_dir) == custom_output_dir


def test_cmd_ai_curate_data():
    """Test that ai-curate-data CLI command invokes run_curation_pipeline."""
    # Validates: ML Data Curation - CLI entrypoint
    from trading_platform.cli import cmd_ai_curate_data

    with patch("trading_platform.cli.run_curation_pipeline") as mock_run_curation:
        args = argparse.Namespace(
            source_dir="/fake/dir", output_file="/fake/file.parquet"
        )

        cmd_ai_curate_data(args)

        # Assert that run_curation_pipeline was called exactly once
        mock_run_curation.assert_called_once_with(
            source_dir=Path("/fake/dir"), output_file=Path("/fake/file.parquet")
        )
