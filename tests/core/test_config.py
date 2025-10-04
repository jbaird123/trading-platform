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
    assert "All runs are stored in the workspace" in caplog.text
    assert "some_other_dir" in caplog.text
