from __future__ import annotations
# ruff: noqa: I001

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from trading_platform.core.config import RunConfig
from trading_platform.core.demo import generate_demo_run
from trading_platform.core.run import initialize_run


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
    # Use demo trades for now to satisfy artifacts; will be replaced by strategy BT
    demo_path = generate_demo_run(user_id=cfg.user_id)
    print(f"Run created at: {demo_path}")
    print(f"- Brief: {demo_path / 'brief.json'}")
    print(f"- Report: {demo_path / 'report.html'}")
    print(f"- Trades: {demo_path / 'trades.csv'}")
    return 0


def cmd_run_live(args: argparse.Namespace) -> int:
    # Placeholder: dry-run stub
    if args.dry_run:
        print("Live controller (dry-run): OK")
        return 0
    print("Live controller is not yet implemented. Use --dry-run.", file=sys.stderr)
    return 2


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

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
