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


# NOTE: Tests for campaign-plan and campaign-run commented out until
# earlier phases are implemented
# def test_cmd_campaign_plan(tmp_path):
#     """Test campaign-plan CLI command."""
#     ...
#
# def test_cmd_campaign_run(tmp_path):
#     """Test campaign-run CLI command."""
#     ...


def test_cmd_campaign_validate():
    """Test campaign-validate CLI command."""
    from trading_platform.cli import cmd_campaign_validate

    with patch(
        "trading_platform.ai.campaigns.validate_campaign_candidates"
    ) as mock_validate:
        args = argparse.Namespace(campaign_id="test")
        result = cmd_campaign_validate(args)

        mock_validate.assert_called_once_with("test")
        assert result == 0


def test_cmd_campaign_review():
    """Test campaign-review CLI command."""
    from trading_platform.cli import cmd_campaign_review

    with patch("trading_platform.ai.campaigns.generate_review_report") as mock_review:
        args = argparse.Namespace(campaign_id="test")
        result = cmd_campaign_review(args)

        mock_review.assert_called_once_with("test")
        assert result == 0


def test_cmd_campaign_approve():
    """Test campaign-approve CLI command."""
    from trading_platform.cli import cmd_campaign_approve

    with patch("trading_platform.ai.campaigns.approve_candidate") as mock_approve:
        args = argparse.Namespace(
            campaign_id="test", run_id="run_001", notes="Looks good"
        )
        result = cmd_campaign_approve(args)

        mock_approve.assert_called_once_with("test", "run_001", "Looks good")
        assert result == 0


def test_cmd_campaign_needs_rework():
    """Test campaign-needs-rework CLI command."""
    from trading_platform.cli import cmd_campaign_needs_rework

    with patch("trading_platform.ai.campaigns.mark_needs_rework") as mock_rework:
        args = argparse.Namespace(
            campaign_id="test",
            run_id="run_002",
            reason="Tweak params",
            suggestions="Lower stop",
        )
        result = cmd_campaign_needs_rework(args)

        mock_rework.assert_called_once_with(
            "test", "run_002", "Tweak params", "Lower stop"
        )
        assert result == 0


def test_cmd_campaign_enrich():
    """Test campaign-enrich CLI command."""
    from trading_platform.cli import cmd_campaign_enrich

    with patch("trading_platform.ai.campaigns.enrich_campaign_dataset") as mock_enrich:
        args = argparse.Namespace(campaign_id="test")
        result = cmd_campaign_enrich(args)

        mock_enrich.assert_called_once_with("test")
        assert result == 0


def test_cmd_campaign_publish():
    """Test campaign-publish CLI command."""
    from trading_platform.cli import cmd_campaign_publish

    with patch(
        "trading_platform.ai.campaigns.publish_campaign_dataset"
    ) as mock_publish:
        args = argparse.Namespace(campaign_id="test")
        result = cmd_campaign_publish(args)

        mock_publish.assert_called_once_with("test")
        assert result == 0
