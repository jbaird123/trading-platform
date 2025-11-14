"""Validate RMM candidates by executing backtests and exporting metrics."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

BacktestFn = Callable[[Path, Path, Path], dict]


def _trade_pnls(trades: Sequence[object]) -> np.ndarray:
    values = []
    for trade in trades:
        values.append(float(getattr(trade, "pnl", 0.0)))
    return np.asarray(values, dtype=float)


def _total_pnl(pnls: np.ndarray) -> float:
    return float(pnls.sum())


def _sharpe_ratio(pnls: np.ndarray) -> float:
    if len(pnls) == 0:
        return 0.0
    mean = pnls.mean()
    std = pnls.std(ddof=1) if len(pnls) > 1 else 0.0
    if std == 0:
        return 0.0
    return float(mean / std)


def _max_drawdown(equity: Sequence[float]) -> float:
    if not equity:
        return 0.0
    equity_arr = np.asarray(equity, dtype=float)
    running_max = np.maximum.accumulate(equity_arr)
    drawdowns = running_max - equity_arr
    return float(drawdowns.max())


def _default_backtest(candidate: Path, strategy: Path, enriched: Path) -> dict:
    raise RuntimeError(
        "No backtest function provided. Supply backtest_fn when calling validation."
    )


def validate_rmm_candidate(
    candidate_path: Path,
    strategy_config_path: Path,
    enriched_path: Path,
    output_dir: Path,
    *,
    backtest_fn: BacktestFn = _default_backtest,
) -> dict:
    """Run backtest for a single candidate and persist validation metrics."""

    output_dir.mkdir(parents=True, exist_ok=True)

    backtest_result = backtest_fn(candidate_path, strategy_config_path, enriched_path)

    trades = backtest_result.get("trades", [])
    equity_entries = backtest_result.get("equity_curve", [])
    equity: list[float] = []
    for entry in equity_entries:
        if isinstance(entry, (tuple, list)) and entry:
            value = entry[-1]
        else:
            value = entry
        try:
            equity.append(float(value))
        except (TypeError, ValueError):
            continue
    skipped = backtest_result.get("skipped", [])

    pnl_array = _trade_pnls(trades)
    metrics = {
        "candidate_path": str(candidate_path),
        "strategy_config": str(strategy_config_path),
        "total_pnl": _total_pnl(pnl_array),
        "sharpe": _sharpe_ratio(pnl_array),
        "max_drawdown": _max_drawdown(equity),
        "n_trades": len(trades),
        "n_skipped": len(skipped),
    }

    report_path = output_dir / "validation_report.json"
    report_path.write_text(json.dumps(metrics, indent=2))

    return metrics


def _candidate_files(candidate_root: Path) -> Iterable[Path]:
    return candidate_root.rglob("candidate-*.yaml")


def validate_all_candidates(
    candidate_root: Path,
    strategy_config_path: Path,
    enriched_path: Path,
    output_dir: Path,
    *,
    backtest_fn: BacktestFn = _default_backtest,
) -> list[dict]:
    """Validate every candidate in a directory tree and create summary CSV."""

    summaries: list[dict] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for candidate_path in _candidate_files(candidate_root):
        report_dir = output_dir / candidate_path.parent.name
        metrics = validate_rmm_candidate(
            candidate_path,
            strategy_config_path,
            enriched_path,
            report_dir,
            backtest_fn=backtest_fn,
        )
        metrics["context_key"] = candidate_path.parent.name
        summaries.append(metrics)

    summaries.sort(key=lambda item: (-item["total_pnl"], -item["sharpe"]))

    if summaries:
        csv_path = output_dir / "validation_summary.csv"
        fieldnames = list(summaries[0].keys())
        with csv_path.open("w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summaries)

    return summaries
