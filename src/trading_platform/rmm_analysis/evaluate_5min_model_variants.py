"""Evaluate alternative classifiers for 5min profitability filtering."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from trading_platform.rmm_analysis.grid_feature_pattern_search import (
    _prepare_xy,
    collect_patterns,
    load_data,
    split_data,
)

MODEL_SPECS = {
    "logistic_balanced": "Balanced Logistic Regression",
    "rf_balanced": "RandomForest (class weight balanced)",
    "gb_weighted": "GradientBoosting (sample-weighted)",
}

DEFAULT_THRESHOLDS = [0.5, 0.55, 0.6, 0.65, 0.7]
DEFAULT_MODEL = "logistic"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train different classifiers for the 5min_trend_following context "
            "and compare probability thresholds."
        )
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (enriched trades).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="CSV path for results.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed (default: 42).",
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default=None,
        help="Comma-separated probability thresholds (default: 0.5-0.7).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        choices=["logistic", "gb_weighted"],
        help="Classifier to evaluate (default: logistic).",
    )
    parser.add_argument(
        "--gating",
        type=str,
        default="true",
        help=(
            "Optional gating expression (pandas.eval syntax). Columns available: "
            "atr_percentile, volume_ratio, prior_return, alignment_score, "
            "alignment_full, session_london, session_newyork."
        ),
    )
    parser.add_argument(
        "--extra-output",
        type=Path,
        default=None,
        help="Optional CSV path for augmented output.",
    )
    return parser.parse_args(argv)


def parse_thresholds(arg: str | None) -> list[float]:
    if arg is None:
        return DEFAULT_THRESHOLDS
    values = [float(token.strip()) for token in arg.split(",") if token.strip()]
    return values or DEFAULT_THRESHOLDS


def _context_mask(df: pd.DataFrame, context: str) -> pd.Series:
    return (df["execution_timeframe"] + "_" + df["strategy_archetype"]) == context


def _extract_context(df: pd.DataFrame, context: str) -> pd.DataFrame:
    mask = _context_mask(df, context)
    return df.loc[mask].copy()


def _train_models(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    patterns: Iterable[str],
    *,
    random_state: int,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    X_train, X_test, y_train, y_test, _ = _prepare_xy(train_df, test_df, patterns)
    y_train_bin = (y_train > 0.0).astype(int)

    models: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    log_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=random_state,
        ),
    )
    log_model.fit(X_train, y_train_bin)
    models["logistic_balanced"] = (log_model.predict_proba(X_test)[:, 1], y_test)

    rf = RandomForestClassifier(
        n_estimators=500,
        max_depth=None,
        random_state=random_state,
        n_jobs=-1,
        class_weight="balanced",
    )
    rf.fit(X_train, y_train_bin)
    models["rf_balanced"] = (rf.predict_proba(X_test)[:, 1], y_test)

    gb = GradientBoostingClassifier(random_state=random_state)
    pos = y_train_bin.sum()
    neg = len(y_train_bin) - pos
    weight_pos = len(y_train_bin) / (2.0 * pos) if pos > 0 else 1.0
    weight_neg = len(y_train_bin) / (2.0 * neg) if neg > 0 else 1.0
    sample_weight = np.where(y_train_bin == 1, weight_pos, weight_neg)
    gb.fit(X_train, y_train_bin, sample_weight=sample_weight)
    models["gb_weighted"] = (gb.predict_proba(X_test)[:, 1], y_test)

    return models


def _classification_metrics(proba: np.ndarray, y_test: np.ndarray) -> dict[str, float]:
    y_true = (y_test > 0).astype(int)
    predictions = (proba >= 0.5).astype(int)
    acc = accuracy_score(y_true, predictions)
    precision = precision_score(y_true, predictions, zero_division=0)
    recall = recall_score(y_true, predictions, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y_true, predictions).ravel()
    try:
        auc = roc_auc_score(y_true, proba)
    except ValueError:
        auc = float("nan")
    return {
        "logistic_accuracy": float(acc),
        "logistic_precision": float(precision),
        "logistic_recall": float(recall),
        "logistic_auc": float(auc),
        "tp": float(tp),
        "fp": float(fp),
        "tn": float(tn),
        "fn": float(fn),
    }


def _threshold_metrics(
    proba: np.ndarray,
    y_test: np.ndarray,
    thresholds: Iterable[float],
) -> list[dict[str, float]]:
    y_values = y_test.astype(float)
    total = len(y_values)
    baseline_mean = float(np.mean(y_values))
    baseline_win = float(np.mean(y_values > 0.0))
    rows: list[dict[str, float]] = []
    for tau in thresholds:
        mask = proba >= tau
        selected = y_values[mask]
        if len(selected) == 0:
            mean_r = float("nan")
            win_rate = float("nan")
            sum_r = 0.0
        else:
            mean_r = float(np.mean(selected))
            win_rate = float(np.mean(selected > 0.0))
            sum_r = float(np.sum(selected))
        rows.append(
            {
                "threshold": float(tau),
                "selected_fraction": float(mask.sum()) / float(total),
                "mean_r": mean_r,
                "win_rate": win_rate,
                "sum_r": sum_r,
                "lift_mean_r": mean_r - baseline_mean
                if len(selected)
                else float("nan"),
                "lift_win_rate": win_rate - baseline_win
                if len(selected)
                else float("nan"),
            }
        )
    return rows


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    data = load_data(args.enriched_data)
    train_df, test_df = split_data(data)

    context = "5min_trend_following"
    patterns = collect_patterns("structure+momentum".split("+"))

    train_ctx = _extract_context(train_df, context)
    test_ctx = _extract_context(test_df, context)
    models = _train_models(
        train_ctx, test_ctx, patterns, random_state=args.random_state
    )

    threshold_values = parse_thresholds(args.thresholds)

    results: list[dict[str, object]] = []
    for key, (proba, y_test) in models.items():
        metrics = _classification_metrics(proba, y_test)
        threshold_rows = _threshold_metrics(proba, y_test, threshold_values)
        for row in threshold_rows:
            results.append(
                {
                    "model": key,
                    **metrics,
                    **row,
                }
            )

    df = pd.DataFrame(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(df.to_string(index=False))


__all__ = ["parse_args", "parse_thresholds", "main", "MODEL_SPECS"]
