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
from trading_platform.data.schema import resample_ohlc
from trading_platform.execution.oanda_stub import OandaStubAdapter
from trading_platform.portfolio.portfolio import PortfolioManager
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import compute_data_quality
from trading_platform.reporting.compare_html import save_comparison_report
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
    data = cfg_raw.get("data") or {}
    df: pd.DataFrame
    if isinstance(data, dict) and data.get("csv_path"):
        p = Path(str(data["csv_path"]))
        # Read CSV with first column as index; require a datetime-like index.
        df = pd.read_csv(p, index_col=0)
        # First try an explicit format commonly used in OHLCV CSVs.
        try:
            df.index = pd.to_datetime(df.index, format="%Y-%m-%d %H:%M:%S")
        except Exception:
            # Fallback to generic parsing (dateutil) without warnings at read time.
            try:
                df.index = pd.to_datetime(df.index)
            except Exception as exc:  # pragma: no cover
                raise SystemExit(
                    "CSV index could not be parsed as datetime. Please provide "
                    "ISO timestamps or '%Y-%m-%d %H:%M:%S' format in the first "
                    "column."
                ) from exc
        # Optional resample: e.g., "1D" for daily, "1H" for hourly
        rs = str(data.get("resample", "")).strip() if isinstance(data, dict) else ""
        if rs:
            df = resample_ohlc(df, rs)
        # Final guard: ensure we have a DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):  # pragma: no cover
            raise SystemExit(
                "CSV index must be datetime-like. Provide parseable timestamps."
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
    strat = compile_strategy(strat_cfg)
    signals = strat.generate_signals(df)

    rem_cfg = cfg_raw.get("rem_config") or {}
    rem = RiskExitManager(config=rem_cfg)

    res = run_backtest(
        market_data=df,
        signals=signals,
        strategy=strat,
        config=cfg,
        rem=rem,
        return_exposure=True,
    )
    if isinstance(res, tuple):
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
    params: dict[str, Any] = {}
    finalize_run(
        run_path,
        meta=meta,
        params=params,
        trades=trades,
        initial_cash=float(cfg_raw.get("initial_cash", 100000.0)),
        config=cfg,
        exposure_curve=exposure,
        data_quality=compute_data_quality(df),
    )
    print(f"Run created at: {run_path}")
    print(f"- Brief: {run_path / 'brief.json'}")
    print(f"- Report: {run_path / 'report.html'}")
    print(f"- Trades: {run_path / 'trades.csv'}")
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


def cmd_compare(args: argparse.Namespace) -> int:
    a = Path(args.a)
    b = Path(args.b)
    out = Path(str(args.out))
    if not a.exists() or not b.exists():
        print("Both input brief paths must exist", file=sys.stderr)
        return 2
    save_comparison_report(a, b, out)
    print(f"Comparison written to: {out}")
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

    pc = sub.add_parser("compare", help="Compare two briefs and write HTML")
    pc.add_argument("a", help="Path to first brief.json")
    pc.add_argument("b", help="Path to second brief.json")
    pc.add_argument("--out", default="comparison.html", help="Output HTML path")
    pc.set_defaults(func=cmd_compare)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
