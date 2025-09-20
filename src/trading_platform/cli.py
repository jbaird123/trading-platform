from __future__ import annotations

#! ruff: noqa: I001
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.core.demo import generate_demo_run
from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.core.run import finalize_run, initialize_run
from trading_platform.core.sweeps import (
    run_parameter_sweep,
    walk_forward_optimize_and_test,
)
from trading_platform.data.loader import load_from_catalog
from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.portfolio.trade import Trade
from trading_platform.regime_market_manager.engine import RMMEngine
from trading_platform.reporting.brief import compute_data_quality
from trading_platform.reporting.chart_export import (
    save_chart_from_brief,
    save_features_for_chart,
)
from trading_platform.reporting.compare_html import save_comparison_report
from trading_platform.reporting.csv_export import save_prices_csv
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import compile_strategy


def _get_git_commit() -> str | None:
    """Return the short git commit hash, or None if git fails."""
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode("ascii")
            .strip()
        )
    except Exception:
        return None


def _load_config(path: Path) -> dict[str, Any]:
    txt = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except Exception as exc:  # pragma: no cover
            raise SystemExit(
                "YAML config provided but PyYAML is not installed. "
                "Install pyyaml or use JSON."
            ) from exc
        return dict(yaml.safe_load(txt))  # type: ignore[no-any-return]
    return dict(json.loads(txt))


def cmd_run_backtest(args: argparse.Namespace) -> int:
    if args.demo:
        run_path = generate_demo_run(user_id=args.user)
        print(f"Run created at: {run_path}")
        print(f"- Brief: {run_path / 'brief.json'}")
        print(f"- Report: {run_path / 'report.html'}")
        print(f"- Trades: {run_path / 'trades.csv'}")
        return 0

    if not args.config:
        print("--config is required unless --demo is used", file=sys.stderr)
        return 2
    cfg_path = Path(args.config)
    cfg_raw = _load_config(cfg_path)
    cfg = RunConfig.model_validate(cfg_raw)
    run_path = initialize_run(cfg)

    # Minimal pipeline: toy data unless provided, simple strategy compile.
    df: pd.DataFrame
    dq_flags: list[str] = []
    data_req = cfg_raw.get("data_request")
    if isinstance(data_req, dict):
        # Delegate sourcing to Data Handler via catalog
        df, dq_flags = load_from_catalog(data_req)
    else:
        idx = pd.date_range("2024-01-01", periods=5, freq="h")
        vals = [1.0, 2.0, 3.0, 2.0, 1.0]
        df = pd.DataFrame(
            {
                "open": vals,
                "high": vals,
                "low": vals,
                "close": vals,
                "volume": [1] * 5,
            },
            index=idx,
        )

    # Strategy can be embedded or referenced via a separate YAML/JSON file
    strat_cfg = cfg_raw.get("strategy") or {
        "strategy_name": "CLI_Default",
        "entry_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": "close",
                        "right": 1.5,
                    }
                ]
            }
        ],
        "exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_below",
                        "left": "close",
                        "right": 1.5,
                    }
                ]
            }
        ],
    }
    # Optional fast-mode: limit dataset for quicker iterations
    fast_mode = cfg_raw.get("fast_mode") or {}
    if isinstance(fast_mode, dict):
        try:
            from datetime import timedelta

            last_days = int(fast_mode.get("last_days", 0) or 0)
            limit_bars = int(fast_mode.get("limit_bars", 0) or 0)
        except Exception:
            last_days = 0
            limit_bars = 0
        if last_days > 0 and isinstance(df.index, pd.DatetimeIndex):
            cutoff = df.index.max() - timedelta(days=last_days)
            df = df.loc[cutoff:]
        elif limit_bars > 0:
            df = df.tail(limit_bars)

    strat_path = cfg_raw.get("strategy_path")
    if strat_path:
        strat_cfg = _load_config(Path(str(strat_path)))
    # Apply optional per-run overrides for strategy tunables
    overrides = cfg_raw.get("strategy_overrides") or {}
    if isinstance(overrides, dict):
        # 1) Parameter-level overrides (e.g., slope_filter)
        param_over = overrides.get("parameters") or {}
        if isinstance(param_over, dict):
            base_params = strat_cfg.get("parameters") or {}
            if isinstance(base_params, dict):
                base_params.update({k: v for k, v in param_over.items()})
                strat_cfg["parameters"] = base_params
        # 2) Feature-level overrides (existing behavior)
        feat_over = (overrides.get("features") or {}) if overrides else {}
        if isinstance(feat_over, dict) and isinstance(strat_cfg.get("features"), list):
            for f in strat_cfg["features"]:
                name = str(f.get("name", ""))
                if name and name in feat_over and isinstance(feat_over[name], dict):
                    params = f.get("params") or {}
                    if isinstance(params, dict):
                        params.update({k: v for k, v in feat_over[name].items()})
                        f["params"] = params
    strat = compile_strategy(strat_cfg)
    signals = strat.generate_signals(df)
    # Persist prices and features for charts before finalize_run
    try:
        save_prices_csv(run_path / "prices.csv", df)
    except Exception:
        pass
    try:
        fdf = getattr(strat, "_feature_df", None)
        if fdf is not None:
            save_features_for_chart(run_path, fdf, strat.features)
    except Exception:
        pass

    # REM can be embedded or referenced via a separate file
    rem_cfg = cfg_raw.get("rem_config") or {}
    rem_path = cfg_raw.get("rem_path")
    if rem_path:
        rem_cfg = _load_config(Path(str(rem_path)))
    rem = RiskExitManager(config=rem_cfg)

    # RMM optional for legacy configs; if present, build per-bar context
    rmm_context: dict[datetime, dict[str, Any]] | None = None
    rmm_cfg: dict[str, Any] | None = (
        cfg.rmm_config if isinstance(cfg.rmm_config, dict) else None
    )
    rmm_path = cfg_raw.get("rmm_path")
    if rmm_path:
        rmm_cfg = _load_config(Path(str(rmm_path)))
    if isinstance(rmm_cfg, dict) and rmm_cfg:
        try:
            RMMEngine.validate_config(rmm_cfg)
        except Exception as exc:  # pragma: no cover
            raise SystemExit(f"RMM config validation failed: {exc}") from exc
        rmm_engine = RMMEngine(config=rmm_cfg)
        daily_regimes = rmm_engine.classify_daily(df)
        rmm_policy = rmm_cfg.get("policy") or {}
        per_bar = rmm_engine.project_to_index(
            daily_regimes, cast(pd.DatetimeIndex, df.index), policy=rmm_policy
        )
        rmm_context = {
            cast(datetime, ts): {
                "label": str(row["label"]),
                "confidence": float(row["confidence"]),
                "allowed_sides": list(row["allowed_sides"] or []),
                "policy": rmm_policy,
            }
            for ts, row in per_bar.iterrows()
        }
        # Persist RMM spans for chart shading
        try:

            def _mode(sides: list[str] | None) -> str:
                s = set(sides or [])
                if "long" in s and "short" in s:
                    return "both"
                if "long" in s:
                    return "long_only"
                if "short" in s:
                    return "short_only"
                return "blocked"

            spans: list[dict[str, object]] = []
            prev_mode: str | None = None
            start_ts: datetime | None = None
            prev_ts: datetime | None = None
            for ts, row in per_bar.iterrows():
                ts_dt = cast(datetime, ts)
                mode = _mode(list(row["allowed_sides"] or []))
                if prev_mode is None:
                    prev_mode = mode
                    start_ts = ts_dt
                elif mode != prev_mode:
                    if start_ts is not None and prev_ts is not None:
                        spans.append(
                            {
                                "start": start_ts.isoformat(),
                                "end": prev_ts.isoformat(),
                                "mode": prev_mode,
                            }
                        )
                    prev_mode = mode
                    start_ts = ts_dt
                prev_ts = ts_dt
            if prev_mode is not None and start_ts is not None and prev_ts is not None:
                spans.append(
                    {
                        "start": start_ts.isoformat(),
                        "end": prev_ts.isoformat(),
                        "mode": prev_mode,
                    }
                )
            spans_path = run_path / "rmm_spans.json"
            spans_path.write_text(json.dumps(spans))
            print(f"- RMM spans: {spans_path}")
        except Exception:
            pass

    # Output toggles; default to no exposure unless explicitly requested
    ret_exp = bool(cfg_raw.get("return_exposure", False))
    ret_skips = bool(cfg_raw.get("return_skips", True))

    res = run_backtest(
        market_data=df,
        signals=signals,
        strategy=strat,
        config=cfg,
        rem=rem,
        rmm_context=rmm_context,
        return_exposure=ret_exp,
        return_skips=ret_skips,
    )
    skips: list[dict[str, Any]] = []
    if isinstance(res, tuple):
        if len(res) == 3:
            trades = cast(list[Trade], res[0])
            exposure = cast(list[tuple[datetime, float]], res[1])
            skips = cast(list[dict[str, Any]], res[2])
        else:
            trades = cast(list[Trade], res[0])
            exposure = cast(list[tuple[datetime, float]], res[1])
    else:
        trades = cast(list[Trade], res)
        exposure = []

    meta = {
        "strategy_name": strat.name,
        "run_id": cfg.run_id,
        "git_commit": _get_git_commit(),
        "run_seed": cfg.run_seed,
    }
    # Snapshot parameters in brief: prefer explicit run-time params,
    # then strategy defaults
    params_snapshot: dict[str, Any] = {}
    if isinstance(cfg_raw.get("strategy_params"), dict):
        params_snapshot = dict(cfg_raw["strategy_params"])  # user-specified
    elif isinstance(strat_cfg.get("parameters"), dict):
        params_snapshot = dict(strat_cfg["parameters"])  # strategy defaults
    dq = compute_data_quality(df)
    if dq_flags:
        dq = {**dq, "loader_flags": dq_flags}

    # Optional parameter sweep (full re-runs for candidates)
    ps_cfg = cfg_raw.get("parameter_search") or {}
    ps_results = None
    if isinstance(ps_cfg, dict) and (ps_cfg.get("grid") or ps_cfg.get("random_space")):
        ps_results = run_parameter_sweep(
            df,
            cfg_raw,
            strat_cfg,
            grid=ps_cfg.get("grid"),
            random_space=ps_cfg.get("random_space"),
            n_samples=ps_cfg.get("n_samples"),
            seed=ps_cfg.get("seed"),
            objective=str(ps_cfg.get("objective", "total_pnl")),
            dd_penalty=ps_cfg.get("dd_penalty"),
            vol_penalty=ps_cfg.get("vol_penalty"),
            debug_dir=run_path / "debug",
        )

    # Optional walk-forward optimize→test (requires grid)
    wf_cfg = cfg_raw.get("walk_forward") or {}
    wf_results = None
    if (
        isinstance(wf_cfg, dict)
        and int(wf_cfg.get("window", 0)) > 0
        and int(wf_cfg.get("step", 0)) > 0
        and isinstance(ps_cfg, dict)
        and ps_cfg.get("grid")
    ):
        grid_cfg = ps_cfg.get("grid")
        grid_typed = cast(dict[str, list[Any]], grid_cfg)
        wf_results = walk_forward_optimize_and_test(
            df,
            cfg_raw,
            strat_cfg,
            window=int(wf_cfg.get("window", 0)),
            step=int(wf_cfg.get("step", 0)),
            grid=grid_typed,
            seed=ps_cfg.get("seed"),
            objective=str(ps_cfg.get("objective", "total_pnl")),
            dd_penalty=ps_cfg.get("dd_penalty"),
            vol_penalty=ps_cfg.get("vol_penalty"),
        )

    # Optional Monte Carlo (bar-level resimulation)
    mc_cfg = cfg_raw.get("monte_carlo") or {}
    mc_results = None
    if isinstance(mc_cfg, dict) and str(mc_cfg.get("mode")) in {
        "bar_resimulation",
        "bar_bootstrap",
    }:
        from trading_platform.core.sweeps import monte_carlo_resimulation

        mc_results = monte_carlo_resimulation(
            df,
            cfg_raw,
            strat_cfg,
            trials=int(mc_cfg.get("trials", 100)),
            seed=mc_cfg.get("seed"),
            mode=str(mc_cfg.get("mode")),
            cost_jitter=mc_cfg.get("cost_jitter"),
            perturbation=mc_cfg.get("perturbation"),
        )

    finalize_run(
        run_path,
        meta=meta,
        params=params_snapshot,
        trades=trades,
        initial_cash=float(cfg_raw.get("initial_cash", 100000.0)),
        config=cfg,
        exposure_curve=exposure,
        data_quality=dq,
        skipped_trades=skips,
        parameter_search=ps_results,
        walk_forward=wf_results,
        monte_carlo=mc_results,
    )
    print(f"Run created at: {run_path}")
    print(f"- Brief: {run_path / 'brief.json'}")
    print(f"- Report: {run_path / 'report.html'}")
    print(f"- Trades: {run_path / 'trades.csv'}")
    print(f"- Chart: {run_path / 'chart.html'}")
    return 0


def cmd_run_live(args: argparse.Namespace) -> int:
    if args.dry_run:
        print("Live controller (dry-run): OK")
        return 0
    if not args.config:
        print("--config is required (or use --dry-run)", file=sys.stderr)
        return 2
    cfg_raw = _load_config(Path(args.config))
    cfg = RunConfig.model_validate(cfg_raw)
    policy = TradingWindowPolicy.from_config(
        blackout_utc=cfg.blackout_utc, blackout_events=cfg.blackout_events
    )
    pm = PortfolioManager(initial_cash=float(cfg_raw.get("initial_cash", 100000.0)))
    adapter = OandaStubAdapter(pm=pm, policy=policy, pm_limits=cfg_raw.get("pm_limits"))
    adapter.connect()
    print("Live controller stub connected (adapter: OandaStubAdapter)")
    adapter.shutdown()
    return 0


def _find_last_briefs(runs_dir: Path, user: str | None, n: int) -> list[Path]:
    base = runs_dir / user if user else runs_dir
    briefs: list[tuple[float, Path]] = []
    if not base.exists():
        return []
    for run_dir in base.iterdir():
        if run_dir.is_dir():
            brief = run_dir / "brief.json"
            if brief.exists():
                briefs.append((brief.stat().st_mtime, brief))
    briefs.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in briefs[: max(0, n)]]


def cmd_compare(args: argparse.Namespace) -> int:
    last = int(getattr(args, "last", 0) or 0)
    if last >= 2:
        runs_dir = Path(str(getattr(args, "runs_dir", "runs")))
        user = getattr(args, "user", None)
        paths = _find_last_briefs(runs_dir, user, last)
        if len(paths) < 2:
            print("Not enough briefs found for --last.", file=sys.stderr)
            return 2
        # Generate pairwise consecutive comparisons: [0..1], [1..2], ...
        # Write comparisons under runs/<user>/comparisons by default
        out_dir = runs_dir / (user or "") / "comparisons"
        out_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for i in range(len(paths) - 1):
            a, b = paths[i + 1], paths[i]
            aid = json.loads(a.read_text()).get("meta", {}).get("run_id", a.parent.name)
            bid = json.loads(b.read_text()).get("meta", {}).get("run_id", b.parent.name)
            out = out_dir / f"compare_{aid}_vs_{bid}.html"
            save_comparison_report(a, b, out)
            written.append(out)
        print("Wrote:")
        for p in written:
            print(f"- {p}")
        return 0
    # Fallback: explicit a/b compare
    a = Path(args.a)
    b = Path(args.b)
    out = Path(str(args.out))
    if not a.exists() or not b.exists():
        print("Both input brief paths must exist", file=sys.stderr)
        return 2
    save_comparison_report(a, b, out)
    print(f"Comparison written to: {out}")
    return 0


def cmd_open_chart(args: argparse.Namespace) -> int:
    runs_dir = Path(str(getattr(args, "runs_dir", "runs")))
    user = getattr(args, "user", None)
    paths = _find_last_briefs(runs_dir, user, int(getattr(args, "last", 1)))
    if not paths:
        print("No runs found.", file=sys.stderr)
        return 2
    brief = paths[0]
    run_path = brief.parent
    out = run_path / "chart.html"
    if not out.exists():
        try:
            save_chart_from_brief(run_path)
        except Exception as exc:  # pragma: no cover
            print(f"Failed to generate chart: {exc}", file=sys.stderr)
            return 1
    print(f"Chart: {out}")
    if bool(getattr(args, "open", False)):
        try:
            import webbrowser

            webbrowser.open(out.resolve().as_uri())
        except Exception:
            pass
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="tp", description="Trading Platform CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("run-backtest", help="Run backtest and write artifacts")
    pb.add_argument("--config", help="Path to JSON/YAML RunConfig")
    pb.add_argument("--user", default="cli_user", help="User id for run path")
    pb.add_argument("--demo", action="store_true", help="Use demo backtest")
    pb.set_defaults(func=cmd_run_backtest)

    pl = sub.add_parser("run-live", help="Run live adapter/controller")
    pl.add_argument("--config", help="Path to JSON/YAML RunConfig")
    pl.add_argument("--dry-run", action="store_true", help="No-op live run")
    pl.set_defaults(func=cmd_run_live)

    pc = sub.add_parser("compare", help="Compare briefs and write HTML")
    pc.add_argument("a", nargs="?", help="Path to first brief.json")
    pc.add_argument("b", nargs="?", help="Path to second brief.json")
    pc.add_argument("--out", default="comparison.html", help="Output HTML path")
    pc.add_argument(
        "--last",
        type=int,
        default=0,
        help="Compare the last N runs (pairwise); ignores a/b when set",
    )
    pc.add_argument(
        "--runs-dir", default="runs", help="Root runs directory (for --last)"
    )
    pc.add_argument(
        "--user", default=None, help="User id under runs/ to search (for --last)"
    )
    pc.set_defaults(func=cmd_compare)

    po = sub.add_parser("open-chart", help="Open latest run chart")
    po.add_argument("--runs-dir", default="runs", help="Root runs directory")
    po.add_argument("--user", default=None, help="User id under runs/")
    po.add_argument("--last", type=int, default=1, help="Pick Nth latest run")
    po.add_argument("--open", action="store_true", help="Open in browser")
    po.set_defaults(func=cmd_open_chart)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
