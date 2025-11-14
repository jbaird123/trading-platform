"""Automate RMM optimization via quantile sweeps and OOS validation."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

DEFAULT_QUANTILES = [
    "0.25,0.75",
    "0.20,0.80",
    "0.30,0.70",
    "0.15,0.85",
    "0.35,0.65",
    "0.10,0.90",
    "0.40,0.60",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Iterate quantile sweeps to find the best RMM candidate."
    )
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--baseline-config", required=True, type=Path)
    parser.add_argument("--oos-config", required=True, type=Path)
    parser.add_argument("--enriched-path", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--data-root", default=Path("data/dvc/raw"), type=Path)
    parser.add_argument("--target-context", default="1H_trend_following")
    parser.add_argument(
        "--quantiles",
        nargs="+",
        default=DEFAULT_QUANTILES,
        help="Pairs formatted as lower,upper (e.g., 0.25,0.75).",
    )
    parser.add_argument(
        "--baseline-trades",
        type=int,
        required=True,
        help="Baseline trade count for guardrail checks.",
    )
    parser.add_argument(
        "--baseline-max-drawdown",
        type=float,
        required=True,
        help="Baseline max drawdown for guardrail checks.",
    )
    parser.add_argument(
        "--min-trade-ratio",
        type=float,
        default=0.5,
        help="Minimum fraction of baseline trades a candidate must keep.",
    )
    parser.add_argument(
        "--max-drawdown-multiplier",
        type=float,
        default=1.0,
        help="Allow drawdown up to baseline * multiplier.",
    )
    parser.add_argument(
        "--min-total-pnl",
        type=float,
        default=float("-inf"),
        help="Minimum acceptable total PnL for candidates.",
    )
    parser.add_argument(
        "--oos-baseline-trades",
        type=int,
        required=True,
        help="Out-of-sample baseline trade count.",
    )
    parser.add_argument(
        "--oos-baseline-max-drawdown",
        type=float,
        required=True,
        help="Out-of-sample baseline max drawdown.",
    )
    parser.add_argument(
        "--oos-min-trade-ratio",
        type=float,
        default=0.5,
        help="Minimum fraction of out-of-sample trades to keep.",
    )
    parser.add_argument(
        "--oos-max-drawdown-multiplier",
        type=float,
        default=1.0,
        help="Allow out-of-sample drawdown up to baseline * multiplier.",
    )
    parser.add_argument(
        "--oos-min-total-pnl",
        type=float,
        default=float("-inf"),
        help="Minimum out-of-sample total PnL.",
    )
    parser.add_argument(
        "--promote-path",
        type=Path,
        help="Optional destination to copy the winning candidate.",
    )
    return parser.parse_args(argv)


def _run_cmd(cmd: Iterable[str]) -> None:
    subprocess.run(list(cmd), check=True)


def _timestamp() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _read_validation_summary(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def _ensure_unique_promote(promote_path: Path) -> None:
    if promote_path.exists():
        raise FileExistsError(f"Promote target already exists: {promote_path}")
    promote_path.parent.mkdir(parents=True, exist_ok=True)


def _copy_candidate(src: Path, dst: Path) -> None:
    _ensure_unique_promote(dst)
    shutil.copy(src, dst)


def _evaluate_oos(
    candidate: Path,
    oos_config: Path,
    data_root: Path,
    enriched_path: Path,
    result_dir: Path,
) -> dict[str, float]:
    result_dir.mkdir(parents=True, exist_ok=True)
    tmp_cfg = result_dir / "run_config.yaml"
    cfg_raw = yaml.safe_load(oos_config.read_text())
    cfg: dict[str, Any] = dict(cfg_raw)
    cfg["rmm_path"] = str(candidate.resolve())
    cfg.pop("rmm_config", None)
    tmp_cfg.write_text(yaml.safe_dump(cfg, sort_keys=False))
    run_dir = result_dir / "runs"
    _run_cmd(
        [
            "poetry",
            "run",
            "tp",
            "run-backtest",
            "--config",
            str(tmp_cfg),
            "--output-dir",
            str(run_dir),
        ]
    )
    user_dir = Path(cfg.get("user_id", "default_user"))
    runs_parent = run_dir / user_dir
    latest = max(runs_parent.iterdir(), key=lambda p: p.stat().st_mtime)
    brief = json.loads((latest / "brief.json").read_text())
    equity = brief["equity_stats"]
    overall = brief["overall_performance"]
    return {
        "sharpe": float(equity["sharpe_ratio"]),
        "max_drawdown": float(equity["max_drawdown"]),
        "n_trades": int(overall["n_trades"]),
        "total_pnl": float(overall["total_pnl"]),
    }


def _parse_quantile_pair(pair: str) -> tuple[float, float]:
    lower_str, upper_str = pair.split(",")
    return float(lower_str), float(upper_str)


@dataclass
class CandidateResult:
    iteration: str
    lower_quantile: float
    upper_quantile: float
    sharpe: float
    max_drawdown: float
    n_trades: int
    total_pnl: float
    candidate_path: str
    eligible: bool


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    args.campaign_root.mkdir(parents=True, exist_ok=True)
    results: list[CandidateResult] = []

    for index, pair in enumerate(args.quantiles, start=1):
        lower, upper = _parse_quantile_pair(pair)
        stamp = _timestamp()
        iter_name = f"{stamp}_{index:02d}_q{int(lower*100):02d}_q{int(upper*100):02d}"
        iter_root = args.campaign_root / iter_name
        gen_dir = iter_root / "generation"
        val_dir = iter_root / "validation"
        gen_dir.mkdir(parents=True, exist_ok=True)
        val_dir.mkdir(parents=True, exist_ok=True)

        _run_cmd(
            [
                "poetry",
                "run",
                "tp",
                "ai-generate-rmm-candidates",
                "--enriched-path",
                str(args.enriched_path),
                "--model-dir",
                str(args.model_dir),
                "--output-dir",
                str(gen_dir),
                "--lower-quantile",
                f"{lower:.2f}",
                "--upper-quantile",
                f"{upper:.2f}",
            ]
        )
        _run_cmd(
            [
                "poetry",
                "run",
                "tp",
                "ai-validate-rmm-candidates",
                "--candidates-dir",
                str(gen_dir / "candidates"),
                "--strategy-config",
                str(args.baseline_config),
                "--enriched-path",
                str(args.enriched_path),
                "--output-dir",
                str(val_dir),
                "--data-root",
                str(args.data_root),
            ]
        )

        summary_path = val_dir / "validation_summary.csv"
        rows = _read_validation_summary(summary_path)
        target_rows = [
            csv_row
            for csv_row in rows
            if csv_row.get("context_key") == args.target_context
        ]
        if not target_rows:
            continue
        summary_row = target_rows[0]
        metrics = CandidateResult(
            iteration=iter_name,
            lower_quantile=lower,
            upper_quantile=upper,
            sharpe=float(summary_row["sharpe"]),
            max_drawdown=float(summary_row["max_drawdown"]),
            n_trades=int(summary_row["n_trades"]),
            total_pnl=float(summary_row["total_pnl"]),
            candidate_path=str(summary_row["candidate_path"]),
            eligible=False,
        )
        min_trades = int(args.baseline_trades * args.min_trade_ratio)
        max_dd_allowed = args.baseline_max_drawdown * args.max_drawdown_multiplier
        eligible = (
            metrics.n_trades >= min_trades
            and metrics.max_drawdown <= max_dd_allowed
            and metrics.total_pnl >= args.min_total_pnl
        )
        metrics.eligible = eligible
        results.append(metrics)

    stats_path = args.campaign_root / "results.json"
    stats_path.write_text(json.dumps([asdict(row) for row in results], indent=2))
    eligible_rows = [row for row in results if row.eligible]
    if not eligible_rows:
        raise RuntimeError("No in-sample candidates satisfied guardrails.")
    eligible_rows.sort(key=lambda row: row.sharpe, reverse=True)

    oos_base_dir = args.campaign_root / "oos_evaluation"
    if oos_base_dir.exists():
        shutil.rmtree(oos_base_dir)
    oos_base_dir.mkdir(parents=True, exist_ok=True)

    min_oos_trades = int(args.oos_baseline_trades * args.oos_min_trade_ratio)
    max_oos_dd = args.oos_baseline_max_drawdown * args.oos_max_drawdown_multiplier

    best_row: CandidateResult | None = None
    best_candidate: Path | None = None
    best_oos: dict[str, float] | None = None

    for row in eligible_rows:
        candidate_path = Path(row.candidate_path)
        iter_dir = oos_base_dir / row.iteration
        oos_metrics = _evaluate_oos(
            candidate_path,
            args.oos_config,
            args.data_root,
            args.enriched_path,
            iter_dir,
        )
        if oos_metrics["n_trades"] < min_oos_trades:
            continue
        if oos_metrics["max_drawdown"] > max_oos_dd:
            continue
        if oos_metrics["total_pnl"] < args.oos_min_total_pnl:
            continue
        best_row = row
        best_candidate = candidate_path
        best_oos = oos_metrics
        break

    if best_row is None or best_candidate is None or best_oos is None:
        raise RuntimeError(
            "No candidate satisfied out-of-sample guardrails; "
            "inspect results.json for details."
        )

    summary = {
        "best_iteration": best_row.iteration,
        "best_candidate": str(best_candidate),
        "in_sample": asdict(best_row),
        "out_of_sample": best_oos,
        "baseline": {
            "trades": args.baseline_trades,
            "max_drawdown": args.baseline_max_drawdown,
            "min_trade_ratio": args.min_trade_ratio,
            "max_drawdown_multiplier": args.max_drawdown_multiplier,
        },
    }
    summary_path = args.campaign_root / "best_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    if args.promote_path and best_candidate is not None:
        _copy_candidate(best_candidate, args.promote_path)


__all__ = ["parse_args", "main"]
