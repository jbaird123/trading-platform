"""Backtest profitability thresholds using logistic probabilities."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from trading_platform.rmm_analysis.grid_feature_pattern_search import (
    _prepare_xy,
    collect_patterns,
    load_data,
    split_data,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare baseline vs. threshold-filtered profitability metrics per "
            "context."
        )
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (enriched trades).",
    )
    parser.add_argument(
        "--recommendations",
        required=True,
        type=Path,
        help="CSV produced by threshold_recommendation_report.py.",
    )
    parser.add_argument(
        "--output-path",
        required=True,
        type=Path,
        help="CSV path for backtest results.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random state for logistic regression (default: 42).",
    )
    return parser.parse_args(argv)


def _load_recommendations(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"context", "group_combo", "threshold"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Recommendation file missing columns: {missing}")
    return df


def _compute_metrics(y_values: np.ndarray) -> dict[str, float]:
    if len(y_values) == 0:
        return {
            "count": 0.0,
            "fraction": 0.0,
            "mean_r_multiple": float("nan"),
            "median_r_multiple": float("nan"),
            "win_rate": float("nan"),
            "sum_r_multiple": 0.0,
        }
    return {
        "count": float(len(y_values)),
        "fraction": float(len(y_values)),  # to be normalised by caller
        "mean_r_multiple": float(np.mean(y_values)),
        "median_r_multiple": float(np.median(y_values)),
        "win_rate": float(np.mean(y_values > 0.0)),
        "sum_r_multiple": float(np.sum(y_values)),
    }


def evaluate_context_threshold(
    timeframe: str,
    archetype: str,
    patterns: Iterable[str],
    threshold: float,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    *,
    random_state: int,
) -> dict[str, object] | None:
    train_subset = train_df[
        (train_df["execution_timeframe"] == timeframe)
        & (train_df["strategy_archetype"] == archetype)
    ]
    test_subset = test_df[
        (test_df["execution_timeframe"] == timeframe)
        & (test_df["strategy_archetype"] == archetype)
    ]
    if len(train_subset) < 50 or len(test_subset) < 30:
        return None
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
            random_state=random_state,
        ),
    )
    pipeline.fit(X_train, (y_train > 0.0).astype(int))
    probabilities = pipeline.predict_proba(X_test)[:, 1]

    baseline = _compute_metrics(y_test)
    filtered_mask = probabilities >= threshold
    filtered = _compute_metrics(y_test[filtered_mask])

    total = max(baseline["count"], 0.0001)
    baseline_fraction = baseline["fraction"] / total
    filtered_fraction = filtered["fraction"] / total

    return {
        "context": f"{timeframe}_{archetype}",
        "baseline_count": baseline["count"],
        "baseline_fraction": baseline_fraction,
        "baseline_mean_r": baseline["mean_r_multiple"],
        "baseline_median_r": baseline["median_r_multiple"],
        "baseline_win_rate": baseline["win_rate"],
        "baseline_sum_r": baseline["sum_r_multiple"],
        "filtered_count": filtered["count"],
        "filtered_fraction": filtered_fraction,
        "filtered_mean_r": filtered["mean_r_multiple"],
        "filtered_median_r": filtered["median_r_multiple"],
        "filtered_win_rate": filtered["win_rate"],
        "filtered_sum_r": filtered["sum_r_multiple"],
        "threshold": float(threshold),
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    recommendations = _load_recommendations(args.recommendations)
    data = load_data(args.enriched_data)
    train_df, test_df = split_data(data)

    rows: list[dict[str, object]] = []
    for _, rec in recommendations.iterrows():
        context = rec["context"]
        if "_" not in context:
            raise ValueError(f"Invalid context format: {context}")
        timeframe, archetype = context.split("_", 1)
        combo = tuple(rec["group_combo"].split("+"))
        threshold = float(rec["threshold"])
        patterns = collect_patterns(combo)
        result = evaluate_context_threshold(
            timeframe,
            archetype,
            patterns,
            threshold,
            train_df,
            test_df,
            random_state=args.random_state,
        )
        if result is None:
            continue
        result["group_combo"] = rec["group_combo"]
        rows.append(result)

    if not rows:
        print("No contexts evaluated. Check data availability.")
        return

    output_path = args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"Wrote threshold backtest results to {output_path}")


__all__ = [
    "parse_args",
    "_load_recommendations",
    "_compute_metrics",
    "evaluate_context_threshold",
    "main",
]
