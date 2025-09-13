from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from trading_platform.core.config import RunConfig
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import save_run_brief
from trading_platform.reporting.html_export import save_html_report


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


def finalize_run(
    run_path: Path,
    *,
    meta: dict,
    params: dict,
    trades: list[Trade],
    initial_cash: float,
    regimes_at_entry: list[str] | None = None,
    instrument_definitions: dict[str, Any] | None = None,
    cost_model: dict[str, Any] | None = None,
    fill_policy: dict[str, Any] | None = None,
    tie_break_policy: dict[str, Any] | None = None,
    config: RunConfig | None = None,
    monte_carlo: dict[str, Any] | None = None,
    walk_forward: dict[str, Any] | None = None,
) -> Path:
    """Generate and save a brief for this run under the run_path.

    Returns the path to `brief.json`.
    """
    # If a config is provided, use its snapshots as defaults
    if config is not None:
        instrument_definitions = instrument_definitions or config.instrument_definitions
        cost_model = cost_model or config.cost_model
        fill_policy = fill_policy or config.fill_policy
        tie_break_policy = tie_break_policy or config.tie_break_policy
        monte_carlo = monte_carlo or config.monte_carlo
        walk_forward = walk_forward or config.walk_forward

    brief_path = save_run_brief(
        run_path,
        meta=meta,
        params=params,
        trades=trades,
        initial_cash=initial_cash,
        regimes_at_entry=regimes_at_entry,
        instrument_definitions=instrument_definitions,
        cost_model=cost_model,
        fill_policy=fill_policy,
        tie_break_policy=tie_break_policy,
        monte_carlo=monte_carlo,
        walk_forward=walk_forward,
    )
    # Also export a minimal HTML report (skeleton)
    try:
        save_html_report(run_path, meta=meta, trades=trades)
    except Exception:  # pragma: no cover - keep finalize robust
        pass
    return brief_path
