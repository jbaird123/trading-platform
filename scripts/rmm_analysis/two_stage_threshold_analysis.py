"""Evaluate two-stage threshold rules for profitability predictions."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

if __package__ is None or __package__ == "":  # pragma: no cover - script entrypoint
    import sys

    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

from scripts.rmm_analysis.grid_feature_pattern_search import (  # noqa: E402
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
        TwoStageRule(
            name="tau70",
            high_threshold=0.70,
            mid_threshold=0.70,
            gating_expression="true",
        ),
        TwoStageRule(
            name="tau55_atr60",
            high_threshold=0.70,
            mid_threshold=0.55,
            gating_expression="atr_percentile >= 60",
        ),
        TwoStageRule(
            name="tau55_alignment",
            high_threshold=0.70,
            mid_threshold=0.55,
            gating_expression="alignment_score > 0",
        ),
        TwoStageRule(
            name="tau55_align_atr70",
            high_threshold=0.70,
            mid_threshold=0.55,
            gating_expression="(alignment_score > 0) and (atr_percentile >= 70)",
        ),
        TwoStageRule(
            name="tau55_alignfull",
            high_threshold=0.70,
            mid_threshold=0.55,
            gating_expression="alignment_full",
        ),
        TwoStageRule(
            name="tau60_session",
            high_threshold=0.70,
            mid_threshold=0.60,
            gating_expression="session_london or session_newyork",
        ),
        TwoStageRule(
            name="tau55_atr70_session",
            high_threshold=0.70,
            mid_threshold=0.55,
            gating_expression=(
                "(atr_percentile >= 70) and (session_london or session_newyork)"
            ),
        ),
        TwoStageRule(
            name="tau55_vol_ratio",
            high_threshold=0.70,
            mid_threshold=0.55,
            gating_expression="volume_ratio >= 1.1",
        ),
        TwoStageRule(
            name="tau60_atr65_volume",
            high_threshold=0.70,
            mid_threshold=0.60,
            gating_expression="(atr_percentile >= 65) and (volume_ratio >= 1.0)",
        ),
        TwoStageRule(
            name="tau55_momentum",
            high_threshold=0.70,
            mid_threshold=0.55,
            gating_expression="prior_return > 0",
        ),
        TwoStageRule(
            name="tau60_momentum_alignment",
            high_threshold=0.70,
            mid_threshold=0.60,
            gating_expression="(prior_return > 0) and (alignment_score > 0)",
        ),
    ]


def _gating_frame(df: pd.DataFrame) -> pd.DataFrame:
    columns = {}
    columns["atr_percentile"] = df[
        "context_at_entry_global_features_m15_atr_percentile_100"
    ]
    columns["session_london"] = (
        df["context_at_entry_global_features_m15_calendar_session_london"] > 0.0
    )
    columns["session_newyork"] = (
        df["context_at_entry_global_features_m15_calendar_session_newyork"] > 0.0
    )
    columns["alignment_score"] = df[
        "context_at_entry_global_features_m15_trend_alignment_stack_score"
    ]
    columns["alignment_full"] = (
        df["context_at_entry_global_features_m15_trend_alignment_full_alignment"] > 0.0
    )
    columns["prior_return"] = df["context_at_entry_global_features_m15_prior_return_1"]
    columns["volume_ratio"] = df[
        "context_at_entry_global_features_m15_volume_sma_ratio_20"
    ]
    return pd.DataFrame(columns, index=df.index)


def _eval_expression(expr: str, gating_df: pd.DataFrame) -> np.ndarray:
    if expr.strip().lower() in {"true", "", "none"}:
        return np.ones(len(gating_df), dtype=bool)
    bool_df = gating_df.assign(
        session_london=gating_df["session_london"].astype(bool),
        session_newyork=gating_df["session_newyork"].astype(bool),
    )
    local_vars = {
        "atr_percentile": bool_df["atr_percentile"],
        "session_london": bool_df["session_london"],
        "session_newyork": bool_df["session_newyork"],
        "volume_ratio": bool_df["volume_ratio"],
    }
    return bool_df.eval(expr, local_dict=local_vars).to_numpy(dtype=bool)


def _prepare_context_data(
    df: pd.DataFrame,
    context: str,
) -> tuple[pd.DataFrame, pd.Series]:
    num_mask = (df["execution_timeframe"] + "_" + df["strategy_archetype"]) == context
    subset = df.loc[num_mask].copy()
    y = subset["r_multiple"].astype(float).to_numpy()
    return subset, pd.Series(y, index=subset.index)


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

    model = model.lower()
    if model == "logistic":
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

    if model == "gb_weighted":
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
    timeframe, archetype = context.split("_", 1)
    patterns = collect_patterns(args.group.split("+"))

    train_ctx, _ = _prepare_context_data(train_df, context)
    test_ctx, y_test_series = _prepare_context_data(test_df, context)
    probabilities, y_test = _train_probabilities(
        train_ctx,
        test_ctx,
        patterns,
        model=args.model,
        random_state=args.random_state,
    )

    output_rows: list[dict[str, object]] = []
    total = len(y_test)
    baseline = _metrics(np.ones(total, dtype=bool), y_test, total)

    gating_df = _gating_frame(test_ctx)

    for rule in _rules():
        gate_mask = _eval_expression(rule.gating_expression, gating_df)
        include_mask = (probabilities >= rule.high_threshold) | (
            (probabilities >= rule.mid_threshold) & gate_mask
        )
        stats = _metrics(include_mask, y_test, total)
        result = {
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
        output_rows.append(result)

    output = pd.DataFrame(output_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    print(output.to_string(index=False))


if __name__ == "__main__":  # pragma: no cover
    main()
