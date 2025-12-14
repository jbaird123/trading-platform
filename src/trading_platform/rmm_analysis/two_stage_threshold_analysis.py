"""Evaluate two-stage threshold gating rules for profitability predictions."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, cast

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from trading_platform.rmm_analysis.grid_feature_pattern_search import (
    _prepare_xy,
    collect_patterns,
    load_data,
    split_data,
)


@dataclass
class TwoStageRule:
    name: str
    high_threshold: float
    mid_threshold: float
    gating_expression: str


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply two-stage probability thresholds with gating predicates to "
            "profitability predictions and report lift metrics."
        )
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (enriched trades).",
    )
    parser.add_argument(
        "--context",
        required=True,
        type=str,
        help="Context identifier, e.g. 5min_trend_following.",
    )
    parser.add_argument(
        "--group",
        required=True,
        type=str,
        help="Feature group combination name (e.g. structure+momentum).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="CSV path for rule metrics.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed (default: 42).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gb_weighted",
        choices=["logistic", "gb_weighted"],
        help="Classifier to use (default: gb_weighted).",
    )
    return parser.parse_args(argv)


def _rules() -> list[TwoStageRule]:
    return [
        TwoStageRule("tau70", 0.70, 0.70, "true"),
        TwoStageRule("tau55_atr60", 0.70, 0.55, "atr_percentile >= 60"),
        TwoStageRule("tau55_alignment", 0.70, 0.55, "alignment_score > 0"),
        TwoStageRule(
            "tau55_align_atr70",
            0.70,
            0.55,
            "(alignment_score > 0) and (atr_percentile >= 70)",
        ),
        TwoStageRule("tau55_alignfull", 0.70, 0.55, "alignment_full"),
        TwoStageRule(
            "tau60_session",
            0.70,
            0.60,
            "session_london or session_newyork",
        ),
        TwoStageRule(
            "tau55_atr70_session",
            0.70,
            0.55,
            "(atr_percentile >= 70) and (session_london or session_newyork)",
        ),
        TwoStageRule("tau55_vol_ratio", 0.70, 0.55, "volume_ratio >= 1.1"),
        TwoStageRule(
            "tau60_atr65_volume",
            0.70,
            0.60,
            "(atr_percentile >= 65) and (volume_ratio >= 1.0)",
        ),
        TwoStageRule("tau55_momentum", 0.70, 0.55, "prior_return > 0"),
        TwoStageRule(
            "tau60_momentum_alignment",
            0.70,
            0.60,
            "(prior_return > 0) and (alignment_score > 0)",
        ),
    ]


def _gating_frame(df: pd.DataFrame) -> pd.DataFrame:
    columns = {
        "atr_percentile": df[
            "context_at_entry_global_features_15min_" "atr_percentile_100"
        ],
        "session_london": (
            df["context_at_entry_global_features_15min_forex_session_london"] > 0.0
        ),
        "session_newyork": (
            df["context_at_entry_global_features_15min_forex_session_newyork"] > 0.0
        ),
        "alignment_score": df[
            "context_at_entry_global_features_15min_trend_" "alignment_stack_score"
        ],
        "alignment_full": (
            df[
                "context_at_entry_global_features_15min_trend_alignment_full_"
                "alignment"
            ]
            > 0.0
        ),
        "prior_return": df["context_at_entry_global_features_15min_prior_return_1"],
        "volume_ratio": df[
            "context_at_entry_global_features_15min_volume_sma_ratio_20"
        ],
    }
    return pd.DataFrame(columns, index=df.index)


def _eval_expression(expr: str, gating_df: pd.DataFrame) -> np.ndarray:
    if expr.strip().lower() in {"true", "", "none"}:
        return np.ones(len(gating_df), dtype=bool)
    result = cast(pd.Series, gating_df.eval(expr, engine="python"))
    return result.to_numpy(dtype=bool)


def _prepare_context_data(
    df: pd.DataFrame,
    context: str,
) -> tuple[pd.DataFrame, np.ndarray]:
    mask: pd.Series = (
        df["execution_timeframe"] + "_" + df["strategy_archetype"]
    ) == context
    subset = df.loc[mask].copy()
    y = subset["r_multiple"].astype(float).to_numpy()
    return subset, y


def _train_probabilities(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    patterns: Iterable[str],
    model: str,
    *,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    X_train, X_test, y_train, y_test, _ = _prepare_xy(
        train_df,
        test_df,
        patterns,
    )
    y_train_bin = (y_train > 0.0).astype(int)

    model_name = model.lower()
    if model_name == "logistic":
        pipeline = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                random_state=random_state,
            ),
        )
        pipeline.fit(X_train, y_train_bin)
        probabilities = pipeline.predict_proba(X_test)[:, 1]
        return probabilities, y_test

    if model_name == "gb_weighted":
        gb = GradientBoostingClassifier(random_state=random_state)
        pos = y_train_bin.sum()
        neg = len(y_train_bin) - pos
        weight_pos = len(y_train_bin) / (2.0 * pos) if pos > 0 else 1.0
        weight_neg = len(y_train_bin) / (2.0 * neg) if neg > 0 else 1.0
        sample_weight = np.where(y_train_bin == 1, weight_pos, weight_neg)
        gb.fit(X_train, y_train_bin, sample_weight=sample_weight)
        probabilities = gb.predict_proba(X_test)[:, 1]
        return probabilities, y_test

    raise ValueError(f"Unsupported model: {model}")


def _metrics(mask: np.ndarray, y_values: np.ndarray, total: int) -> dict[str, float]:
    if mask.sum() == 0:
        return {
            "selected_count": 0.0,
            "selected_fraction": 0.0,
            "mean_r": float("nan"),
            "median_r": float("nan"),
            "win_rate": float("nan"),
            "sum_r": 0.0,
        }
    selected = y_values[mask]
    return {
        "selected_count": float(mask.sum()),
        "selected_fraction": float(mask.sum()) / float(total),
        "mean_r": float(np.mean(selected)),
        "median_r": float(np.median(selected)),
        "win_rate": float(np.mean(selected > 0.0)),
        "sum_r": float(np.sum(selected)),
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    df = load_data(args.enriched_data)
    train_df, test_df = split_data(df)

    context = args.context
    patterns = collect_patterns(args.group.split("+"))

    train_ctx, _ = _prepare_context_data(train_df, context)
    test_ctx, y_test = _prepare_context_data(test_df, context)
    probabilities, y_test_values = _train_probabilities(
        train_ctx,
        test_ctx,
        patterns,
        model=args.model,
        random_state=args.random_state,
    )

    output_rows: list[dict[str, object]] = []
    total = len(y_test_values)
    baseline = _metrics(np.ones(total, dtype=bool), y_test_values, total)
    gating_df = _gating_frame(test_ctx)

    for rule in _rules():
        gate_mask = _eval_expression(rule.gating_expression, gating_df)
        include_mask = (probabilities >= rule.high_threshold) | (
            (probabilities >= rule.mid_threshold) & gate_mask
        )
        stats = _metrics(include_mask, y_test_values, total)
        output_rows.append(
            {
                "context": context,
                "group_combo": args.group,
                "rule": rule.name,
                "high_threshold": rule.high_threshold,
                "mid_threshold": rule.mid_threshold,
                "gating_expression": rule.gating_expression,
                "baseline_mean_r": baseline["mean_r"],
                "baseline_win_rate": baseline["win_rate"],
                **stats,
            }
        )

    output = pd.DataFrame(output_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(output.to_string(index=False))


__all__ = ["parse_args", "main", "TwoStageRule"]
