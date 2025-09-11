from __future__ import annotations
from pathlib import Path
import json
from .utils import gen_run_id, get_logger
from .config import RunConfig


def initialize_run(config: RunConfig | None = None) -> Path:
    """
    Initializes a new run by creating a unique directory and saving the configuration.
    This is the main entrypoint for all platform executions.
    """
    if config is None:
        config = RunConfig(run_id=gen_run_id())

    out = config.runs_dir / config.user_id / config.run_id
    out.mkdir(parents=True, exist_ok=True)

    (out / "config.json").write_text(config.model_dump_json(indent=2))
    get_logger().info(f"Created {out/'config.json'}")
    return out


if __name__ == "__main__":
    initialize_run()
