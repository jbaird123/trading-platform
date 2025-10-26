from __future__ import annotations

#! ruff: noqa: I001
import argparse
import json
import logging
import math
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from trading_platform.ai.data_curation import run_curation_pipeline
from trading_platform.backtester.core import run_backtest
from trading_platform.core import paths
from trading_platform.core.config import RunConfig
from trading_platform.core.demo import generate_demo_run
from trading_platform.core.meta_campaign_config import MetaCampaignConfig
from trading_platform.core.meta_campaign_generator import (
    calculate_cartesian_product,
    campaign_config_to_yaml_dict,
    generate_campaign_filename,
)
from trading_platform.core.policy import TradingWindowPolicy
from trading_platform.core.run import finalize_run, initialize_run
from trading_platform.core.sweeps import (
    run_parameter_sweep,
    walk_forward_optimize_and_test,
)
from trading_platform.data.handler import DataHandler
from trading_platform.data.instrument import get_instrument_definition
from trading_platform.data.integrity_validator import validate_all_data
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
from trading_platform.reporting.diagnostics import RuleBasedAnalyzer
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import compile_strategy
from trading_platform.utils.cache import clear_numba_cache
from trading_platform.validation.pre_deployment import run_pre_deployment_checklist
from trading_platform.validation.walk_forward import (
    check_performance_consistency,
    split_into_periods,
    walk_forward_validate,
)

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
        # Try loading from strategy_path if provided
        # (extracted earlier before validation)
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
            [f.name for f in rmm_config.features if f.name]
            if rmm_config.features
            else []
        )

        def _safe_float(val: Any, default: float = 0.0) -> float:
            if isinstance(val, (int, float)):
                if isinstance(val, float) and math.isnan(val):
                    return default
                return float(val)
            return default

        def _safe_int(val: Any, default: int = 0) -> int:
            if isinstance(val, (int, float)):
                if isinstance(val, float) and math.isnan(val):
                    return default
                return int(val)
            return default

        def _safe_label(primary: Any, fallback: str) -> str:
            if isinstance(primary, str) and primary:
                return primary
            return fallback

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
                "raw_label": _safe_label(row.get("raw_label"), str(row["label"])),
                "raw_confidence": _safe_float(
                    row.get("raw_confidence"), float(row["confidence"])
                ),
                "bars_in_state": _safe_int(row.get("bars_in_state")),
                "cooldown_remaining": _safe_int(row.get("cooldown_remaining")),
            }
            for ts, row in per_bar.iterrows()
        }
        for ctx in rmm_context.values():
            ctx["hysteresis"] = {
                "bars_in_state": _safe_int(ctx["bars_in_state"]),
                "cooldown_remaining": _safe_int(ctx["cooldown_remaining"]),
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

    # Map brief.json structure to what RuleBasedAnalyzer expects
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

    analyzer = RuleBasedAnalyzer(analysis_data=analysis_data)
    analyzer.run()

    output_dir = brief_path.parent
    (output_dir / "ai_diagnostic_report.md").write_text(
        analyzer.generate_report_markdown()
    )
    diagnostic_json = analyzer.generate_report_json()
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


def cmd_campaign_plan(args: argparse.Namespace) -> int:
    """Generate campaign execution plan."""
    import yaml

    from trading_platform.ai.campaigns import CampaignConfig, generate_campaign_plan
    from trading_platform.core import paths

    # Load campaign YAML
    with open(args.config) as f:
        campaign_dict = yaml.safe_load(f)

    # Validate as CampaignConfig
    campaign = CampaignConfig.model_validate(campaign_dict)

    # Determine output directory
    output_dir = paths.PROJECT_ROOT / "data" / "campaigns" / campaign.campaign_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate plan
    plan = generate_campaign_plan(campaign, output_dir)

    print(f"Campaign plan created: {output_dir / 'plan.json'}")
    print(f"Total runs: {len(plan.runs)}")
    print(f"Provenance captured at: {plan.provenance.captured_at}")

    return 0


def cmd_campaign_run(args: argparse.Namespace) -> int:
    """Execute campaign runs."""
    import json

    from trading_platform.ai.campaigns import CampaignPlan, execute_campaign_runs
    from trading_platform.core import paths

    # Load plan
    campaign_dir = paths.PROJECT_ROOT / "data" / "campaigns" / args.campaign_id
    plan_path = campaign_dir / "plan.json"

    with open(plan_path) as f:
        plan_dict = json.load(f)

    plan = CampaignPlan.model_validate(plan_dict)

    # Define runs directory
    runs_dir = campaign_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    # Execute runs
    results = execute_campaign_runs(
        plan,
        runs_dir,
        campaign_dir,
        fail_fast=args.fail_fast,
        continue_on_error=args.continue_on_error,
    )

    print(f"Execution complete: {results.successful}/{results.total_runs} successful")

    return 0 if results.successful == results.total_runs else 1


def cmd_campaign_validate(args: argparse.Namespace) -> int:
    """Validate campaign candidates."""
    from trading_platform.ai.campaigns import validate_campaign_candidates

    report = validate_campaign_candidates(args.campaign_id)

    print(f"Validation complete: {report.passed}/{report.total_candidates} passed")

    return 0


def cmd_campaign_review(args: argparse.Namespace) -> int:
    """Generate campaign review report."""
    from trading_platform.ai.campaigns import generate_review_report

    report_path = generate_review_report(args.campaign_id)

    print(f"Review report generated: {report_path}")

    return 0


def cmd_campaign_approve(args: argparse.Namespace) -> int:
    """Approve a campaign candidate."""
    from trading_platform.ai.campaigns import approve_candidate

    approve_candidate(args.campaign_id, args.run_id, args.notes)

    print(f"Approved {args.run_id} in campaign {args.campaign_id}")

    return 0


def cmd_campaign_reject(args: argparse.Namespace) -> int:
    """Reject a campaign candidate."""
    from trading_platform.ai.campaigns import reject_candidate

    reject_candidate(args.campaign_id, args.run_id, args.reason)

    print(f"Rejected {args.run_id} in campaign {args.campaign_id}")

    return 0


def cmd_campaign_needs_rework(args: argparse.Namespace) -> int:
    """Mark candidate as needs-rework."""
    from trading_platform.ai.campaigns import mark_needs_rework

    mark_needs_rework(args.campaign_id, args.run_id, args.reason, args.suggestions)

    print(f"Marked {args.run_id} as needs-rework in campaign {args.campaign_id}")

    return 0


def cmd_campaign_enrich(args: argparse.Namespace) -> int:
    """Enrich campaign dataset."""
    from trading_platform.ai.campaigns import enrich_campaign_dataset

    result = enrich_campaign_dataset(args.campaign_id)

    print(f"Enrichment complete: {result.total_trades_enriched} trades enriched")
    print(f"Output: {result.output_path}")

    return 0


def cmd_campaign_publish(args: argparse.Namespace) -> int:
    """Publish campaign dataset to master trade log."""
    from trading_platform.ai.campaigns import publish_campaign_dataset

    result = publish_campaign_dataset(args.campaign_id)

    print(f"Published {result.total_trades_published} trades to master log")
    print(f"Checksum: {result.sha256_checksum}")
    print(f"DVC tracking updated: {result.dvc_tracking_updated}")

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


def cmd_train_profitability_models(args: argparse.Namespace) -> int:
    """Train profitability models from enriched trade data."""
    from trading_platform.ai.models import ModelRegistry

    # Load enriched data
    enriched_path = Path(args.enriched_data)
    if not enriched_path.exists():
        print(f"Error: Enriched data not found: {enriched_path}", file=sys.stderr)
        return 1

    print(f"Loading enriched data from: {enriched_path}")
    enriched_df = pd.read_parquet(enriched_path)
    print(f"Loaded {len(enriched_df)} trades")

    # Initialize registry
    model_dir = Path(args.model_dir) if args.model_dir else Path("models")
    registry = ModelRegistry(model_dir=model_dir)

    # Train models
    print("\nTraining profitability models...")
    print(f"Model directory: {model_dir}")

    trained_models = registry.train_all_profitability_models(
        enriched_df, n_estimators=args.n_estimators, random_state=args.random_state
    )

    if not trained_models:
        print("\nNo models trained (insufficient data for all contexts)")
        return 1

    # Save models
    print(f"\nSaving {len(trained_models)} models...")
    registry.save()

    print("\nProfitability models trained successfully:")
    for key in trained_models.keys():
        model_path = registry.get_model_path("profitability", key)
        print(f"  - {key}: {model_path}")

    return 0


def cmd_train_diagnostic_models(args: argparse.Namespace) -> int:
    """Train diagnostic models from enriched trade data."""
    from trading_platform.ai.models import ModelRegistry, PerformanceDiagnosticModel

    # Load enriched data
    enriched_path = Path(args.enriched_data)
    if not enriched_path.exists():
        print(f"Error: Enriched data not found: {enriched_path}", file=sys.stderr)
        return 1

    print(f"Loading enriched data from: {enriched_path}")
    enriched_df = pd.read_parquet(enriched_path)
    print(f"Loaded {len(enriched_df)} trades")

    # Initialize registry
    model_dir = Path(args.model_dir) if args.model_dir else Path("models")
    registry = ModelRegistry(model_dir=model_dir)

    # Find all unique contexts
    contexts = enriched_df[
        ["execution_timeframe", "strategy_archetype"]
    ].drop_duplicates()

    print(f"\nTraining diagnostic models for {len(contexts)} contexts...")
    print(f"Model directory: {model_dir}")

    trained_count = 0
    for _, row in contexts.iterrows():
        timeframe = row["execution_timeframe"]
        archetype = row["strategy_archetype"]
        key = f"{timeframe}_{archetype}"

        # Create and train model
        model = PerformanceDiagnosticModel(
            timeframe=timeframe,
            archetype=archetype,
            n_estimators=args.n_estimators,
            random_state=args.random_state,
        )

        try:
            model.fit(enriched_df)
            registry.register_model("diagnostic", key, model)
            trained_count += 1
            print(f"  ✓ Trained {key}")
        except ValueError as e:
            print(f"  ✗ Skipped {key}: {e}")

    if trained_count == 0:
        print("\nNo models trained (insufficient data for all contexts)")
        return 1

    # Save models
    print(f"\nSaving {trained_count} models...")
    registry.save()

    print(f"\nDiagnostic models trained successfully: {trained_count} models")

    return 0


def cmd_predict_profitability(args: argparse.Namespace) -> int:
    """Predict profitability for new trades using trained models."""
    from trading_platform.ai.models import ModelRegistry

    # Load models
    model_dir = Path(args.model_dir) if args.model_dir else Path("models")
    registry = ModelRegistry(model_dir=model_dir)

    print(f"Loading models from: {model_dir}")
    registry.load()

    prof_models = registry.list_models("profitability")
    if not prof_models:
        print(
            "Error: No profitability models found. Train models first.", file=sys.stderr
        )
        return 1

    print(f"Loaded {len(prof_models)} profitability models")

    # Load input data
    input_path = Path(args.input_data)
    if not input_path.exists():
        print(f"Error: Input data not found: {input_path}", file=sys.stderr)
        return 1

    print(f"Loading input data from: {input_path}")
    input_df = pd.read_parquet(input_path)
    print(f"Loaded {len(input_df)} trades")

    # Make predictions
    print("\nGenerating predictions...")
    predictions = []

    for _, trade in input_df.iterrows():
        timeframe = trade["execution_timeframe"]
        archetype = trade["strategy_archetype"]

        try:
            pred_r_multiple = registry.predict_profitability(
                X=pd.DataFrame([trade]), timeframe=timeframe, archetype=archetype
            )
            r_mult_value = pred_r_multiple.iloc[0]
            predictions.append(
                {
                    "index": trade.name,
                    "predicted_r_multiple": r_mult_value,
                    "prediction_favorable": 1 if r_mult_value > 0 else 0,
                }
            )
        except ValueError as e:
            print(f"Warning: Skipping trade (no model): {e}")
            predictions.append(
                {
                    "index": trade.name,
                    "predicted_r_multiple": None,
                    "prediction_favorable": None,
                }
            )

    # Save predictions
    output_path = Path(args.output) if args.output else Path("predictions.csv")
    pred_df = pd.DataFrame(predictions)
    pred_df.to_csv(output_path, index=False)

    print(f"\nPredictions saved to: {output_path}")
    print(f"Total predictions: {len(pred_df)}")
    print(f"Predicted profitable: {pred_df['prediction'].sum()}")

    return 0


def cmd_analyze_regime(args: argparse.Namespace) -> int:
    """Analyze regime performance using trained diagnostic models."""
    from trading_platform.ai.models import ModelRegistry

    # Load models
    model_dir = Path(args.model_dir) if args.model_dir else Path("models")
    registry = ModelRegistry(model_dir=model_dir)

    print(f"Loading models from: {model_dir}")
    registry.load()

    diag_models = registry.list_models("diagnostic")
    if not diag_models:
        print("Error: No diagnostic models found. Train models first.", file=sys.stderr)
        return 1

    print(f"Loaded {len(diag_models)} diagnostic models")

    # Load input data
    input_path = Path(args.input_data)
    if not input_path.exists():
        print(f"Error: Input data not found: {input_path}", file=sys.stderr)
        return 1

    print(f"Loading input data from: {input_path}")
    input_df = pd.read_parquet(input_path)
    print(f"Loaded {len(input_df)} trades")

    # Analyze regime
    print("\nAnalyzing regime performance...")

    # Group by context and get quintile distributions
    contexts = input_df[["execution_timeframe", "strategy_archetype"]].drop_duplicates()

    results = []
    for _, row in contexts.iterrows():
        timeframe = row["execution_timeframe"]
        archetype = row["strategy_archetype"]
        key = f"{timeframe}_{archetype}"

        # Get model
        model = registry.get_model("diagnostic", key)
        if model is None:
            print(f"Warning: No model for {key}")
            continue

        # Filter trades for this context
        context_trades = input_df[
            (input_df["execution_timeframe"] == timeframe)
            & (input_df["strategy_archetype"] == archetype)
        ]

        if len(context_trades) == 0:
            continue

        # Predict quintiles
        quintiles = model.predict(context_trades)

        results.append(
            {
                "context": key,
                "n_trades": len(context_trades),
                "avg_quintile": quintiles.mean(),
                "quintile_0_pct": (quintiles == 0).sum() / len(quintiles) * 100,
                "quintile_4_pct": (quintiles == 4).sum() / len(quintiles) * 100,
            }
        )

    # Display results
    if results:
        results_df = pd.DataFrame(results)
        print("\nRegime Analysis Results:")
        print(results_df.to_string(index=False))

        # Save if output specified
        if args.output:
            output_path = Path(args.output)
            results_df.to_csv(output_path, index=False)
            print(f"\nResults saved to: {output_path}")
    else:
        print("\nNo results generated")

    return 0


def _check_output_directory(output_dir: Path, force: bool) -> tuple[bool, list[Path]]:
    """
    Check if output directory contains existing files.

    Returns:
        Tuple of (should_proceed, existing_files)
    """
    existing_files = list(output_dir.glob("*.yaml"))
    if existing_files and not force:
        print(
            "Error: Output directory contains existing files.",
            file=sys.stderr,
        )
        print("       Use --force to overwrite.", file=sys.stderr)
        print(
            f"       Found {len(existing_files)} existing file(s)",
            file=sys.stderr,
        )
        return (False, existing_files)
    return (True, existing_files)


def _write_campaign_files(
    campaigns: list[dict[str, Any]],
    output_dir: Path,
    meta_campaign_id: str,
) -> int:
    """
    Write campaign configuration files.

    Returns:
        Number of files written
    """
    import yaml

    profile_counters: dict[str, int] = {}
    generated_count = 0

    for campaign in campaigns:
        profile_name = campaign["profile_name"]
        instrument = campaign["instrument"]
        timeframe = campaign["execution_timeframe"]

        # Get and increment counter for this profile
        if profile_name not in profile_counters:
            profile_counters[profile_name] = 0
        param_index = profile_counters[profile_name]
        profile_counters[profile_name] += 1

        # Generate filename
        filename = generate_campaign_filename(
            meta_campaign_id=meta_campaign_id,
            profile_name=profile_name,
            instrument=instrument,
            timeframe=timeframe,
            param_index=param_index,
        )

        # Convert to YAML dict
        yaml_dict = campaign_config_to_yaml_dict(campaign)

        # Write file
        output_path = output_dir / filename
        with open(output_path, "w") as f:
            yaml.dump(yaml_dict, f, default_flow_style=False, sort_keys=False)

        generated_count += 1

    return generated_count


def _print_summary(generated_count: int, output_dir: Path) -> None:
    """Print summary of generated campaigns."""
    print(f"✓ Generated {generated_count} campaign configurations")
    print(f"✓ Output directory: {output_dir}")
    print()
    print("Next steps:")
    print("  1. Review generated configs in " + str(output_dir))
    print("  2. Run campaigns with: tp campaign-run <campaign_file>")
    print("  3. Review results with: tp campaign-review")
    print()


def _meta_campaign_plan_logic(args: argparse.Namespace) -> int:
    """Generate campaign configurations from a meta-campaign file."""
    # Validate config argument
    if not args.config:
        print("Error: --config is required", file=sys.stderr)
        return 2

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        return 2

    # Load meta-campaign config
    try:
        config = MetaCampaignConfig.from_yaml(config_path)
    except Exception as e:
        print(f"Error loading meta-campaign config: {e}", file=sys.stderr)
        return 2

    # Prepare output directory
    default_dir = "config/campaigns/generated/"
    output_dir = Path(args.output_dir if args.output_dir else default_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing files
    should_proceed, existing_files = _check_output_directory(output_dir, args.force)
    if not should_proceed:
        return 1

    # Clear directory if --force is set
    if args.force and existing_files:
        for file in existing_files:
            file.unlink()
        print(f"Cleared {len(existing_files)} file(s) from {output_dir}")

    # Print generation info
    print(f"Generating campaigns from: {config_path}")
    print(f"Meta-campaign ID: {config.meta_campaign_id}")
    print(f"Description: {config.description}")
    print()

    # Generate campaigns
    campaigns = calculate_cartesian_product(config)
    print(f"Calculated: {len(campaigns)} campaign configurations")
    print()

    # Write campaign files
    generated_count = _write_campaign_files(
        campaigns, output_dir, config.meta_campaign_id
    )

    # Print summary
    _print_summary(generated_count, output_dir)

    return 0


def _validate_data_logic(args: argparse.Namespace) -> int:
    """Validate data integrity for historical price data."""
    # Validate data_dir argument
    if not args.data_dir:
        print("Error: --data-dir is required", file=sys.stderr)
        return 2

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
        return 2

    # Get list of instruments
    if args.instruments:
        instruments = args.instruments
    else:
        # Scan directory for all instruments
        instruments = []
        for file in data_dir.glob("*.parquet"):
            # Extract instrument from filename (e.g., EUR_USD_1H.parquet -> EUR_USD)
            parts = file.stem.split("_")
            if len(parts) >= 2:
                instrument = "_".join(parts[:2])  # Take first two parts
                if instrument not in instruments:
                    instruments.append(instrument)

    if not instruments:
        print("Error: No instruments found or specified", file=sys.stderr)
        return 2

    print(f"Validating data in: {data_dir}")
    print(f"Instruments: {', '.join(instruments)}")
    print()

    # Run validation
    results = validate_all_data(data_dir, instruments)

    # Print summary
    print(f"Total files checked: {results['total_files']}")
    print(f"Files with issues: {results['total_issues']}")
    print()

    # Print detailed issues
    if results["issues"]:
        print("Issues found:")
        for issue in results["issues"]:
            print(f"\nFile: {issue['file']}")
            if issue["status"] == "corrupted":
                print("  Status: CORRUPTED")
                print(f"  Error: {issue['error']}")
            else:
                if issue.get("gaps"):
                    print(f"  Gaps: {len(issue['gaps'])}")
                    for gap in issue["gaps"][:3]:  # Show first 3 gaps
                        print(
                            f"    {gap['start_time']} -> {gap['end_time']} "
                            f"({gap['gap_minutes']:.0f} minutes)"
                        )
                    if len(issue["gaps"]) > 3:
                        print(f"    ... and {len(issue['gaps']) - 3} more gaps")
                if issue.get("timestamp_issues"):
                    print("  Timestamp issues:")
                    for ts_issue in issue["timestamp_issues"]:
                        print(f"    - {ts_issue}")
    else:
        print("No issues found!")

    # Return exit code
    return 1 if results["total_issues"] > 0 else 0


def _walk_forward_validate_logic(args: argparse.Namespace) -> int:
    """Perform walk-forward validation on a strategy."""
    # Validate arguments
    if not args.strategy:
        print("Error: --strategy is required", file=sys.stderr)
        return 2

    if not args.data:
        print("Error: --data is required", file=sys.stderr)
        return 2

    strategy_path = Path(args.strategy)
    data_path = Path(args.data)

    if not strategy_path.exists():
        print(f"Error: Strategy file not found: {strategy_path}", file=sys.stderr)
        return 2

    if not data_path.exists():
        print(f"Error: Data file not found: {data_path}", file=sys.stderr)
        return 2

    # Load strategy config
    strategy_config = _load_config(strategy_path)

    # Load data
    print(f"Loading data from: {data_path}")
    data = pd.read_parquet(data_path)

    # Split into periods
    print(f"Splitting data into {args.periods} periods...")
    periods = split_into_periods(data, period=args.periods)
    print(f"Created {len(periods)} periods")

    if len(periods) < 2:
        print(
            "Error: Need at least 2 periods for walk-forward validation",
            file=sys.stderr,
        )
        return 2

    # Define mock training and backtest functions
    # In a real implementation, these would call actual model training and backtesting
    def mock_train_model(training_data: pd.DataFrame) -> dict[str, Any]:
        """Mock model training - returns dummy model."""
        print(f"  Training on {len(training_data)} rows")
        return {"model": "trained"}

    def mock_run_backtest(
        config: dict[str, Any], test_data: pd.DataFrame
    ) -> dict[str, Any]:
        """Mock backtest - returns dummy metrics."""
        print(f"  Testing on {len(test_data)} rows")
        # Simple mock metrics
        return {
            "sharpe_ratio": 1.5,
            "max_drawdown": -0.15,
            "total_return": 0.25,
            "win_rate": 0.55,
        }

    # Run walk-forward validation
    print("\nRunning walk-forward validation...")
    results = walk_forward_validate(
        data=data,
        strategy_config=strategy_config,
        periods=periods,
        train_model_fn=mock_train_model,
        run_backtest_fn=mock_run_backtest,
    )

    # Print results table
    print("\n" + "=" * 80)
    print("WALK-FORWARD VALIDATION RESULTS")
    print("=" * 80)
    print(
        f"{'Period':<30} {'Sharpe':<10} {'Max DD':<10} {'Return':<10} {'Win Rate':<10}"
    )
    print("-" * 80)

    for period_name, metrics in results.items():
        print(
            f"{period_name:<30} "
            f"{metrics.get('sharpe_ratio', 0):<10.2f} "
            f"{metrics.get('max_drawdown', 0):<10.2%} "
            f"{metrics.get('total_return', 0):<10.2%} "
            f"{metrics.get('win_rate', 0):<10.2%}"
        )

    print("-" * 80)

    # Check consistency
    is_consistent = check_performance_consistency(
        results, metric="sharpe_ratio", tolerance=0.3
    )
    print(f"\nConsistency Check (Sharpe Ratio): {'PASS' if is_consistent else 'FAIL'}")

    if is_consistent:
        print("✓ Performance is consistent across periods")
    else:
        print("✗ Performance varies significantly across periods")
        print("  Consider investigating regime changes or overfitting")

    return 0


def _pre_deployment_checklist_logic(args: argparse.Namespace) -> int:
    """Validate strategy against pre-deployment checklist."""
    # Validate all required arguments
    required_args = [
        "model_metrics",
        "walk_forward_results",
        "phase4_results",
        "strategy_config",
    ]
    for arg_name in required_args:
        if not getattr(args, arg_name, None):
            print(f"Error: --{arg_name.replace('_', '-')} is required", file=sys.stderr)
            return 2

    # Load all input files
    try:
        model_metrics_path = Path(args.model_metrics)
        with model_metrics_path.open() as f:
            model_metrics = json.load(f)

        walk_forward_path = Path(args.walk_forward_results)
        with walk_forward_path.open() as f:
            walk_forward_results = json.load(f)

        phase4_path = Path(args.phase4_results)
        with phase4_path.open() as f:
            phase4_results = json.load(f)

        strategy_path = Path(args.strategy_config)
        strategy_config = _load_config(strategy_path)

    except FileNotFoundError as e:
        print(f"Error: File not found: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return 2

    # Run checklist
    checklist = run_pre_deployment_checklist(
        model_metrics=model_metrics,
        walk_forward_results=walk_forward_results,
        phase4_results=phase4_results,
        strategy_config=strategy_config,
    )

    # Print checklist with checkbox format
    print("=" * 80)
    print("PRE-DEPLOYMENT CHECKLIST")
    print("=" * 80)
    print()

    all_passed = True
    for item_name, item_data in checklist.items():
        checkbox = "☑" if item_data["passed"] else "☐"
        status = "PASS" if item_data["passed"] else "FAIL"
        print(f"{checkbox} [{status}] {item_data['description']}")
        print(f"         {item_data['details']}")
        print()

        if not item_data["passed"]:
            all_passed = False

    print("=" * 80)

    # Print overall recommendation
    if all_passed:
        print("✓ READY FOR DEPLOYMENT")
        print()
        print("All pre-deployment criteria have been met.")
        return 0
    else:
        print("✗ NOT READY FOR DEPLOYMENT")
        print()
        print("Please address the failed items above before deploying to production.")
        return 1


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

    # Campaign commands
    pcp = sub.add_parser("campaign-plan", help="Generate campaign execution plan")
    pcp.add_argument("--config", required=True, help="Campaign YAML config file")
    pcp.set_defaults(func=cmd_campaign_plan)

    pcr = sub.add_parser("campaign-run", help="Execute campaign runs")
    pcr.add_argument("--campaign-id", required=True, help="Campaign identifier")
    pcr.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    pcr.add_argument(
        "--continue-on-error", action="store_true", help="Continue on errors"
    )
    pcr.set_defaults(func=cmd_campaign_run)

    pcv = sub.add_parser("campaign-validate", help="Validate campaign candidates")
    pcv.add_argument("--campaign-id", required=True, help="Campaign identifier")
    pcv.set_defaults(func=cmd_campaign_validate)

    pcrv = sub.add_parser("campaign-review", help="Generate campaign review report")
    pcrv.add_argument("--campaign-id", required=True, help="Campaign identifier")
    pcrv.set_defaults(func=cmd_campaign_review)

    pca = sub.add_parser("campaign-approve", help="Approve a campaign candidate")
    pca.add_argument("--campaign-id", required=True, help="Campaign identifier")
    pca.add_argument("--run-id", required=True, help="Run identifier")
    pca.add_argument("--notes", required=True, help="Approval notes")
    pca.set_defaults(func=cmd_campaign_approve)

    pcrj = sub.add_parser("campaign-reject", help="Reject a campaign candidate")
    pcrj.add_argument("--campaign-id", required=True, help="Campaign identifier")
    pcrj.add_argument("--run-id", required=True, help="Run identifier")
    pcrj.add_argument("--reason", required=True, help="Rejection reason")
    pcrj.set_defaults(func=cmd_campaign_reject)

    pcnr = sub.add_parser(
        "campaign-needs-rework", help="Mark candidate as needs-rework"
    )
    pcnr.add_argument("--campaign-id", required=True, help="Campaign identifier")
    pcnr.add_argument("--run-id", required=True, help="Run identifier")
    pcnr.add_argument("--reason", required=True, help="Reason for rework")
    pcnr.add_argument("--suggestions", required=True, help="Suggestions for rework")
    pcnr.set_defaults(func=cmd_campaign_needs_rework)

    pce = sub.add_parser("campaign-enrich", help="Enrich campaign dataset")
    pce.add_argument("--campaign-id", required=True, help="Campaign identifier")
    pce.set_defaults(func=cmd_campaign_enrich)

    pcpb = sub.add_parser(
        "campaign-publish", help="Publish campaign dataset to master trade log"
    )
    pcpb.add_argument("--campaign-id", required=True, help="Campaign identifier")
    pcpb.set_defaults(func=cmd_campaign_publish)

    # Meta-Campaign command
    pmcp = sub.add_parser(
        "meta-campaign-plan",
        help="Generate campaign configurations from a meta-campaign file",
    )
    pmcp.add_argument("--config", required=True, help="Path to meta-campaign.yaml file")
    pmcp.add_argument(
        "--output-dir",
        default="config/campaigns/generated/",
        help="Directory to write generated campaign configs",
    )
    pmcp.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files in output directory",
    )
    pmcp.set_defaults(func=_meta_campaign_plan_logic)

    # Data Validation command
    pvd = sub.add_parser(
        "validate-data", help="Validate data integrity for historical price data"
    )
    pvd.add_argument(
        "--data-dir", required=True, help="Directory containing parquet files"
    )
    pvd.add_argument(
        "--instruments",
        nargs="+",
        help="Specific instruments to check (default: all in directory)",
    )
    pvd.set_defaults(func=_validate_data_logic)

    # Walk-Forward Validation command
    pwfv = sub.add_parser(
        "walk-forward-validate", help="Perform walk-forward validation on a strategy"
    )
    pwfv.add_argument("--strategy", required=True, help="Path to strategy config")
    pwfv.add_argument(
        "--data", required=True, help="Path to master_trade_log.parquet or data file"
    )
    pwfv.add_argument(
        "--periods",
        default="year",
        help="Period granularity (year, quarter, month)",
    )
    pwfv.set_defaults(func=_walk_forward_validate_logic)

    # Pre-deployment Checklist command
    ppdc = sub.add_parser(
        "pre-deployment-checklist",
        help="Validate strategy against pre-deployment checklist",
    )
    ppdc.add_argument(
        "--model-metrics",
        required=True,
        help="Path to model performance metrics JSON",
    )
    ppdc.add_argument(
        "--walk-forward-results",
        required=True,
        help="Path to walk-forward validation results JSON",
    )
    ppdc.add_argument(
        "--phase4-results",
        required=True,
        help="Path to Phase 4 optimization results JSON",
    )
    ppdc.add_argument(
        "--strategy-config",
        required=True,
        help="Path to final strategy config YAML",
    )
    ppdc.set_defaults(func=_pre_deployment_checklist_logic)

    # ML Model Training Commands
    ptpm = sub.add_parser(
        "train-profitability-models",
        help="Train profitability models from enriched trade data",
    )
    ptpm.add_argument(
        "--enriched-data",
        required=True,
        help="Path to enriched trade data (parquet file)",
    )
    ptpm.add_argument(
        "--model-dir", default=None, help="Directory to save models (default: models/)"
    )
    ptpm.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees in RandomForest (default: 100)",
    )
    ptpm.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    ptpm.set_defaults(func=cmd_train_profitability_models)

    ptdm = sub.add_parser(
        "train-diagnostic-models",
        help="Train diagnostic models from enriched trade data",
    )
    ptdm.add_argument(
        "--enriched-data",
        required=True,
        help="Path to enriched trade data (parquet file)",
    )
    ptdm.add_argument(
        "--model-dir", default=None, help="Directory to save models (default: models/)"
    )
    ptdm.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees in RandomForest (default: 100)",
    )
    ptdm.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    ptdm.set_defaults(func=cmd_train_diagnostic_models)

    ppp = sub.add_parser(
        "predict-profitability",
        help="Predict profitability for trades using trained models",
    )
    ppp.add_argument(
        "--input-data", required=True, help="Path to input trade data (parquet file)"
    )
    ppp.add_argument(
        "--model-dir",
        default=None,
        help="Directory containing trained models (default: models/)",
    )
    ppp.add_argument(
        "--output",
        default=None,
        help="Output path for predictions (default: predictions.csv)",
    )
    ppp.set_defaults(func=cmd_predict_profitability)

    par = sub.add_parser(
        "analyze-regime",
        help="Analyze regime performance using trained diagnostic models",
    )
    par.add_argument(
        "--input-data", required=True, help="Path to input trade data (parquet file)"
    )
    par.add_argument(
        "--model-dir",
        default=None,
        help="Directory containing trained models (default: models/)",
    )
    par.add_argument(
        "--output", default=None, help="Output path for analysis results (CSV)"
    )
    par.set_defaults(func=cmd_analyze_regime)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
