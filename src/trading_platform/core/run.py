from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from trading_platform.core.config import RunConfig
from trading_platform.core.robustness import (
    monte_carlo_summary,
    parameter_search,
    walk_forward_summary,
)
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import save_run_brief
from trading_platform.reporting.csv_export import save_trades_csv
from trading_platform.reporting.html_export import save_html_report


def initialize_run(config: RunConfig) -> Path:
    run_path = config.runs_dir / config.user_id / config.run_id
    run_path.mkdir(parents=True, exist_ok=True)
    config_path = run_path / "config.json"
    config_path.write_text(config.model_dump_json(indent=2))
    logging.info(f"Initialized run artifacts at: {run_path}")
    return run_path


if __name__ == "__main__":  # pragma: no cover
    default_config = RunConfig(
        user_id="default_user",
        log_level="INFO",
        run_seed=42,
        initial_cash=100000.0,
        allow_flip_on_bar=False,
    )  # pragma: no cover
    initialize_run(default_config)  # pragma: no cover


def finalize_run(
    run_path: Path,
    *,
    meta: dict,
    params: dict,
    trades: list[Trade],
    initial_cash: float,
    regimes_at_entry: list[str] | None = None,
    data_quality: dict[str, Any] | None = None,
    instrument_definitions: dict[str, Any] | None = None,
    cost_model: dict[str, Any] | None = None,
    fill_policy: dict[str, Any] | None = None,
    tie_break_policy: dict[str, Any] | None = None,
    config: RunConfig | None = None,
    monte_carlo: dict[str, Any] | None = None,
    walk_forward: dict[str, Any] | None = None,
    exposure_curve: list[tuple[datetime, float]] | None = None,
    skipped_trades: list[dict[str, Any]] | None = None,
) -> Path:
    """Generate and save a brief for this run under the run_path.

    Returns the path to `brief.json`.
    """
    # If a config is provided, use its snapshots as defaults
    blackout_policy: dict[str, Any] | None = None
    if config is not None:
        # If params are not explicitly provided, try to get them from the strategy
        if not params:
            params = config.strategy.get("parameters", {})

        instrument_definitions = instrument_definitions or config.instrument_definitions
        cost_model = cost_model or config.cost_model
        fill_policy = fill_policy or config.fill_policy
        tie_break_policy = tie_break_policy or config.tie_break_policy
        monte_carlo = monte_carlo or config.monte_carlo
        walk_forward = walk_forward or config.walk_forward
        blackout_policy = {
            "blackout_utc": config.blackout_utc,
            "blackout_events": config.blackout_events,
        }

    # Compute optional robustness/search summaries from config toggles
    mc_cfg = config.monte_carlo if config is not None else {}
    wf_cfg = config.walk_forward if config is not None else {}
    ps_cfg = config.parameter_search if config is not None else {}

    mc_summary = None
    try:
        trials = int(mc_cfg.get("trials", 0)) if isinstance(mc_cfg, dict) else 0
        if trials > 0 or mc_cfg.get("enabled"):
            mc_summary = monte_carlo_summary(
                trades,
                initial_cash=initial_cash,
                trials=max(trials, 100),
                seed=mc_cfg.get("seed"),
                mode=str(mc_cfg.get("mode", "bootstrap_trades")),
            )
    except Exception:
        mc_summary = None  # pragma: no cover

    wf_summary = None
    try:
        window = int(wf_cfg.get("window", 0)) if isinstance(wf_cfg, dict) else 0
        step = int(wf_cfg.get("step", 0)) if isinstance(wf_cfg, dict) else 0
        if window > 0 and step > 0:
            wf_summary = walk_forward_summary(trades, window=window, step=step)
    except Exception:
        wf_summary = None  # pragma: no cover

    ps_summary = None
    try:
        if isinstance(ps_cfg, dict) and (
            ps_cfg.get("grid") or ps_cfg.get("random_space")
        ):
            # Simple objective based on current trades
            total_pnl = float(sum(t.pnl for t in trades))

            def eval_fn(_p: dict[str, Any]) -> float:
                obj = str(ps_cfg.get("objective", "total_pnl"))
                return total_pnl if obj == "total_pnl" else total_pnl

            ps_summary = parameter_search(
                grid=ps_cfg.get("grid"),
                random_space=ps_cfg.get("random_space"),
                n_samples=ps_cfg.get("n_samples"),
                seed=ps_cfg.get("seed"),
                evaluate=eval_fn,
            )
    except Exception:
        ps_summary = None  # pragma: no cover

    brief_path = save_run_brief(
        run_path,
        meta=meta,
        params=params,
        trades=trades,
        initial_cash=initial_cash,
        regimes_at_entry=regimes_at_entry,
        data_quality=data_quality,
        instrument_definitions=instrument_definitions,
        cost_model=cost_model,
        fill_policy=fill_policy,
        tie_break_policy=tie_break_policy,
        monte_carlo=mc_summary if mc_summary is not None else monte_carlo,
        walk_forward=wf_summary if wf_summary is not None else walk_forward,
        blackout_policy=blackout_policy,
        exposure_curve=exposure_curve,
        config_snapshot=(config.model_dump() if config is not None else None),
        parameter_search=ps_summary
        if ps_summary is not None
        else (config.parameter_search if config is not None else None),
        skipped_trades=skipped_trades,
    )
    # Also export a minimal HTML report (skeleton)
    try:
        save_html_report(run_path, meta=meta, trades=trades)
    except Exception:  # pragma: no cover - keep finalize robust
        pass
    # Export trades CSV for convenience
    try:
        save_trades_csv(run_path / "trades.csv", trades)
    except Exception:  # pragma: no cover
        pass
    return brief_path
