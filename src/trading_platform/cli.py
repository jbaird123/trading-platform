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

from trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine
from trading_platform.backtester.core import run_backtest
from trading_platform.core import paths
from trading_platform.core.config import RunConfig
from trading_platform.core.demo import generate_demo_run
from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.core.robustness import walk_forward_summary
from trading_platform.core.run import finalize_run, initialize_run
from trading_platform.core.sweeps import (
    run_parameter_sweep,
    walk_forward_optimize_and_test,
)
from trading_platform.data.handler import DataHandler
from trading_platform.data.instrument import get_instrument_definition
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
            import yaml
        except Exception as exc:  # pragma: no cover
            raise SystemExit(
                "YAML config provided but PyYAML is not installed. "
                "Install pyyaml or use JSON."
            ) from exc
        return dict(yaml.safe_load(txt))
    return dict(json.loads(txt))


def cmd_run_backtest(args: argparse.Namespace) -> int:
    if args.demo and not args.config:
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

    # Load REM and RMM configs and include them in cfg_raw for proper config snapshot
    rem_path = cfg_raw.get("rem_path")
    if rem_path:
        loaded_rem_cfg = _load_config(Path(str(rem_path)))
        cfg_raw["rem_config"] = loaded_rem_cfg

    rmm_path = cfg_raw.get("rmm_path")
    if rmm_path:
        loaded_rmm_cfg = _load_config(Path(str(rmm_path)))
        cfg_raw["rmm_config"] = loaded_rmm_cfg

    cfg = RunConfig.model_validate(cfg_raw)
    run_path = initialize_run(cfg)

    # Initialize DataHandler for centralized data access with caching
    data_handler: DataHandler | None = None
    df: pd.DataFrame
    dq_flags: list[str] = []
    instrument_def = None  # Will be set if data_request present
    data_req = cfg_raw.get("data_request")
    if isinstance(data_req, dict):
        # Create DataHandler - loads raw data once, handles all resampling/caching
        instrument_def = get_instrument_definition(data_req["symbol"])
        data_handler = DataHandler(
            symbol=data_req["symbol"],
            data_root=paths.PROJECT_ROOT / "data",
            instrument=instrument_def,
        )
        dq_flags = data_handler.data_quality_flags

        # Get data for requested timeframe and date range
        # DataHandler caches complete datasets and applies filtering
        df = data_handler.get_data(
            timeframe=data_req.get("timeframe"),
            start=data_req.get("start"),
            end=data_req.get("end"),
        )
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

    # Persist processed market data for AI Lab analysis
    processed_data_path: Path | None = None
    try:
        processed_data_path = run_path / "processed_data.parquet"
        df.to_parquet(processed_data_path)
    except Exception:
        processed_data_path = None

    # Strategy can be embedded or referenced via a separate YAML/JSON file
    strat_cfg = cfg_raw.get("strategy")
    if not strat_cfg:
        # Try loading from strategy_path if provided
        strategy_path = cfg_raw.get("strategy_path")
        if strategy_path:
            strat_cfg = _load_config(Path(strategy_path))
        else:
            raise ValueError(
                "No strategy provided. Specify 'strategy_path' in config "
                "or embed 'strategy' definition."
            )
    # Optional fast-mode: limit dataset for quicker iterations
    fast_mode = cfg_raw.get("fast_mode") or {}
    if isinstance(fast_mode, dict):
        try:
            from datetime import timedelta

            last_days = int(fast_mode.get("last_days", 0) or 0)
            limit_bars = int(fast_mode.get("limit_bars", 0) or 0)
        except Exception:  # pragma: no cover
            last_days = 0  # pragma: no cover - Defensive: fallback if
            # fast_mode has invalid values
            limit_bars = 0  # pragma: no cover
        if last_days > 0 and isinstance(df.index, pd.DatetimeIndex):
            cutoff = df.index.max() - timedelta(days=last_days)
            df = df.loc[cutoff:]
        elif limit_bars > 0:
            df = df.tail(limit_bars)

    if isinstance(strat_cfg, dict) and "file_path" in strat_cfg:
        # Resolve file_path relative to the main config file
        p = Path(cfg_path.parent, strat_cfg["file_path"])
        strat_cfg = _load_config(p)

    # Apply strategy_params from config (used for parameter sweeps)
    # This allows the config to override strategy defaults
    strategy_params_from_cfg = cfg_raw.get("strategy_params")
    if isinstance(strategy_params_from_cfg, dict):
        base_params = strat_cfg.get("parameters") or {}
        if isinstance(base_params, dict):
            base_params.update({k: v for k, v in strategy_params_from_cfg.items()})
            strat_cfg["parameters"] = base_params

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

    # Persist raw signals for AI Lab analysis
    try:
        from trading_platform.core.signal import Signal

        signals_path = run_path / "signals.parquet"
        # Ensure signals are saved with proper column name
        if isinstance(signals, pd.Series):
            # Extract command strings from Signal objects for serialization
            signal_values = signals.apply(
                lambda x: x.command if isinstance(x, Signal) else x
            )
            signals_df = pd.DataFrame({"signal": signal_values})
        else:
            signals_df = pd.DataFrame(signals)
        signals_df.to_parquet(signals_path)
    except Exception:  # pragma: no cover
        signals_path = None  # pragma: no cover - Defensive: file save might fail

    # Persist prices and features for charts before finalize_run
    try:
        save_prices_csv(run_path / "prices.csv", df)
    except Exception:  # pragma: no cover
        pass  # pragma: no cover - Defensive: price save might fail
    try:
        fdf = getattr(strat, "_feature_df", None)
        if fdf is not None:
            save_features_for_chart(run_path, fdf, strat.features)
    except Exception:  # pragma: no cover
        pass  # pragma: no cover - Defensive: feature save might fail

    # REM can be embedded or referenced via a separate file
    rem_cfg: dict[str, Any] | None = cfg_raw.get("rem_config")
    # Pass complete instrument definition with all metadata (asset_class, etc.)
    instrument_dict = instrument_def.model_dump() if instrument_def else None
    rem = RiskExitManager(config=rem_cfg or {}, instrument=instrument_dict)

    # RMM optional for legacy configs; if present, build per-bar context
    rmm_context: dict[datetime, dict[str, Any]] | None = None
    rmm_cfg: dict[str, Any] | None = cfg_raw.get("rmm_config")
    rmm_spans_path: Path | None = None
    if isinstance(rmm_cfg, dict) and rmm_cfg:
        try:
            RMMEngine.validate_config(rmm_cfg)
        except Exception as exc:  # pragma: no cover
            raise SystemExit(f"RMM config validation failed: {exc}") from exc
        rmm_engine = RMMEngine(config=rmm_cfg)
        regime_timeframe = rmm_cfg.get("timeframe", "1D")
        classify_regime = getattr(rmm_engine, "classify_regime", None)
        if callable(classify_regime):
            regimes = classify_regime(df, timeframe=regime_timeframe)
        else:
            classify_daily = getattr(rmm_engine, "classify_daily", None)
            if not callable(classify_daily):
                raise SystemExit(
                    "RMM engine must implement classify_regime or classify_daily"
                )
            regimes = classify_daily(df)
        rmm_policy = rmm_cfg.get("policy") or {}
        per_bar = rmm_engine.project_to_index(
            regimes, cast(pd.DatetimeIndex, df.index), policy=rmm_policy
        )
        # Extract regime feature names from config
        feature_names = [
            f.get("name") for f in rmm_cfg.get("features", []) if f.get("name")
        ]

        # Build RMM context with full precision - rounding happens in brief.py
        rmm_context = {
            cast(datetime, ts): {
                "label": str(row["label"]),
                "confidence": float(row["confidence"]),
                "allowed_sides": list(row["allowed_sides"] or []),
                "policy": rmm_policy,
                "features": {
                    fname: row.get(fname)
                    for fname in feature_names
                    if fname in row.index
                },
                "timeframe": regime_timeframe,
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
            span_start: datetime | None = None
            prev_ts: datetime | None = None
            for ts, row in per_bar.iterrows():
                ts_dt = cast(datetime, ts)
                mode = _mode(list(row["allowed_sides"] or []))
                if prev_mode is None:
                    prev_mode = mode
                    span_start = ts_dt
                elif mode != prev_mode:
                    if span_start is not None and prev_ts is not None:
                        spans.append(
                            {
                                "start": span_start.isoformat(),
                                "end": prev_ts.isoformat(),
                                "mode": prev_mode,
                            }
                        )
                    prev_mode = mode
                    span_start = ts_dt
                prev_ts = ts_dt
            if prev_mode is not None and span_start is not None and prev_ts is not None:
                spans.append(
                    {
                        "start": span_start.isoformat(),
                        "end": prev_ts.isoformat(),
                        "mode": prev_mode,
                    }
                )
            rmm_spans_path = run_path / "rmm_spans.json"
            rmm_spans_path.write_text(json.dumps(spans))
            print(f"- RMM spans: {rmm_spans_path}")
        except Exception:  # pragma: no cover
            rmm_spans_path = (
                None  # pragma: no cover - Defensive: RMM span save might fail
            )

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
            data_handler=data_handler,
        )

    # Optional walk-forward analysis
    wf_cfg = cfg_raw.get("walk_forward") or {}
    wf_results = None
    if (
        isinstance(wf_cfg, dict)
        and int(wf_cfg.get("window", 0)) > 0
        and int(wf_cfg.get("step", 0)) > 0
    ):
        # If parameter_search grid is provided, do walk-forward OPTIMIZATION
        if isinstance(ps_cfg, dict) and ps_cfg.get("grid"):
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
                data_handler=data_handler,
            )
        else:
            # Otherwise, just do walk-forward ANALYSIS on existing trades
            # (splits trades by time into train/test windows and computes
            # OOS performance)
            wf_results = walk_forward_summary(
                trades,
                window=int(wf_cfg.get("window", 0)),
                step=int(wf_cfg.get("step", 0)),
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
            data_handler=data_handler,
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
        signals_path=signals_path,
        rmm_spans_path=rmm_spans_path,
        processed_data_path=processed_data_path,
    )
    print(f"Run created at: {run_path}")
    print(f"- Brief: {run_path / 'brief.json'}")
    print(f"- Report: {run_path / 'report.html'}")
    print(f"- Trades: {run_path / 'trades.csv'}")
    print(f"- Chart: {run_path / 'chart.html'}")
    return 0


def cmd_ai_diagnose(args: argparse.Namespace) -> int:
    if not args.brief:
        raise ValueError("--brief is required")

    brief_path = Path(args.brief)
    if not brief_path.exists():
        raise ValueError(f"No such file: {brief_path}")

    try:
        with open(brief_path) as f:
            brief_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding brief.json: {e}")

    # Map brief.json structure to what DiagnosticSynthesisEngine expects
    analysis_data = brief_data

    # Task 13.4: Train model if requested
    if getattr(args, "train_model", False):
        from trading_platform.ai.lab.trainer import (
            save_model,
            train_profitability_model,
        )

        model, features = train_profitability_model(brief_data)
        model_path = brief_path.parent / "profitability_model.joblib"
        save_model(model, str(model_path))
        print(f"Profitability model saved to {model_path}")

    engine = DiagnosticSynthesisEngine(analysis_data=analysis_data)
    engine.run()

    output_dir = brief_path.parent
    (output_dir / "ai_diagnostic_report.md").write_text(
        engine.generate_report_markdown()
    )
    diagnostic_json = engine.generate_report_json()
    (output_dir / "ai_diagnostic_report.json").write_text(diagnostic_json)

    # Update brief.json with recommendations from diagnostic report
    try:
        diagnostic_data = json.loads(diagnostic_json)
        recommendations = diagnostic_data.get("recommendations", [])
        if recommendations:
            brief_data["recommendations"] = recommendations
            with open(brief_path, "w") as f:
                json.dump(brief_data, f, indent=2)
            print(f"Updated {brief_path} with {len(recommendations)} recommendations")
    except Exception as e:  # pragma: no cover
        print(  # pragma: no cover - Defensive: brief recommendation update might fail
            f"Warning: Could not update brief with recommendations: {e}",
            file=sys.stderr,
        )

    # Task 4: Qualitative LLM report generation
    if getattr(args, "qualitative_report", False):
        print("Generating qualitative report via LLM...")
        try:
            from trading_platform.ai.llm_analysis.client import LlmApiClient
            from trading_platform.ai.llm_analysis.engine import LLMAnalysisEngine

            client = LlmApiClient()
            llm_engine = LLMAnalysisEngine(brief_data=brief_data, client=client)
            feedback = llm_engine.run()
            report_path = output_dir / "ai_qualitative_report.md"
            report_path.write_text(feedback)
            print(f"Qualitative report saved to {report_path}")
        except Exception as e:  # pragma: no cover
            print(
                f"Could not generate qualitative report: {e}", file=sys.stderr
            )  # pragma: no cover - Defensive: LLM report generation might fail

    print(f"AI diagnostic reports saved to {output_dir}")
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
    pm = PortfolioManager(
        base_currency="USD",
        initial_cash=float(cfg_raw.get("initial_cash", 100000.0)),
    )
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
    from trading_platform.core import paths

    last = int(getattr(args, "last", 0) or 0)
    if last >= 2:
        runs_dir = Path(str(getattr(args, "runs_dir", paths.RUNS_DIR)))
        user = getattr(args, "user", None)
        brief_paths = _find_last_briefs(runs_dir, user, last)
        if len(brief_paths) < 2:
            print("Not enough briefs found for --last.", file=sys.stderr)
            return 2
        # Generate pairwise consecutive comparisons: [0..1], [1..2], ...
        # Write comparisons under runs/<user>/comparisons by default
        out_dir = runs_dir / (user or "") / "comparisons"
        out_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for i in range(len(brief_paths) - 1):
            a, b = brief_paths[i + 1], brief_paths[i]
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
    from trading_platform.core import paths

    runs_dir = Path(str(getattr(args, "runs_dir", paths.RUNS_DIR)))
    user = getattr(args, "user", None)
    brief_paths = _find_last_briefs(runs_dir, user, int(getattr(args, "last", 1)))
    if not brief_paths:
        print("No runs found.", file=sys.stderr)
        return 2
    brief = brief_paths[0]
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
        "--runs-dir", default=paths.RUNS_DIR, help="Root runs directory (for --last)"
    )
    pc.add_argument(
        "--user", default=None, help="User id under runs/ to search (for --last)"
    )
    pc.set_defaults(func=cmd_compare)

    po = sub.add_parser("open-chart", help="Open latest run chart")
    po.add_argument("--runs-dir", default=paths.RUNS_DIR, help="Root runs directory")
    po.add_argument("--user", default=None, help="User id under runs/")
    po.add_argument("--last", type=int, default=1, help="Pick Nth latest run")
    po.add_argument("--open", action="store_true", help="Open in browser")
    po.set_defaults(func=cmd_open_chart)

    pad = sub.add_parser("ai-diagnose", help="Run AI diagnostic analysis on a brief")
    pad.add_argument("--brief", help="Path to brief.json file")
    pad.add_argument(
        "--train-model",
        action="store_true",
        help="Train ML profitability model and save to run directory",
    )
    pad.add_argument(
        "--qualitative-report",
        action="store_true",
        help="Generate a qualitative report using an external LLM. "
        "WARNING: This sends run data to a third-party API and may incur costs.",
    )
    pad.set_defaults(func=cmd_ai_diagnose)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
