import logging

from trading_platform.core import paths
from trading_platform.core.config import RunConfig


def test_run_config_auto_populate_instrument_from_data_request() -> None:
    """Test instrument auto-populated from data_request."""
    # Validates: [REQ-CONFIG-001] Auto-populate instrument
    from trading_platform.core.config import RunConfig

    config = RunConfig.model_validate(
        {
            "run_id": "test",
            "data_request": {"symbol": "EUR_USD", "timeframe": "1H"},
        }
    )

    assert config.instrument is not None
    assert config.instrument["symbol"] == "EURUSD"
    assert config.instrument["timeframe"] == "1H"


def test_run_config_enforces_workspace_runs_dir(caplog) -> None:
    """Test that RunConfig overrides a user-provided runs_dir."""
    with caplog.at_level(logging.WARNING):
        config = RunConfig.model_validate(
            {
                "run_id": "test_override",
                "instrument": {"symbol": "EURUSD"},
                "runs_dir": "./some_other_dir",
            }
        )

    assert config.runs_dir.resolve() == paths.RUNS_DIR.resolve()
    assert "Ignoring configured `runs_dir`" in caplog.text
    assert "outside the project workspace" in caplog.text
    assert "some_other_dir" in caplog.text


def test_run_config_allows_custom_workspace_runs_dir(caplog) -> None:
    """Test RunConfig allows custom paths within workspace."""
    # Validates: Task 1 - Relaxed path validator

    # Test Case 1: Allow custom path within workspace
    custom_dir = paths.WORKSPACE_DIR / "custom_runs"
    with caplog.at_level(logging.WARNING):
        config = RunConfig.model_validate(
            {
                "run_id": "test_custom",
                "instrument": {"symbol": "EURUSD"},
                "runs_dir": str(custom_dir),
            }
        )

    # Should accept the custom directory within workspace
    assert config.runs_dir.resolve() == custom_dir.resolve()
    # Should not log a warning for valid workspace path
    assert "Ignoring configured `runs_dir`" not in caplog.text

    # Test Case 2: Reject path outside workspace
    caplog.clear()
    outside_dir = "/tmp/some_dir"
    with caplog.at_level(logging.WARNING):
        config = RunConfig.model_validate(
            {
                "run_id": "test_outside",
                "instrument": {"symbol": "EURUSD"},
                "runs_dir": outside_dir,
            }
        )

    # Should reject and fall back to default
    assert config.runs_dir.resolve() == paths.RUNS_DIR.resolve()
    # Should log a warning for path outside workspace
    assert "Ignoring configured `runs_dir`" in caplog.text
    assert "outside the project workspace" in caplog.text
    assert outside_dir in caplog.text
