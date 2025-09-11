from __future__ import annotations

import logging
from pathlib import Path

from trading_platform.core.config import RunConfig


def initialize_run(config: RunConfig) -> Path:
    run_path = config.runs_dir / config.user_id / config.run_id
    run_path.mkdir(parents=True, exist_ok=True)
    config_path = run_path / "config.json"
    config_path.write_text(config.model_dump_json(indent=2))
    logging.info(f"Initialized run artifacts at: {run_path}")
    return run_path


if __name__ == "__main__":
    default_config = RunConfig(user_id="default_user", log_level="INFO")
    initialize_run(default_config)
