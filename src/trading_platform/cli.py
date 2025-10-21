from __future__ import annotations

#! ruff: noqa: I001
import argparse
import json
import logging
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from trading_platform.ai.data_curation import run_curation_pipeline
from trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine
from trading_platform.backtester.core import run_backtest
from trading_platform.core import paths
from trading_platform.core.config import RunConfig
from trading_platform.core.demo import generate_demo_run
from trading_platform.core.policy import TradingWindowPolicy
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
from trading_platform.regime_market_manager.models import RMMConfig
from trading_platform.reporting.brief import compute_data_quality
from trading_platform.reporting.chart_export import (
    save_chart_from_brief,
    save_equity_chart_from_brief,
    save_features_for_chart,
)
from trading_platform.reporting.compare_html import save_comparison_report
from trading_platform.reporting.csv_export import save_prices_csv
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import compile_strategy
from trading_platform.utils.cache import clear_numba_cache

logger = logging.getLogger(__name__)


def _get_git_commit() -> str | None:
    """Return the short git commit hash, or None if git fails."""
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode("ascii")
            .strip()
        )
    except Exception as e:
        # Safe to continue: git commit hash is metadata only
        # System works fine without it
        logger.debug(f"Failed to get git commit hash: {e}")
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


def _run_backtest_logic(args: argparse.Namespace) -> int:
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

    # Apply CLI --output-dir override if provided
    output_dir = getattr(args, "output_dir", None)
    if output_dir:
        cfg_raw["runs_dir"] = output_dir

    # Load REM and RMM configs and include them in cfg_raw for proper config snapshot
    rem_path = cfg_raw.get("rem_path")
    if rem_path:
        loaded_rem_cfg = _load_config(Path(str(rem_path)))
        cfg_raw["rem_config"] = loaded_rem_cfg
        # Remove the path key after loading since it's not part of the schema
        cfg_raw.pop("rem_path", None)

    rmm_path = cfg_raw.get("rmm_path")
    if rmm_path:
        loaded_rmm_cfg = _load_config(Path(str(rmm_path)))
        cfg_raw["rmm_config"] = loaded_rmm_cfg
        # Remove the path key after loading since it's not part of the schema
        cfg_raw.pop("rmm_path", None)

    # Remove CLI-only fields that aren't part of RunConfig schema
    cfg_raw.pop("fast_mode", None)  # Removed - not needed
    cfg_raw.pop("rmm", None)  # Legacy field - not part of schema
    cfg_raw.pop("data", None)  # Legacy - use data_request instead
    strategy_overrides = cfg_raw.pop(
        "strategy_overrides", None
    )  # Extract for later use
    strategy_path = cfg_raw.pop("strategy_path", None)  # Extract for later use
    strategy_params = cfg_raw.pop("strategy_params", None)  # Extract for later use

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
            data_root=paths.RAW_DATA_DIR,
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
    except Exception as e:
        # Safe to continue: processed_data.parquet is for AI Lab analysis
        # Not required for backtest results
        logger.warning(f"Failed to save processed data parquet: {e}")
        processed_data_path = None

    # Strategy can be embedded or referenced via a separate YAML/JSON file
    strat_cfg = cfg_raw.get("strategy")
    if not strat_cfg:
        # Try loading from strategy_path if provided (extracted earlier before validation)
        if strategy_path:
            strat_cfg = _load_config(Path(strategy_path))
        else:
            raise ValueError(
                "No strategy provided. Specify 'strategy_path' in config "
                "or embed 'strategy' definition."
            )

    if isinstance(strat_cfg, dict) and "file_path" in strat_cfg:
        # Resolve file_path relative to the main config file
        p = Path(cfg_path.parent, strat_cfg["file_path"])
        strat_cfg = _load_config(p)

    # Apply strategy_params from config (used for parameter sweeps)
    # This allows the config to override strategy defaults
    if isinstance(strategy_params, dict):
        base_params = strat_cfg.get("parameters") or {}
        if isinstance(base_params, dict):
            base_params.update({k: v for k, v in strategy_params.items()})
            strat_cfg["parameters"] = base_params

    # Apply optional per-run overrides for strategy tunables
    if isinstance(strategy_overrides, dict):
        # 1) Parameter-level overrides (e.g., slope_filter)
        param_over = strategy_overrides.get("parameters") or {}
        if isinstance(param_over, dict):
            base_params = strat_cfg.get("parameters") or {}
            if isinstance(base_params, dict):
                base_params.update({k: v for k, v in param_over.items()})
                strat_cfg["parameters"] = base_params
        # 2) Feature-level overrides (existing behavior)
        feat_over = strategy_overrides.get("features") or {}
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

    # Get feature-enriched dataframe for REM (includes ATR, etc.)
    # This allows REM to access strategy-calculated features like ATR
    # Ensure it's aligned with the (possibly sliced) input df
    feature_enriched_df = strat._feature_df if strat._feature_df is not None else df
    if feature_enriched_df is not None:
        # Defensive checks: feature_df must match input df's length and index type
        if len(feature_enriched_df) != len(df) or not isinstance(
            feature_enriched_df.index, type(df.index)
        ):
            # Fall back to raw df if mismatched (can happen in tests with mocks)
            feature_enriched_df = df

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
    except Exception as e:  # pragma: no cover
        # Safe to continue: signals.parquet is for AI Lab post-analysis
        # Not required for backtest results
        logger.warning(
            f"Failed to save signals.parquet for AI Lab: {e}"
        )  # pragma: no cover
        signals_path = None  # pragma: no cover

    # Persist prices and features for charts before finalize_run
    try:
        save_prices_csv(run_path / "prices.csv", df)
    except Exception as e:  # pragma: no cover
        # Safe to continue: prices.csv is only for interactive charts
        # brief.json contains all data needed for analysis
        logger.warning(f"Failed to save prices.csv: {e}")  # pragma: no cover
    try:
        fdf = getattr(strat, "_feature_df", None)
        if fdf is not None:
            save_features_for_chart(run_path, fdf, strat.features)
    except Exception as e:  # pragma: no cover
        # Safe to continue: features.json is for charts/debugging only
        # Not required for backtest analysis
        logger.warning(f"Failed to save features: {e}")  # pragma: no cover

    # REM can be embedded or referenced via a separate file
    rem_cfg: dict[str, Any] | None = cfg_raw.get("rem_config")
    # Pass complete instrument definition with all metadata (asset_class, etc.)
    instrument_dict = instrument_def.model_dump() if instrument_def else None
    # Pass dict directly - RiskExitManager will validate new-format configs
    # and allow legacy configs to bypass validation
    rem = RiskExitManager(config=rem_cfg, instrument=instrument_dict)

    # RMM optional for legacy configs; if present, build per-bar context
    rmm_context: dict[datetime, dict[str, Any]] | None = None
    rmm_cfg: dict[str, Any] | None = cfg_raw.get("rmm_config")
    rmm_spans_path: Path | None = None
    if isinstance(rmm_cfg, dict) and rmm_cfg:
        # Validate and create the RMM engine using the Pydantic model
        rmm_config = RMMConfig(**rmm_cfg)
        rmm_engine = RMMEngine(config=rmm_config)

        regime_timeframe = rmm_config.timeframe or "1D"
        classify_regime = getattr(rmm_engine, "classify_regime", None)
        if callable(classify_regime):
            regimes = classify_regime(df, timeframe=regime_timeframe)
        else:
            # This path is for legacy compatibility, can be removed later
            classify_daily = getattr(rmm_engine, "classify_daily", None)
            if not callable(classify_daily):
                raise SystemExit(
                    "RMM engine must implement classify_regime or classify_daily"
                )
            regimes = classify_daily(df)

        rmm_policy = rmm_config.policy.model_dump() if rmm_config.policy else {}
        per_bar = rmm_engine.project_to_index(
            regimes, cast(pd.DatetimeIndex, df.index), policy=rmm_policy
        )
        # Extract regime feature names from config
        feature_names = (
            [f.name for f in rmm_config.features if f.name] if rmm_config.features else []
        )

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
        except Exception as e:  # pragma: no cover
            # Safe to continue: rmm_spans.json is for chart shading only
            # Not required for backtest analysis
            logger.warning(
                f"Failed to save RMM spans for chart: {e}"
            )  # pragma: no cover
            rmm_spans_path = None  # pragma: no cover

    # Output toggles; default to no exposure unless explicitly requested
    ret_exp = bool(cfg_raw.get("return_exposure", False))
    ret_skips = bool(cfg_raw.get("return_skips", True))

    res = run_backtest(
        market_data=feature_enriched_df,
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

    # Optional walk-forward analysis (bar-based)
    wf_cfg = cfg_raw.get("walk_forward") or {}
    wf_results = None

    if isinstance(wf_cfg, dict) and wf_cfg.get("enabled"):
        train_bars = int(wf_cfg.get("train_bars", 0))
        test_bars = int(wf_cfg.get("test_bars", 0))
        step_bars = int(wf_cfg.get("step_bars", 0))

        if train_bars > 0 and test_bars > 0 and step_bars > 0:
            # If parameter_search grid is provided, do walk-forward OPTIMIZATION
            if isinstance(ps_cfg, dict) and ps_cfg.get("grid"):
                grid_cfg = ps_cfg.get("grid")
                grid_typed = cast(dict[str, list[Any]], grid_cfg)
                wf_results = walk_forward_optimize_and_test(
                    df,
                    cfg_raw,
                    strat_cfg,
                    window=train_bars,
                    step=step_bars,
                    grid=grid_typed,
                    seed=ps_cfg.get("seed"),
                    objective=str(ps_cfg.get("objective", "total_pnl")),
                    dd_penalty=ps_cfg.get("dd_penalty"),
                    vol_penalty=ps_cfg.get("vol_penalty"),
                    data_handler=data_handler,
                )

                # NEW: Add per-candidate WFE summaries
                # If both parameter_search and walk_forward are enabled,
                # run WFE analysis for top N candidates from parameter sweep
                if ps_results and wf_cfg.get("per_candidate_wfe", True):
                    from trading_platform.core.sweeps import (
                        walk_forward_analysis,
                    )

                    top_n = int(wf_cfg.get("per_candidate_top_n", 5))
                    top_candidates = ps_results.get("results", [])[:top_n]

                    per_candidate_wfe: list[dict[str, Any]] = []
                    for cand in top_candidates:
                        params = cand.get("params", {})
                        # Create strategy config with this candidate's params
                        cand_strat_cfg = deepcopy(strat_cfg)
                        cand_params = dict(cand_strat_cfg.get("parameters") or {})
                        cand_params.update(params)
                        cand_strat_cfg["parameters"] = cand_params

                        # Run WFE for this candidate
                        wfe = walk_forward_analysis(
                            df,
                            cfg_raw,
                            cand_strat_cfg,
                            train_bars=train_bars,
                            test_bars=test_bars,
                            step_bars=step_bars,
                            data_handler=data_handler,
                        )
                        per_candidate_wfe.append(
                            {
                                "params": params,
                                "full_dataset_score": cand.get("score", 0.0),
                                "wfe": wfe,
                            }
                        )

                    # Add to parameter_search results
                    ps_results["per_candidate_wfe"] = per_candidate_wfe
            else:
                # Otherwise, do walk-forward ANALYSIS (bar-based, no re-optimization)
                from trading_platform.core.sweeps import walk_forward_analysis

                wf_results = walk_forward_analysis(
                    df,
                    cfg_raw,
                    strat_cfg,
                    train_bars=train_bars,
                    test_bars=test_bars,
                    step_bars=step_bars,
                    data_handler=data_handler,
                )
        else:
            logger.warning(
                "Walk-forward enabled but missing required parameters. "
                "Provide 'train_bars', 'test_bars', and 'step_bars' (all > 0)."
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

    # Generate equity curve chart
    try:
        save_equity_chart_from_brief(run_path)
    except Exception as e:  # pragma: no cover
        # Safe to continue: equity chart is optional visualization
        logger.warning(f"Failed to generate equity chart: {e}")

    print(f"Run created at: {run_path}")
    print(f"- Brief: {run_path / 'brief.json'}")
    print(f"- Report: {run_path / 'report.html'}")
    print(f"- Trades: {run_path / 'trades.csv'}")
    print(f"- Chart: {run_path / 'chart.html'}")
    print(f"- Equity: {run_path / 'equity_chart.html'}")
    return 0


def cmd_run_backtest(args: argparse.Namespace) -> int:
    if getattr(args, "clear_cache", False):
        print("Clearing Numba cache as requested...")
        clear_numba_cache()

    try:
        return _run_backtest_logic(args)
    except RuntimeError as e:
        if "numba" in str(e).lower() and "cache" in str(e).lower():
            print(
                "Numba cache error detected. "
                "Automatically retrying once with a cleared cache."
            )
            clear_numba_cache()
            return _run_backtest_logic(args)
        else:
            raise


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


def cmd_ai_curate_data(args: argparse.Namespace) -> int:
    """Curate ML training data from backtest results."""
    run_curation_pipeline(
        source_dir=Path(args.source_dir), output_file=Path(args.output_file)
    )
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


def cmd_clear_cache(args: argparse.Namespace) -> int:
    """Clear Numba cache directories."""
    print("Clearing Numba cache...")
    clear_numba_cache()
    print("Numba cache cleared successfully.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="tp", description="Trading Platform CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("run-backtest", help="Run backtest and write artifacts")
    pb.add_argument("--config", help="Path to JSON/YAML RunConfig")
    pb.add_argument("--user", default="cli_user", help="User id for run path")
    pb.add_argument("--demo", action="store_true", help="Use demo backtest")
    pb.add_argument(
        "--output-dir",
        help="Custom root directory for run artifacts (must be within workspace)",
    )
    pb.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear Numba cache before running the backtest.",
    )
    pb.set_defaults(func=cmd_run_backtest)

    pl = sub.add_parser("run-live", help="Run live adapter/controller")
    pl.add_argument("--config", help="Path to JSON/YAML RunConfig")
    pl.add_argument("--dry-run", action="store_true", help="No-op live run")
    pl.set_defaults(func=cmd_run_live)

    p_clear = sub.add_parser("clear-cache", help="Clear Numba cache")
    p_clear.set_defaults(func=cmd_clear_cache)

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

    pcd = sub.add_parser(
        "ai-curate-data", help="Curate ML training data from backtest results"
    )
    pcd.add_argument(
        "--source-dir", required=True, help="Directory containing brief.json files"
    )
    pcd.add_argument("--output-file", required=True, help="Output parquet file path")
    pcd.set_defaults(func=cmd_ai_curate_data)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
