"""Threshold sweep analysis for selected engineered feature combinations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score
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
from scripts.rmm_analysis.train_profitability_selected_groups import (
    _parse_combos,
    _resolve_contexts,
)

DEFAULT_THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate logistic sign predictions across thresholds for selected "
            "feature-group combinations."
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
        help="CSV path for threshold sweep metrics.",
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
        default=",".join(str(t) for t in DEFAULT_THRESHOLDS),
        help=(
            "Comma-separated probability thresholds to evaluate "
            "(default: 0.3,0.4,0.5,0.6,0.7)."
        ),
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=200,
        help="Number of trees for RandomForest baseline (unused but kept for API).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    return parser.parse_args(argv)


def _parse_thresholds(value: str) -> list[float]:
    thresholds: list[float] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        thresholds.append(float(token))
    return thresholds


def evaluate_thresholds(
    y_true: np.ndarray,
    proba: np.ndarray,
    thresholds: Iterable[float],
) -> list[dict[str, float]]:
    metrics: list[dict[str, float]] = []
    y_true_binary = (y_true > 0).astype(int)
    for threshold in thresholds:
        preds = (proba >= threshold).astype(int)
        precision = precision_score(y_true_binary, preds, zero_division=0)
        recall = recall_score(y_true_binary, preds, zero_division=0)
        accuracy = accuracy_score(y_true_binary, preds)
        metrics.append(
            {
                "threshold": float(threshold),
                "precision": float(precision),
                "recall": float(recall),
                "accuracy": float(accuracy),
                "positive_rate": float(np.mean(preds)),
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
            y_train_sign = (y_train > 0).astype(int)
            pipeline.fit(X_train, y_train_sign)
            proba = pipeline.predict_proba(X_test)[:, 1]
            metrics = evaluate_thresholds(y_test, proba, thresholds)
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
        print("No threshold evaluations were produced.")
        return

    output_path = args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_path, index=False)
    print(f"Wrote threshold sweep metrics to {output_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
