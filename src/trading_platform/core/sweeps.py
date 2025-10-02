from __future__ import annotations

import random
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pandas as pd
from trading_platform.backtester.core import run_backtest
from trading_platform.core.config import RunConfig
from trading_platform.core.robustness import walk_forward_splits
from trading_platform.portfolio.trade import Trade
from trading_platform.regime_market_manager.engine import RMMEngine
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import compile_strategy


def _rmm_context(
    df: pd.DataFrame,
    cfg_raw: dict[str, Any],
    data_handler: Any | None = None,
) -> dict | None:
    rmm_cfg = cfg_raw.get("rmm_config") or {}
    rmm_path = cfg_raw.get("rmm_path")
    if rmm_path:
        import json

        import yaml

        txt = open(str(rmm_path)).read()
        rmm_cfg = (
            yaml.safe_load(txt)
            if str(rmm_path).endswith((".yaml", ".yml"))
            else json.loads(txt)
        )
    if not isinstance(rmm_cfg, dict) or not rmm_cfg:
        return None

    regime_timeframe = rmm_cfg.get("timeframe", "1D")

    # PERFORMANCE: Check cache first if DataHandler is available
    if data_handler is not None:
        cached_context = data_handler.get_rmm_context(rmm_cfg, regime_timeframe)
        if cached_context is not None:
            return cached_context

    # Not cached - compute regime classification
    eng = RMMEngine(config=rmm_cfg)

    # Use DataHandler for resampling if available (cached), otherwise fallback to direct resample
    if data_handler is not None:
        df_resampled = data_handler.get_data(timeframe=regime_timeframe)
        already_resampled = True
    else:
        # Fallback for legacy code paths without DataHandler
        df_resampled = df
        already_resampled = False

    regimes = eng.classify_regime(df_resampled, timeframe=regime_timeframe, already_resampled=already_resampled)
    pol = rmm_cfg.get("policy") or {}
    from typing import cast as _cast

    proj = eng.project_to_index(regimes, _cast(pd.DatetimeIndex, df.index), policy=pol)

    # Extract regime feature names from config
    feature_names = [
        f.get("name") for f in rmm_cfg.get("features", []) if f.get("name")
    ]

    import math

    def _round_feature(name: str, val: Any) -> float | None:
        """Round feature value based on its type, returning None for NaN/inf."""
        if val is None:
            return None
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return None

            # Determine precision based on feature name/type
            name_lower = name.lower()

            # ADX, ATR: 2 decimals (percentage-like)
            if any(x in name_lower for x in ["adx", "atr"]):
                return round(f, 2)
            # RSI, Stochastic, CCI: 2 decimals (bounded indicators)
            elif any(x in name_lower for x in ["rsi", "stoch", "cci"]):
                return round(f, 2)
            # Volume: whole numbers
            elif "volume" in name_lower or "vol" in name_lower:
                return round(f, 0)
            # EMA, SMA, prices: 4 decimals (forex precision)
            elif any(
                x in name_lower
                for x in ["ema", "sma", "price", "close", "open", "high", "low"]
            ):
                return round(f, 4)
            # MACD, momentum: 4 decimals
            elif any(x in name_lower for x in ["macd", "mom", "roc"]):
                return round(f, 4)
            # Default: 4 decimals
            else:
                return round(f, 4)
        except (ValueError, TypeError):
            return None

    rmm_context = {
        ts: {
            "label": str(row["label"]),
            "confidence": float(row["confidence"]),
            "allowed_sides": list(row.get("allowed_sides") or []),
            "policy": pol,
            # Include regime feature values with appropriate rounding
            "features": {
                fname: _round_feature(fname, row.get(fname))
                for fname in feature_names
                if fname in row.index
            },
            "timeframe": regime_timeframe,
        }
        for ts, row in proj.iterrows()
    }

    # Cache the result if DataHandler is available
    if data_handler is not None:
        data_handler.set_rmm_context(rmm_cfg, regime_timeframe, rmm_context)

    return rmm_context


def run_parameter_sweep(
    df: pd.DataFrame,
    base_cfg: dict[str, Any],
    strategy_cfg: dict[str, Any],
    *,
    grid: dict[str, list[Any]] | None = None,
    random_space: dict[str, list[Any]] | None = None,
    n_samples: int | None = None,
    seed: int | None = None,
    objective: str = "total_pnl",
    dd_penalty: float | None = None,
    data_handler: Any | None = None,
    vol_penalty: float | None = None,
    debug_dir: str | Path | None = None,
) -> dict[str, Any]:
    # BUGFIX: Reload strategy from file to avoid mutations from baseline compile
    # If strategy_path is specified, reload it fresh
    if "strategy_path" in base_cfg:
        import json
        from pathlib import Path as PathLib

        import yaml

        strat_path = PathLib(str(base_cfg["strategy_path"]))
        txt = strat_path.read_text()
        strategy_cfg = (
            yaml.safe_load(txt)
            if str(strat_path).endswith((".yaml", ".yml"))
            else json.loads(txt)
        )
    if seed is not None:
        random.seed(seed)
    # Build candidates
    cands: list[dict[str, Any]] = []
    if grid:
        keys = list(grid.keys())
        lists = [grid[k] for k in keys]

        def _prod(prefix: dict[str, Any], rk: list[str], rl: list[list[Any]]):
            if not rk:
                cands.append(prefix.copy())
                return
            k = rk[0]
            for v in rl[0]:
                prefix[k] = v
                _prod(prefix, rk[1:], rl[1:])

        _prod({}, keys, lists)
    if random_space and n_samples:
        keys = list(random_space.keys())
        for _ in range(int(n_samples)):
            cands.append({k: random.choice(random_space[k]) for k in keys})

    cfg = RunConfig.model_validate(base_cfg)
    rmm_ctx = _rmm_context(df, base_cfg, data_handler)
    rem_cfg = base_cfg.get("rem_config") or {}
    rem_path = base_cfg.get("rem_path")
    if rem_path:
        import json

        import yaml

        txt = open(str(rem_path)).read()
        rem_cfg = (
            yaml.safe_load(txt)
            if str(rem_path).endswith((".yaml", ".yml"))
            else json.loads(txt)
        )
    rem = RiskExitManager(config=rem_cfg)

    results: list[dict[str, Any]] = []
    log_file: Path | None = None
    if debug_dir is not None:
        try:
            d = Path(str(debug_dir))
            d.mkdir(parents=True, exist_ok=True)
            log_file = d / "sweep_debug.log"
            with log_file.open("a") as f:
                f.write("# sweep start\n")
        except Exception:
            log_file = None
    for cand in cands:
        scfg = deepcopy(strategy_cfg)
        params = dict(scfg.get("parameters") or {})
        params.update(cand)
        scfg["parameters"] = params

        # DEBUG: Log the config being compiled
        if log_file is not None:
            try:
                with log_file.open("a") as f:
                    f.write(f"COMPILE params={cand}\n")
                    f.write(f"  scfg['parameters']={scfg.get('parameters')}\n")
                    # Check feature params
                    for feat in scfg.get("features", []):
                        fname = feat.get("name")
                        fparams = feat.get("params", {})
                        f.write(f"  feature '{fname}': params={fparams}\n")
            except Exception:
                pass

        strat = compile_strategy(scfg)

        # DEBUG: Log compiled feature params
        if log_file is not None:
            try:
                with log_file.open("a") as f:
                    f.write("COMPILED strategy:\n")
                    f.write(f"  strat.features type={type(strat.features)}\n")
                    f.write(
                        f"  strat.features len={len(strat.features) if hasattr(strat.features, '__len__') else 'N/A'}\n"
                    )
                    if hasattr(strat, "features") and strat.features:
                        for i, feat in enumerate(strat.features):
                            f.write(f"  feature[{i}]: {feat}\n")
                    f.write(
                        f"  strat._feature_df cols={list(strat._feature_df.columns) if hasattr(strat, '_feature_df') and strat._feature_df is not None else 'N/A'}\n"
                    )
            except Exception as e:
                with log_file.open("a") as f:
                    f.write(f"  COMPILE LOG ERROR: {e}\n")

        sig = strat.generate_signals(df)

        # DEBUG: Log detailed info
        if log_file is not None:
            try:
                with log_file.open("a") as f:
                    f.write(f"DEBUG params={cand}\n")
                    f.write(
                        f"  df.shape={df.shape}, df.index[0]={df.index[0]}, df.index[-1]={df.index[-1]}\n"
                    )
                    f.write(f"  sig.shape={sig.shape}\n")
                    vc = sig.value_counts()
                    f.write(f"  sig.value_counts()={dict(vc)}\n")
                    f.write(f"  rmm_ctx keys count={len(rmm_ctx) if rmm_ctx else 0}\n")
                    # Log feature dataframe if available
                    feat_df = getattr(strat, "_feature_df", None)
                    if feat_df is not None:
                        f.write(f"  feat_df.shape={feat_df.shape}\n")
                        # Check EMA values
                        if (
                            "ema_fast" in feat_df.columns
                            and "ema_slow" in feat_df.columns
                        ):
                            non_nan_fast = feat_df["ema_fast"].notna().sum()
                            non_nan_slow = feat_df["ema_slow"].notna().sum()
                            f.write(f"  ema_fast non-NaN count={non_nan_fast}\n")
                            f.write(f"  ema_slow non-NaN count={non_nan_slow}\n")
                    # Save signals and features for analysis
                    import pandas as pd

                    sig_df = pd.DataFrame({"signal": sig})
                    sig_path = (
                        debug_dir
                        / f"sweep_signals_{cand['ema_fast_length']}_{cand['ema_slow_length']}.parquet"
                    )
                    sig_df.to_parquet(str(sig_path))
                    # Save feature dataframe
                    if feat_df is not None:
                        feat_path = (
                            debug_dir
                            / f"sweep_features_{cand['ema_fast_length']}_{cand['ema_slow_length']}.parquet"
                        )
                        feat_df.to_parquet(str(feat_path))
            except Exception as e:
                with log_file.open("a") as f:
                    f.write(f"  DEBUG ERROR: {e}\n")

        _res = run_backtest(
            market_data=df,
            signals=sig,
            strategy=strat,
            config=cfg,
            rem=rem,
            rmm_context=rmm_ctx,
        )
        trades: list[Trade]
        if isinstance(_res, tuple):
            trades = cast(list[Trade], _res[0])
        else:
            trades = cast(list[Trade], _res)
        total_pnl = float(sum(t.pnl for t in trades))
        if objective == "total_pnl":
            score = total_pnl
        elif objective in ("pnl_minus_dd", "pnl_dd_vol"):
            from trading_platform.portfolio.metrics import calculate_equity_curve

            ec = calculate_equity_curve(trades, float(cfg.initial_cash))
            peak = float(cfg.initial_cash)
            max_dd = 0.0
            for _, v in ec:
                if v > peak:  # pragma: no cover
                    peak = v
                dd = max(0.0, peak - v)
                if dd > max_dd:
                    max_dd = dd
            penalty = float(dd_penalty or 1.0)
            score = total_pnl - penalty * max_dd
            if objective == "pnl_dd_vol":
                # Volatility penalty based on std of trade PnL
                vals = [float(t.pnl) for t in trades]
                if vals:
                    m = sum(vals) / len(vals)
                    var = sum((x - m) ** 2 for x in vals) / len(vals)
                    std = var**0.5
                else:
                    std = 0.0
                beta = float(vol_penalty or 0.0)
                score -= beta * std
        else:
            score = total_pnl
        results.append({"params": cand, "score": score})
        # Debug logging per candidate
        try:
            if log_file is not None:
                vc = sig.value_counts()
                long_ct = int(vc.get("long", 0)) if hasattr(vc, "get") else 0
                short_ct = int(vc.get("short", 0)) if hasattr(vc, "get") else 0
                with log_file.open("a") as f:
                    f.write(
                        f"params={cand} long={long_ct} short={short_ct} "
                        f"trades={len(trades)} score={score}\n"
                    )
        except Exception:
            pass
    results.sort(key=lambda r: float(r["score"]), reverse=True)
    top = results[0] if results else {"params": {}, "score": 0.0}
    return {"top": top, "results": results}


def walk_forward_optimize_and_test(
    df: pd.DataFrame,
    base_cfg: dict[str, Any],
    strategy_cfg: dict[str, Any],
    *,
    window: int,
    step: int,
    grid: dict[str, list[Any]],
    seed: int | None = None,
    objective: str = "total_pnl",
    dd_penalty: float | None = None,
    data_handler: Any | None = None,
    vol_penalty: float | None = None,
) -> dict[str, Any]:
    splits = walk_forward_splits(df.index, window=window, step=step)
    if seed is not None:
        random.seed(seed)
    per_split: list[dict[str, Any]] = []
    oos_scores: list[float] = []
    for s in splits:
        train = df.loc[s.train_start : s.train_end]
        test = df.loc[s.test_start : s.test_end]
        ps = run_parameter_sweep(
            train,
            base_cfg,
            strategy_cfg,
            grid=grid,
            objective=objective,
            dd_penalty=dd_penalty,
            vol_penalty=vol_penalty,
        )
        best = ps.get("top", {}).get("params", {})
        scfg = deepcopy(strategy_cfg)
        p = dict(scfg.get("parameters") or {})
        p.update(best)
        scfg["parameters"] = p
        cfg = RunConfig.model_validate(base_cfg)
        rem = RiskExitManager(config=(base_cfg.get("rem_config") or {}))
        strat = compile_strategy(scfg)
        sig = strat.generate_signals(test)
        _res2 = run_backtest(
            market_data=test,
            signals=sig,
            strategy=strat,
            config=cfg,
            rem=rem,
            rmm_context=_rmm_context(test, base_cfg, data_handler),
        )
        trades2: list[Trade]
        if isinstance(_res2, tuple):
            trades2 = cast(list[Trade], _res2[0])
        else:  # pragma: no cover
            trades2 = cast(list[Trade], _res2)
        score = float(sum(t.pnl for t in trades2))
        oos_scores.append(score)
        per_split.append(
            {
                "train_start": s.train_start,
                "train_end": s.train_end,
                "test_start": s.test_start,
                "test_end": s.test_end,
                "best_params": best,
                "oos_score": score,
            }
        )
    from statistics import mean, median

    return {
        "splits": [
            {
                **{k: v for k, v in d.items() if not k.endswith("_start")},
                "train_start": per_split[i]["train_start"],
                "train_end": per_split[i]["train_end"],
                "test_start": per_split[i]["test_start"],
                "test_end": per_split[i]["test_end"],
            }
            for i, d in enumerate(per_split)
        ],
        "oos_total_pnl": {
            "mean": float(mean(oos_scores)) if oos_scores else 0.0,
            "median": float(median(oos_scores)) if oos_scores else 0.0,
            "n_splits": len(oos_scores),
        },
    }


def monte_carlo_resimulation(
    df: pd.DataFrame,
    base_cfg: dict[str, Any],
    strategy_cfg: dict[str, Any],
    *,
    trials: int,
    seed: int | None = None,
    mode: str = "bar_bootstrap",
    cost_jitter: dict[str, Any] | None = None,
    perturbation: dict[str, Any] | None = None,
    data_handler: Any | None = None,
) -> dict[str, Any]:
    """Monte Carlo by resimulating price paths and re-running the engine.

    - mode 'bar_bootstrap': sample bars with replacement, preserving length.
    Returns distribution summaries and exemplar equity paths.
    """
    if seed is not None:
        random.seed(seed)

    def _sample_bars(data: pd.DataFrame) -> pd.DataFrame:
        n = len(data)
        idxs = [random.randrange(n) for _ in range(n)]
        out = data.iloc[idxs].copy()
        out.index = data.index  # keep monotonic index
        return out

    def _perturb_bars(data: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(perturbation, dict):
            return data
        mode_p = str(perturbation.get("mode", "gaussian"))
        std_pct = float(perturbation.get("std_pct", 0.0) or 0.0)
        if std_pct <= 0:
            return data
        out = data.copy()
        if mode_p == "block":
            bl = int(perturbation.get("block_len", 5) or 5)  # pragma: no cover
            bl = max(1, bl)  # pragma: no cover
            for start in range(0, len(out), bl):  # pragma: no cover
                z = random.gauss(0.0, std_pct)  # pragma: no cover
                factor = 1.0 + z  # pragma: no cover
                end = min(len(out), start + bl)  # pragma: no cover
                rows = out.index[start:end]  # pragma: no cover
                for col in ("open", "high", "low", "close"):  # pragma: no cover
                    ser = out.loc[rows, col].astype(float) * factor  # pragma: no cover
                    out.loc[rows, col] = ser  # pragma: no cover
        else:
            # Apply same multiplicative noise per bar to preserve OHLC order
            for i in range(len(out)):
                z = random.gauss(0.0, std_pct)
                factor = 1.0 + z
                for col in ("open", "high", "low", "close"):
                    j = out.columns.get_loc(col)
                    try:
                        base_val = float(out.iat[i, j])  # type: ignore[arg-type,index]
                    except Exception:  # pragma: no cover
                        base_val = 0.0  # pragma: no cover
                    out.iat[i, j] = base_val * factor  # type: ignore[index]
        return out

    def _percentile(values: list[float], pct: float) -> float:
        if not values:  # pragma: no cover
            return 0.0  # pragma: no cover
        vs = sorted(values)
        k = (len(vs) - 1) * pct
        f = int(k)
        c = min(f + 1, len(vs) - 1)
        if f == c:
            return float(vs[f])
        d0 = vs[f] * (c - k)
        d1 = vs[c] * (k - f)
        return float(d0 + d1)

    cfg = RunConfig.model_validate(base_cfg)
    rem = RiskExitManager(config=(base_cfg.get("rem_config") or {}))

    # PERFORMANCE FIX: Compute RMM context once before loop instead of per trial
    # For bar_resimulation mode, the index doesn't change, so we can reuse the same RMM context
    # For bar_bootstrap mode, the index is preserved (line 441), so RMM context is still valid
    rmm_ctx = _rmm_context(df, base_cfg, data_handler)

    finals: list[float] = []
    finals_pnl: list[float] = []
    dd_vals: list[float] = []
    win_rates: list[float] = []
    tuw_ratios: list[float] = []
    curves: list[tuple[float, list[float]]] = []  # (final_eq, curve)

    for _ in range(max(1, int(trials))):
        sim_df = _sample_bars(df) if mode == "bar_bootstrap" else df.copy()
        sim_df = _perturb_bars(sim_df)
        # Optionally jitter cost model per trial
        cfg_trial = cfg
        if isinstance(cost_jitter, dict) and cost_jitter:
            cm = dict(getattr(cfg, "cost_model", {}) or {})
            sp = float(cost_jitter.get("spread_jitter_pct", 0.0) or 0.0)
            sl = float(cost_jitter.get("slippage_jitter_pct", 0.0) or 0.0)

            def _j(v: float, pct: float) -> float:
                if pct <= 0:
                    return v
                r = random.uniform(-pct, pct)
                return max(0.0, v * (1.0 + r))

            base_sp = float(cm.get("spread_per_unit", 0.0) or 0.0)
            base_sl = float(cm.get("slippage_per_unit", 0.0) or 0.0)
            cm["spread_per_unit"] = _j(base_sp, sp)
            cm["slippage_per_unit"] = _j(base_sl, sl)
            cfg_trial = cfg.model_copy(update={"cost_model": cm})
        strat = compile_strategy(
            {**strategy_cfg, "parameters": strategy_cfg.get("parameters", {})}
        )
        sig = strat.generate_signals(sim_df)
        _res3 = run_backtest(
            market_data=sim_df,
            signals=sig,
            strategy=strat,
            config=cfg_trial,
            rem=rem,
            rmm_context=rmm_ctx,
        )
        trades3: list[Trade]
        if isinstance(_res3, tuple):
            trades3 = cast(list[Trade], _res3[0])
        else:  # pragma: no cover
            trades3 = cast(list[Trade], _res3)  # pragma: no cover
        # Build adjusted PnLs with optional per-trade cost jitter
        adj_pnls: list[float] = []
        pct = 0.0
        if isinstance(cost_jitter, dict):
            pct = float(cost_jitter.get("per_trade_cost_jitter_pct", 0.0) or 0.0)
        for t in trades3:
            base_pnl = float(t.pnl)
            if pct > 0.0:
                base_cost = float(getattr(t, "cost_currency", 0.0) or 0.0)
                jitter = random.uniform(-pct, pct)
                new_cost = max(0.0, base_cost * (1.0 + jitter))
                delta = new_cost - base_cost
                adj_pnls.append(base_pnl - delta)
            else:
                adj_pnls.append(base_pnl)

        # Equity curve and metrics using adjusted pnls
        eq_vals: list[float] = []
        eq = float(cfg.initial_cash)
        eq_vals.append(eq)
        for p in adj_pnls:
            eq += float(p)
            eq_vals.append(eq)
        final_eq = eq_vals[-1] if eq_vals else float(cfg.initial_cash)
        finals.append(final_eq)
        finals_pnl.append(final_eq - float(cfg.initial_cash))
        # Max drawdown and TUW
        peak = eq_vals[0] if eq_vals else float(cfg.initial_cash)
        max_dd = 0.0
        uw_count = 0
        for v in eq_vals:
            if v > peak:
                peak = v
            dd = max(0.0, peak - v)
            if dd > 0:
                uw_count += 1
            if dd > max_dd:
                max_dd = dd
        dd_vals.append(max_dd)
        if eq_vals:
            tuw_ratios.append(float(uw_count) / float(len(eq_vals)))
        else:  # pragma: no cover
            tuw_ratios.append(0.0)  # pragma: no cover
        # Win rate
        wins = sum(1 for p in adj_pnls if p > 0)
        wr = float(wins) / float(len(adj_pnls)) if adj_pnls else 0.0
        win_rates.append(wr)
        # Store a downsampled curve exemplar (<= 30 points)
        if eq_vals:
            step = max(1, int(len(eq_vals) / 30))
            curves.append((final_eq, eq_vals[::step]))
        else:  # pragma: no cover
            curves.append((final_eq, []))  # pragma: no cover

    # Risk aggregates
    p05 = _percentile(finals_pnl, 0.05)
    p95 = _percentile(finals_pnl, 0.95)
    var_95 = p05
    tail = [x for x in finals_pnl if x <= var_95]  # pragma: no cover
    cvar_95 = float(sum(tail) / len(tail)) if tail else 0.0  # pragma: no cover
    ruin_prob = (  # pragma: no cover
        float(sum(1 for fe in finals if fe <= 0.0) / len(finals)) if finals else 0.0
    )  # pragma: no cover

    # Exemplars by final equity
    if curves:
        curves.sort(key=lambda x: x[0])
        worst = curves[0]
        best = curves[-1]
        median_idx = len(curves) // 2
        median = curves[median_idx]
        exemplars = {
            "worst": {"final_equity": worst[0], "curve": worst[1]},
            "median": {"final_equity": median[0], "curve": median[1]},
            "best": {"final_equity": best[0], "curve": best[1]},
        }
    else:  # pragma: no cover
        exemplars = {"worst": {}, "median": {}, "best": {}}  # pragma: no cover

    from statistics import mean

    return {
        "mode": str(mode) if mode else "bar_resimulation",
        "trials": int(trials),
        "config": {
            "cost_jitter": cost_jitter or {},
            "perturbation": perturbation or {},
        },
        "final_equity": {
            "mean": float(mean(finals)) if finals else float(cfg.initial_cash),
            "p05": float(_percentile(finals, 0.05)),
            "p95": float(_percentile(finals, 0.95)),
        },
        "total_pnl": {
            "mean": float(mean(finals_pnl)) if finals_pnl else 0.0,
            "p05": float(p05),
            "p95": float(p95),
        },
        "max_drawdown": {
            "mean": float(mean(dd_vals)) if dd_vals else 0.0,
            "p05": float(_percentile(dd_vals, 0.05)),
            "p95": float(_percentile(dd_vals, 0.95)),
        },
        "win_rate": {
            "mean": float(mean(win_rates)) if win_rates else 0.0,
            "p05": float(_percentile(win_rates, 0.05)),
            "p95": float(_percentile(win_rates, 0.95)),
        },
        "risk": {"var_95": float(var_95), "cvar_95": float(cvar_95)},
        "ruin_prob": float(ruin_prob),
        "time_under_water_mean": (float(mean(tuw_ratios)) if tuw_ratios else 0.0),
        "exemplars": exemplars,
    }
