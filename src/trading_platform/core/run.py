from __future__ import annotations
from pathlib import Path
import json
from .utils import gen_run_id, get_logger
from .config import RunConfig


def hello_run(config: RunConfig | None = None) -> Path:
    """
    Creates a new run directory and artifacts based on the provided configuration.
    This serves as the entrypoint for Phase 1.1.
    """
    if config is None:
        config = RunConfig(run_id=gen_run_id())

    out = config.runs_dir / config.run_id
    out.mkdir(parents=True, exist_ok=True)

    (out / "config.json").write_text(config.model_dump_json(indent=2))
    get_logger().info(f"Created {out/'config.json'}")
    return out


if __name__ == "__main__":
    hello_run()
