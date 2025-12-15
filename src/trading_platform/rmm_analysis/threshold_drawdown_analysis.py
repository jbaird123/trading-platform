"""Drawdown-based threshold analysis for profitability model gating.

This module computes drawdown metrics for each (context, threshold) combination
by analyzing equity curves per run_id, then aggregating across runs.

Unlike the R-multiple based recommendations, this prioritizes short drawdown duration.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute drawdown metrics for thresholded predictions, "
            "analyzing equity curves per run_id."
        )
    )
    parser.add_argument(
        "--predictions-csv",
        required=True,
        type=Path,
        help=(
            "Path to threshold_predictions.csv (exported from profitability analysis)."
        ),
    )
    parser.add_argument(
        "--profitability-csv",
        required=True,
        type=Path,
        help="Path to threshold_profitability.csv (to get threshold list).",
    )
    parser.add_argument(
        "--output-path",
        required=True,
        type=Path,
        help="CSV path for drawdown metrics per (context, threshold).",
    )
    return parser.parse_args(argv)


def compute_drawdown_duration_days(equity_series: pd.Series) -> dict[str, float]:
    """Calculate drawdown metrics from an equity curve.

    Args:
        equity_series: Series of cumulative PnL indexed by datetime.

    Returns:
        Dictionary with max_drawdown_duration_days, avg_drawdown_duration_days,
        max_drawdown_pct, and time_in_drawdown_pct.
    """
    if len(equity_series) < 2:
        return {
            "max_drawdown_duration_days": np.nan,
            "avg_drawdown_duration_days": np.nan,
            "max_drawdown_pct": np.nan,
            "time_in_drawdown_pct": np.nan,
            "num_drawdown_periods": 0,
        }

    peak = equity_series.expanding().max()
    drawdown = equity_series - peak

    # Find drawdown periods
    in_drawdown = drawdown < 0
    time_in_drawdown_pct = float(in_drawdown.mean())

    # Calculate max drawdown percentage (relative to peak)
    # Avoid division by zero
    with np.errstate(divide="ignore", invalid="ignore"):
        dd_pct = np.where(peak != 0, drawdown / peak, 0)
    max_drawdown_pct = float(np.nanmin(dd_pct))

    # Find drawdown period durations
    drawdown_periods: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    start: pd.Timestamp | None = None

    for idx, is_dd in in_drawdown.items():
        if is_dd and start is None:
            start = idx  # type: ignore[assignment]
        elif not is_dd and start is not None:
            drawdown_periods.append((start, idx))  # type: ignore[arg-type]
            start = None

    # Handle case where we end in drawdown
    if start is not None:
        drawdown_periods.append((start, equity_series.index[-1]))

    if not drawdown_periods:
        return {
            "max_drawdown_duration_days": 0.0,
            "avg_drawdown_duration_days": 0.0,
            "max_drawdown_pct": max_drawdown_pct,
            "time_in_drawdown_pct": time_in_drawdown_pct,
            "num_drawdown_periods": 0,
        }

    # Calculate durations in days
    durations_days = []
    for dd_start, dd_end in drawdown_periods:
        duration = (dd_end - dd_start).total_seconds() / 86400  # seconds to days
        durations_days.append(duration)

    return {
        "max_drawdown_duration_days": max(durations_days),
        "avg_drawdown_duration_days": sum(durations_days) / len(durations_days),
        "max_drawdown_pct": max_drawdown_pct,
        "time_in_drawdown_pct": time_in_drawdown_pct,
        "num_drawdown_periods": len(drawdown_periods),
    }


def analyze_drawdown_for_run(
    run_trades: pd.DataFrame,
    threshold: float,
    probability_column: str = "probability",
) -> dict[str, float]:
    """Analyze drawdown for a single run at a given threshold.

    Args:
        run_trades: DataFrame of trades for a single run_id, sorted by entry_time.
        threshold: Probability threshold for trade selection.
        probability_column: Column with predicted probabilities.

    Returns:
        Dictionary with drawdown metrics for this run/threshold.
    """
    if probability_column in run_trades.columns:
        selected = run_trades[run_trades[probability_column] >= threshold].copy()
    else:
        # Should not happen with exported predictions
        selected = pd.DataFrame()

    if len(selected) < 2:
        return {
            "n_trades_selected": len(selected),
            "max_drawdown_duration_days": np.nan,
            "avg_drawdown_duration_days": np.nan,
            "max_drawdown_pct": np.nan,
            "time_in_drawdown_pct": np.nan,
            "num_drawdown_periods": 0,
            "total_pnl": selected["pnl"].sum() if len(selected) > 0 else 0.0,
        }

    # Build equity curve
    selected = selected.sort_values("entry_time")
    selected["cumulative_pnl"] = selected["pnl"].cumsum()

    equity_series = pd.Series(
        selected["cumulative_pnl"].values,
        index=pd.to_datetime(selected["entry_time"]),
    )

    dd_metrics = compute_drawdown_duration_days(equity_series)

    return {
        "n_trades_selected": len(selected),
        "total_pnl": float(selected["pnl"].sum()),
        **dd_metrics,
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    # Load data
    df = pd.read_csv(args.predictions_csv)
    profitability_df = pd.read_csv(args.profitability_csv)

    # Ensure columns
    if "probability" not in df.columns:
        raise ValueError("Input predictions CSV must have 'probability' column.")

    # Get unique thresholds from profitability analysis
    thresholds = sorted(profitability_df["threshold"].unique())

    probability_column = "probability"

    # Analyze drawdown per (run_id, threshold)
    run_results: list[dict[str, object]] = []

    unique_runs = df["run_id"].unique()
    print(f"Analyzing {len(unique_runs)} runs across {len(thresholds)} thresholds...")

    # Check if group_combo and model columns exist in predictions
    has_group_combo = "group_combo" in df.columns
    has_model = "model" in df.columns

    if has_group_combo and has_model:
        # Group by run_id, group_combo, model for full granularity
        unique_combos = df[["run_id", "group_combo", "model"]].drop_duplicates()
        print(
            f"Analyzing {len(unique_combos)} (run, group, model) combinations "
            f"across {len(thresholds)} thresholds..."
        )
        for _, combo_row in unique_combos.iterrows():
            run_id = combo_row["run_id"]
            group_combo = combo_row["group_combo"]
            model = combo_row["model"]

            run_trades = df[
                (df["run_id"] == run_id)
                & (df["group_combo"] == group_combo)
                & (df["model"] == model)
            ].copy()

            if len(run_trades) < 5:
                continue

            timeframe = run_trades["execution_timeframe"].iloc[0]
            archetype = run_trades["strategy_archetype"].iloc[0]
            context = f"{timeframe}_{archetype}"

            for threshold in thresholds:
                metrics = analyze_drawdown_for_run(
                    run_trades, threshold, probability_column
                )
                run_results.append(
                    {
                        "run_id": run_id,
                        "context": context,
                        "group_combo": group_combo,
                        "model": model,
                        "threshold": threshold,
                        **metrics,
                    }
                )
    else:
        # Fallback: legacy behavior without group_combo/model
        for run_id in unique_runs:
            run_trades = df[df["run_id"] == run_id].copy()

            if len(run_trades) < 5:
                continue

            # Extract context from run_id or from data
            # run_id format: "strategy_campaign_timeframe_index_symbol"
            # or we can get it from execution_timeframe + strategy_archetype
            timeframe = run_trades["execution_timeframe"].iloc[0]
            archetype = run_trades["strategy_archetype"].iloc[0]
            context = f"{timeframe}_{archetype}"

            for threshold in thresholds:
                metrics = analyze_drawdown_for_run(
                    run_trades, threshold, probability_column
                )
                run_results.append(
                    {
                        "run_id": run_id,
                        "context": context,
                        "threshold": threshold,
                        **metrics,
                    }
                )

    if not run_results:
        print("No runs analyzed. Check data.")
        return

    run_df = pd.DataFrame(run_results)

    # Aggregate by (context, group_combo, model, threshold) or (context, threshold)
    agg_results: list[dict[str, object]] = []

    if has_group_combo and has_model:
        groupby_cols = ["context", "group_combo", "model", "threshold"]
    else:
        groupby_cols = ["context", "threshold"]

    for group_keys, group in run_df.groupby(groupby_cols):
        valid_runs = group.dropna(subset=["max_drawdown_duration_days"])

        if len(valid_runs) == 0:
            continue

        if has_group_combo and has_model:
            context, group_combo, model, threshold = group_keys
            agg_row: dict[str, object] = {
                "context": context,
                "group_combo": group_combo,
                "model": model,
                "threshold": threshold,
            }
        else:
            context, threshold = group_keys
            agg_row = {
                "context": context,
                "threshold": threshold,
            }

        agg_row.update(
            {
                "n_runs": len(valid_runs),
                "median_max_dd_duration_days": valid_runs[
                    "max_drawdown_duration_days"
                ].median(),
                "max_max_dd_duration_days": valid_runs[
                    "max_drawdown_duration_days"
                ].max(),
                "mean_max_dd_duration_days": valid_runs[
                    "max_drawdown_duration_days"
                ].mean(),
                "median_time_in_dd_pct": valid_runs["time_in_drawdown_pct"].median(),
                "mean_total_pnl": valid_runs["total_pnl"].mean(),
                "median_n_trades": valid_runs["n_trades_selected"].median(),
            }
        )
        agg_results.append(agg_row)

    if not agg_results:
        print("No aggregated results. Check threshold profitability data.")
        return

    agg_df = pd.DataFrame(agg_results)

    # Save output
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    agg_df.to_csv(args.output_path, index=False)
    print(f"Wrote drawdown metrics to {args.output_path}")

    # Also save per-run details for debugging
    run_output = args.output_path.parent / "threshold_drawdown_per_run.csv"
    run_df.to_csv(run_output, index=False)
    print(f"Wrote per-run details to {run_output}")


__all__ = [
    "parse_args",
    "compute_drawdown_duration_days",
    "analyze_drawdown_for_run",
    "main",
]
