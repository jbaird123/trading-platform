"""Profitability impact analysis for thresholded logistic predictions."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

if __package__ is None or __package__ == "":
    import sys

    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from scripts.rmm_analysis.grid_feature_pattern_search import (
    _prepare_xy,
    collect_patterns,
    load_data,
    split_data,
)
from scripts.rmm_analysis.threshold_sweep_selected_groups import _parse_thresholds
from scripts.rmm_analysis.train_profitability_selected_groups import (
    _parse_combos,
    _resolve_contexts,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute profitability metrics for logistic sign predictions under "
            "different probability thresholds."
        )
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (enriched trades).",
    )
    parser.add_argument(
        "--output-path",
        required=True,
        type=Path,
        help="CSV path for profitability metrics per threshold.",
    )
    parser.add_argument(
        "--group-combo",
        action="append",
        default=None,
        help=(
            "Feature-group combination to evaluate (e.g., alignment+structure). "
            "Defaults to curated combos from training script."
        ),
    )
    parser.add_argument(
        "--context",
        action="append",
        default=None,
        help=(
            "Specific context(s) to evaluate (e.g., 15min_trend_following). "
            "If omitted, all contexts present in the dataset are used."
        ),
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default="0.3,0.4,0.5,0.6,0.7",
        help="Comma-separated probability thresholds (default: 0.3-0.7).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    return parser.parse_args(argv)


def compute_profitability_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    thresholds: Iterable[float],
) -> list[dict[str, float]]:
    """Aggregate profitability statistics for thresholded predictions."""

    metrics: list[dict[str, float]] = []
    total_trades = float(len(y_true))
    overall_mean = float(np.mean(y_true)) if total_trades else 0.0
    overall_win_rate = float(np.mean(y_true > 0.0)) if total_trades else 0.0

    for threshold in thresholds:
        mask = probabilities >= threshold
        selected = y_true[mask]
        selected_count = float(len(selected))
        if selected_count == 0:
            mean_r = float("nan")
            median_r = float("nan")
            win_rate = float("nan")
        else:
            mean_r = float(np.mean(selected))
            median_r = float(np.median(selected))
            win_rate = float(np.mean(selected > 0.0))

        metrics.append(  # noqa: E501
            {
                "threshold": float(threshold),
                "selected_trades": selected_count,
                "selected_fraction": (
                    selected_count / total_trades if total_trades else 0.0
                ),
                "mean_r_multiple_selected": mean_r,
                "median_r_multiple_selected": median_r,
                "win_rate_selected": win_rate,
                "overall_mean_r_multiple": overall_mean,
                "overall_win_rate": overall_win_rate,
                "lift_mean_r_multiple": (
                    mean_r - overall_mean if selected_count else float("nan")
                ),
                "lift_win_rate": (
                    win_rate - overall_win_rate if selected_count else float("nan")
                ),
            }
        )
    return metrics


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    thresholds = _parse_thresholds(args.thresholds)
    combos = _parse_combos(args.group_combo)
    df = load_data(args.enriched_data)
    train_df, test_df = split_data(df)
    contexts = _resolve_contexts(df, args.context)

    rows: list[dict[str, object]] = []
    for combo in combos:
        patterns = collect_patterns(combo)
        combo_name = "+".join(combo)
        for timeframe, archetype in contexts:
            train_subset = train_df[
                (train_df["execution_timeframe"] == timeframe)
                & (train_df["strategy_archetype"] == archetype)
            ]
            test_subset = test_df[
                (test_df["execution_timeframe"] == timeframe)
                & (test_df["strategy_archetype"] == archetype)
            ]
            if len(train_subset) < 50 or len(test_subset) < 30:
                continue
            X_train, X_test, y_train, y_test, _ = _prepare_xy(
                train_subset,
                test_subset,
                patterns,
            )
            pipeline = make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=args.random_state,
                ),
            )
            pipeline.fit(X_train, (y_train > 0.0).astype(int))
            probabilities = pipeline.predict_proba(X_test)[:, 1]
            metrics = compute_profitability_metrics(y_test, probabilities, thresholds)
            for metric in metrics:
                row: dict[str, object] = {
                    "context": f"{timeframe}_{archetype}",
                    "group_combo": combo_name,
                    "pattern_count": len(patterns),
                    "test_samples": float(len(y_test)),
                }
                row.update(metric)
                rows.append(row)

    if not rows:
        print("No profitability evaluations were produced.")
        return

    output_path = args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"Wrote profitability threshold metrics to {output_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
