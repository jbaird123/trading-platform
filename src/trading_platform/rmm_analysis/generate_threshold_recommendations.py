"""Utility to regenerate profitability thresholds and recommendations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

from trading_platform.rmm_analysis import threshold_drawdown_analysis as tda
from trading_platform.rmm_analysis import (
    threshold_drawdown_recommendation_report as tdrr,
)
from trading_platform.rmm_analysis import threshold_profitability_analysis as tpa
from trading_platform.rmm_analysis import threshold_recommendation_report as trr
from trading_platform.rmm_analysis.grid_feature_pattern_search import (
    DEFAULT_TEST_START,
    DEFAULT_TRAIN_END,
    DEFAULT_TRAIN_START,
)

DEFAULT_THRESHOLDS = "0.3,0.4,0.5,0.53,0.6,0.7"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run profitability threshold analysis followed by recommendation "
            "selection, with optional per-context model overrides."
        )
    )
    parser.add_argument(
        "--enriched-data",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (enriched trades).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help=("Directory to write threshold_profitability.csv and " "recommendations."),
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default=DEFAULT_THRESHOLDS,
        help=(
            "Comma-separated probability thresholds to evaluate "
            f"(default: {DEFAULT_THRESHOLDS})."
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default="logistic",
        choices=("logistic", "gb_weighted"),
        help="Default classifier for all contexts (default: logistic).",
    )
    parser.add_argument(
        "--context-model",
        action="append",
        default=None,
        help=(
            "Per-context overrides of the form context=model. "
            "Example: --context-model 5min_trend_following=gb_weighted"
        ),
    )
    parser.add_argument(
        "--context-gate",
        action="append",
        default=None,
        help=(
            "Per-context gating expressions of the form context=expr. "
            "Example: --context-gate 5min_trend_following=alignment_full"
        ),
    )
    parser.add_argument(
        "--context-output",
        action="append",
        default=None,
        help=("Force final recommendation row " "(context=group:model:threshold)."),
    )
    parser.add_argument(
        "--min-selected-fraction",
        type=float,
        default=trr.DEFAULT_MIN_FRACTION,
        help=(
            "Minimum coverage fraction when selecting recommendations "
            f"(default: {trr.DEFAULT_MIN_FRACTION})."
        ),
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--train-start",
        type=str,
        default=None,
        help=f"Inclusive training start date (default: {DEFAULT_TRAIN_START}).",
    )
    parser.add_argument(
        "--train-end",
        type=str,
        default=None,
        help=f"Inclusive training end date (default: {DEFAULT_TRAIN_END}).",
    )
    parser.add_argument(
        "--test-start",
        type=str,
        default=None,
        help=f"Inclusive test start date (default: {DEFAULT_TEST_START}).",
    )
    return parser.parse_args(argv)


def _parse_overrides(pairs: Sequence[str] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if not pairs:
        return overrides
    for pair in pairs:
        if "=" not in pair:
            continue
        ctx, value = pair.split("=", 1)
        overrides[ctx.strip()] = value.strip()
    return overrides


def _parse_output_spec(pairs: Sequence[str] | None) -> dict[str, dict[str, str]]:
    specs: dict[str, dict[str, str]] = {}
    if not pairs:
        return specs
    for pair in pairs:
        if "=" not in pair:
            continue
        ctx, spec = pair.split("=", 1)
        parts = [p.strip() for p in spec.split(":")]
        if len(parts) != 3:
            raise ValueError(
                "Invalid context-output specification "
                f"'{pair}'. Expected format context=group:model:threshold"
            )
        specs[ctx.strip()] = {
            "group": parts[0],
            "model": parts[1],
            "threshold": parts[2],
        }
    return specs


def _apply_outputs_override(
    recommendations_df: pd.DataFrame,
    profitability_df: pd.DataFrame,
    output_overrides: dict[str, dict[str, str]],
) -> pd.DataFrame:
    if not output_overrides:
        return recommendations_df

    result_df = recommendations_df.copy()
    gating_column = "gating_expression"
    if gating_column not in result_df.columns:
        result_df[gating_column] = "true"
    result_df[gating_column] = result_df[gating_column].map(
        lambda x: "true" if pd.isna(x) else str(x).lower()
    )

    for context, spec in output_overrides.items():
        threshold = float(spec["threshold"])
        if "model" in profitability_df.columns:
            model_mask = profitability_df["model"] == spec["model"]
        else:
            model_mask = pd.Series(True, index=profitability_df.index)
        mask = (
            (profitability_df["context"] == context)
            & (profitability_df["group_combo"] == spec["group"])
            & model_mask
            & (profitability_df["threshold"] == threshold)
        )
        if not mask.any():
            raise ValueError(
                "No profitability metrics found for override "
                f"{context}={spec['group']}:{spec['model']}:{threshold}"
            )
        source = profitability_df.loc[mask].iloc[0]
        new_row = {
            "context": context,
            "group_combo": spec["group"],
            "model": spec["model"],
            "threshold": threshold,
            "selected_fraction": source["selected_fraction"],
            "mean_r_multiple_selected": source["mean_r_multiple_selected"],
            "win_rate_selected": source["win_rate_selected"],
            "lift_mean_r_multiple": source["lift_mean_r_multiple"],
            "lift_win_rate": source["lift_win_rate"],
            gating_column: "true",
        }
        existing_mask = result_df["context"] == context
        if existing_mask.any():
            for key, value in new_row.items():
                result_df.loc[existing_mask, key] = value
        else:
            result_df = pd.concat(
                [result_df, pd.DataFrame([new_row])],
                ignore_index=True,
            )
    return result_df


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    profitability_csv = args.output_dir / "threshold_profitability.csv"
    recommendations_csv = args.output_dir / "threshold_recommendations.csv"

    profit_args: list[str] = [
        "--enriched-data",
        str(args.enriched_data),
        "--output-path",
        str(profitability_csv),
        "--thresholds",
        args.thresholds,
        "--model",
        args.model,
        "--random-state",
        str(args.random_state),
    ]
    if args.train_start:
        profit_args.extend(["--train-start", args.train_start])
    if args.train_end:
        profit_args.extend(["--train-end", args.train_end])
    if args.test_start:
        profit_args.extend(["--test-start", args.test_start])
    if args.context_model:
        for override in args.context_model:
            profit_args.extend(["--context-model", override])

    gate_overrides = _parse_overrides(args.context_gate)
    output_overrides = _parse_output_spec(args.context_output)

    tpa.main(profit_args)

    trr_args = [
        "--profitability-csv",
        str(profitability_csv),
        "--output-csv",
        str(recommendations_csv),
        "--min-selected-fraction",
        str(args.min_selected_fraction),
    ]
    trr.main(trr_args)

    profitability_df = pd.read_csv(profitability_csv)
    recommendations_df = pd.read_csv(recommendations_csv)
    recommendations_df = _apply_outputs_override(
        recommendations_df=recommendations_df,
        profitability_df=profitability_df,
        output_overrides=output_overrides,
    )

    gating_column = "gating_expression"
    if gating_column not in recommendations_df.columns:
        recommendations_df[gating_column] = "true"
    recommendations_df[gating_column] = recommendations_df[gating_column].map(
        lambda x: "true" if pd.isna(x) else str(x).lower()
    )

    if gate_overrides:
        for ctx, expr in gate_overrides.items():
            mask = recommendations_df["context"] == ctx
            if mask.any():
                recommendations_df.loc[mask, "gating_expression"] = expr
            else:
                print(
                    f"Warning: gating override '{ctx}' did not match any context",
                    file=sys.stderr,
                )

    recommendations_df.to_csv(recommendations_csv, index=False)

    # Run drawdown-based recommendation analysis (alongside R-multiple recommendations)
    drawdown_csv = args.output_dir / "threshold_drawdown.csv"
    drawdown_recommendations_csv = (
        args.output_dir / "threshold_recommendations_drawdown.csv"
    )

    print("\n--- Drawdown Analysis ---")
    predictions_csv = args.output_dir / "threshold_predictions.csv"

    tda_args = [
        "--predictions-csv",
        str(predictions_csv),
        "--profitability-csv",
        str(profitability_csv),
        "--output-path",
        str(drawdown_csv),
    ]
    try:
        tda.main(tda_args)

        # Generate drawdown-based recommendations
        tdrr_args = [
            "--drawdown-csv",
            str(drawdown_csv),
            "--output-csv",
            str(drawdown_recommendations_csv),
        ]
        tdrr.main(tdrr_args)
    except Exception as e:
        print(f"Warning: Drawdown analysis failed: {e}", file=sys.stderr)
        print("R-multiple recommendations were still generated successfully.")


__all__ = [
    "parse_args",
    "_parse_overrides",
    "_parse_output_spec",
    "_apply_outputs_override",
    "main",
]
