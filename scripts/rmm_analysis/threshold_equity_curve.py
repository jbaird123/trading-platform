"""Generate equity curves for baseline vs. threshold-filtered trades."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Produce equity curves for recommended thresholds."
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
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for equity curve CSV files.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random state for logistic regression.",
    )
    return parser.parse_args(argv)


def load_recommendations(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"context", "group_combo", "threshold"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Recommendation file missing columns: {missing}")
    return df


def equity_curve(
    r_values: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    included = probabilities >= threshold
    baseline = np.cumsum(r_values)
    filtered = np.cumsum(r_values * included)
    return included, baseline, filtered


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    recommendations = load_recommendations(args.recommendations)
    data = load_data(args.enriched_data)
    train_df, test_df = split_data(data)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for _, rec in recommendations.iterrows():
        context = rec["context"]
        if "_" not in context:
            raise ValueError(f"Invalid context format: {context}")
        timeframe, archetype = context.split("_", 1)
        combo = tuple(rec["group_combo"].split("+"))
        threshold = float(rec["threshold"])
        patterns = collect_patterns(combo)

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

        test_subset = test_subset.sort_values("entry_time").copy()
        train_subset = train_subset.sort_values("entry_time").copy()

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

        included, baseline_equity, filtered_equity = equity_curve(
            y_test,
            probabilities,
            threshold,
        )

        curve_df = pd.DataFrame(
            {
                "entry_time": test_subset["entry_time"].to_numpy(),
                "r_multiple": y_test,
                "probability": probabilities,
                "included": included.astype(int),
                "baseline_equity": baseline_equity,
                "filtered_equity": filtered_equity,
            }
        )
        context_dir = output_dir / context
        context_dir.mkdir(parents=True, exist_ok=True)
        path = context_dir / "equity_curve.csv"
        curve_df.to_csv(path, index=False)
        print(f"Wrote equity curve for {context} to {path}")


if __name__ == "__main__":  # pragma: no cover
    main()
