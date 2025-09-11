from __future__ import annotations

import json
from pathlib import Path

from trading_platform.core.config import RunConfig
from trading_platform.core.run import initialize_run


def test_initialize_run_creates_artifacts(tmp_path: Path):
    """
    Verifies that initialize_run creates the expected run directory and config file.
    """
    # 1. Setup: Create a config pointing to a temporary directory
    config = RunConfig(
        user_id="test_user", run_id="test_run_123", runs_dir=tmp_path, log_level="INFO"
    )

    # 2. Action: Call the function to be tested
    run_path = initialize_run(config)

    # 3. Assert: Verify the output is correct
    config_path = run_path / "config.json"
    assert run_path.is_dir()
    assert run_path.name == "test_run_123"
    assert run_path.parent.name == "test_user"
    assert config_path.is_file()

    # Verify the content of the config file
    data = json.loads(config_path.read_text())
    assert data["user_id"] == "test_user"
    assert data["run_id"] == "test_run_123"
