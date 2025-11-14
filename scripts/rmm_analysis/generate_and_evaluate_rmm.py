"""Generate RMM configs from diagnostic summaries and evaluate them."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Sequence, cast

import yaml
from trading_platform.ai.pipeline.candidate_generator import (
    MAX_FEATURE_PREDICATES,
    _candidate_yaml,
)

TIMEFRAME_KEY = "execution_timeframe"


def _parse_context_timeframe(context: str) -> str:
    return context.split("_", 1)[0]


def _update_timeframe_fields(config: dict, timeframe: str) -> None:
    if TIMEFRAME_KEY in config:
        config[TIMEFRAME_KEY] = timeframe
    instrument = config.get("instrument")
    if isinstance(instrument, dict):
        instrument["timeframe"] = timeframe
    data_request = config.get("data_request")
    if isinstance(data_request, dict):
        data_request["timeframe"] = timeframe


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate RMM configs from diagnostic summaries and evaluate "
            "them in-sample and out-of-sample."
        )
    )
    parser.add_argument(
        "--summaries-dir",
        required=True,
        type=Path,
        help="Directory containing diagnostic_summary.json files.",
    )
    parser.add_argument(
        "--baseline-config",
        required=True,
        type=Path,
        help="Baseline run config YAML for in-sample evaluation.",
    )
    parser.add_argument(
        "--oos-config",
        type=Path,
        help="Optional out-of-sample run config YAML.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to store generated candidates and evaluation artefacts.",
    )
    parser.add_argument(
        "--contexts",
        nargs="*",
        help="Optional subset of context keys to process (e.g., 1H_trend_following).",
    )
    parser.add_argument(
        "--top-features",
        type=int,
        default=MAX_FEATURE_PREDICATES,
        help=(
            "Number of top features to keep per context (default: candidate "
            "generator limit)."
        ),
    )
    parser.add_argument(
        "--poetry-exe",
        default="poetry",
        help="Poetry executable (default: poetry).",
    )
    return parser.parse_args(argv)


def load_summary(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text()))


def build_candidate(summary: dict[str, object], top_n: int) -> dict[str, object]:
    raw_bounds = summary.get("feature_bounds", [])
    bounds: list[dict[str, object]] = []
    if isinstance(raw_bounds, list):
        for item in raw_bounds:
            if isinstance(item, dict):
                bounds.append(item)

    raw_top = summary.get("top_features", [])
    if isinstance(raw_top, list):
        top_features = [str(name) for name in raw_top if isinstance(name, str)][:top_n]
    else:
        top_features = []

    filtered: list[dict[str, object]] = []
    for item in bounds:
        feature = item.get("feature")
        if isinstance(feature, str) and feature in top_features:
            filtered.append(item)

    context_key = summary.get("context_key")
    if not isinstance(context_key, str) or not context_key:
        raise ValueError("diagnostic summary missing context_key")
    candidate = cast(dict[str, object], _candidate_yaml(context_key, filtered))
    return candidate


def write_yaml(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def load_config(path: Path) -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load(path.read_text()))


def write_config(config: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False))


def run_backtest(
    poetry_exe: str,
    config_path: Path,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            poetry_exe,
            "run",
            "tp",
            "run-backtest",
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
    )
    user_dirs = list(output_dir.iterdir())
    if not user_dirs:
        raise RuntimeError(f"No run outputs found in {output_dir}")
    user_dir = max(user_dirs, key=lambda p: p.stat().st_mtime)
    run_dirs = list(user_dir.iterdir())
    if not run_dirs:
        raise RuntimeError(f"No run directories found in {user_dir}")
    latest_run = max(run_dirs, key=lambda p: p.stat().st_mtime)
    return latest_run / "brief.json"


def extract_metrics(brief_path: Path) -> dict:
    brief = json.loads(brief_path.read_text())
    overall = brief.get("overall_performance", {})
    equity = brief.get("equity_stats", {})
    return {
        "total_pnl": float(overall.get("total_pnl", 0.0)),
        "n_trades": int(overall.get("n_trades", 0)),
        "sharpe": float(equity.get("sharpe_ratio", 0.0)),
        "max_drawdown": float(equity.get("max_drawdown", 0.0)),
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    summaries_dir = args.summaries_dir
    output_dir = args.output_dir
    candidates_dir = output_dir / "candidates"
    results = []

    summary_paths = list(summaries_dir.glob("*/diagnostic_summary.json"))
    if args.contexts:
        summary_paths = [
            path for path in summary_paths if path.parent.name in set(args.contexts)
        ]
    if not summary_paths:
        raise RuntimeError("No diagnostic summaries found for the specified contexts.")

    for summary_path in summary_paths:
        summary = load_summary(summary_path)
        context_value = summary.get("context_key")
        if not isinstance(context_value, str):
            raise ValueError(
                f"diagnostic summary at {summary_path} missing context_key"
            )
        context = context_value
        timeframe = _parse_context_timeframe(context)
        print(f"Processing context {context}")
        candidate_yaml = build_candidate(summary, args.top_features)
        candidate_path = candidates_dir / f"auto_from_model_{context}.yaml"
        write_yaml(candidate_yaml, candidate_path)

        ctx_dir = output_dir / context
        insample_cfg = load_config(args.baseline_config)
        _update_timeframe_fields(insample_cfg, timeframe)
        insample_cfg["user_id"] = "rmm_model_eval_insample"
        insample_cfg["rmm_path"] = str(candidate_path.resolve())
        insample_cfg.pop("rmm_config", None)
        insample_cfg_path = ctx_dir / "insample_config.yaml"
        write_config(insample_cfg, insample_cfg_path)

        insample_output = ctx_dir / "insample_runs"
        brief_path = run_backtest(args.poetry_exe, insample_cfg_path, insample_output)
        metrics = extract_metrics(brief_path)
        results.append(
            {
                "context": context,
                "dataset": "in_sample",
                "candidate_path": str(candidate_path.resolve()),
                **metrics,
            }
        )

        if args.oos_config:
            oos_cfg = load_config(args.oos_config)
            _update_timeframe_fields(oos_cfg, timeframe)
            oos_cfg["user_id"] = "rmm_model_eval_oos"
            oos_cfg["rmm_path"] = str(candidate_path.resolve())
            oos_cfg.pop("rmm_config", None)
            oos_cfg_path = ctx_dir / "oos_config.yaml"
            write_config(oos_cfg, oos_cfg_path)
            oos_output = ctx_dir / "oos_runs"
            brief_oos = run_backtest(args.poetry_exe, oos_cfg_path, oos_output)
            metrics_oos = extract_metrics(brief_oos)
            results.append(
                {
                    "context": context,
                    "dataset": "out_of_sample",
                    "candidate_path": str(candidate_path.resolve()),
                    **metrics_oos,
                }
            )

    results_path = output_dir / "rmm_model_eval_metrics.json"
    results_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote metrics to {results_path}")


if __name__ == "__main__":
    main()
