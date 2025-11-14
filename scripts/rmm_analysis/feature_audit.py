"""
Feature audit CLI for the RMM research workflow.

Loads the enriched trade dataset once, computes basic quality metrics, and
stores them under a user-provided output directory. The goal is to quickly
confirm whether features are populated, exhibit variance, and look reasonable
before investing in heavier modelling or optimisation.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

try:  # Optional dependency: matplotlib is only required for histograms.
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - matplotlib may be absent in CI
    plt = None


LOGGER = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit feature availability/variance in the trade dataset."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to master_trade_log.parquet (or similar enriched dataset).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write audit results (CSV/JSON/plots).",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        help=(
            "Optional path to a Markdown summary (ideal for a tracked analysis "
            "directory). If provided, a concise report is written here."
        ),
    )
    parser.add_argument(
        "--hist-top-variance",
        default=0,
        type=int,
        help=(
            "Generate histograms for the N highest-variance numeric features. "
            "Requires matplotlib. Set to 0 to disable (default)."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args(argv)


def _load_dataframe(path: Path) -> pd.DataFrame:
    LOGGER.info("Loading dataset: %s", path)
    if not path.exists():
        raise FileNotFoundError(f"Input dataset not found: {path}")
    df = pd.read_parquet(path)
    LOGGER.info("Loaded %d rows, %d columns", len(df), df.shape[1])
    return df


def _save_series(series: pd.Series, path: Path) -> None:
    series.to_csv(path, header=["value"])
    LOGGER.debug("Wrote %s", path)


def _save_dataframe(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path)
    LOGGER.debug("Wrote %s", path)


def _basic_profile(df: pd.DataFrame, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)

    missing = df.isna().mean().sort_values(ascending=False)
    _save_series(missing, out_dir / "missing_fraction.csv")

    inf_counts = np.isinf(df.select_dtypes(include=[np.number])).sum()
    _save_series(inf_counts.sort_values(ascending=False), out_dir / "inf_counts.csv")

    numeric = df.select_dtypes(include=[np.number])
    if not numeric.empty:
        variance = numeric.var().sort_values(ascending=False)
        _save_series(variance, out_dir / "variance.csv")

        stats = numeric.describe().transpose()
        _save_dataframe(stats, out_dir / "describe_numeric.csv")

    summary: dict[str, object] = {
        "row_count": len(df),
        "column_count": df.shape[1],
        "numeric_columns": numeric.shape[1],
        "non_numeric_columns": df.shape[1] - numeric.shape[1],
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    LOGGER.debug("Wrote %s", summary_path)
    return summary


def _check_r_multiple_missing(
    df: pd.DataFrame, out_dir: Path
) -> dict[str, float] | None:
    if "r_multiple" not in df.columns or "initial_stop_loss_price" not in df.columns:
        LOGGER.info(
            "Skipping r_multiple invariant check " "(required columns missing)."
        )
        return None
    missing_by_stop = (
        df.groupby(df["initial_stop_loss_price"].isna())["r_multiple"]
        .apply(lambda s: s.isna().mean())
        .rename({True: "stop_missing", False: "stop_present"})
    )
    missing_by_stop.to_csv(
        out_dir / "missing_r_multiple_by_stop_flag.csv", header=["missing_fraction"]
    )
    overall = float(df["r_multiple"].isna().mean())
    missing_stop = float(missing_by_stop.get("stop_missing", np.nan))
    missing_present = float(missing_by_stop.get("stop_present", np.nan))
    return {
        "overall_missing": overall,
        "missing_when_stop_missing": missing_stop,
        "missing_when_stop_present": missing_present,
    }


def _check_lower_tf_features(
    df: pd.DataFrame, out_dir: Path, base_timeframe: str = "execution_timeframe"
) -> pd.Series | None:
    if base_timeframe not in df.columns:
        LOGGER.info(
            "Skipping lower timeframe feature check "
            "(execution timeframe column missing)."
        )
        return None
    tf_col = df[base_timeframe]
    lower_cols = [
        col for col in df.columns if "_m15_" in col.lower() and df[col].dtype != "O"
    ]
    if not lower_cols:
        LOGGER.info("No lower timeframe (m15) features detected; skipping check.")
        return None
    subset = df.loc[:, lower_cols]
    grouped = subset.isna().groupby(tf_col).mean().mean(axis=1).sort_index()
    grouped.to_csv(
        out_dir / "m15_feature_missing_by_execution_timeframe.csv",
        header=["missing_fraction"],
    )
    return grouped


def _write_markdown_summary(
    path: Path,
    summary: dict[str, object],
    r_multiple_stats: dict[str, float] | None,
    m15_stats: pd.Series | None,
) -> None:
    lines = [
        "# Feature Audit Summary",
        "",
        f"- Rows: {summary['row_count']}",
        (
            "- Columns: "
            f"{summary['column_count']} "
            f"(numeric: {summary['numeric_columns']}, "
            f"non-numeric: {summary['non_numeric_columns']})"
        ),
        "",
    ]
    if r_multiple_stats:
        lines.extend(
            [
                "## r_multiple invariant",
                "",
                "- `r_multiple` missing fraction overall: "
                f"{r_multiple_stats['overall_missing']:.3f}",
                (
                    "- Missing fraction when `initial_stop_loss_price` is "
                    "**missing** (no REM / baseline): "
                    f"{r_multiple_stats['missing_when_stop_missing']:.3f}"
                ),
                (
                    "- Missing fraction when `initial_stop_loss_price` is "
                    "**present** (REM configured): "
                    f"{r_multiple_stats['missing_when_stop_present']:.3f}"
                ),
                "",
                (
                    "Interpretation: missing `r_multiple` is confined to trades "
                    "without a stop-loss (baseline runs)."
                ),
                "",
            ]
        )
    if m15_stats is not None:
        lines.extend(
            [
                "## M15 feature availability",
                "",
                "| Execution Timeframe | Avg. Missing Fraction (M15 features) |",
                "|---------------------|---------------------------------------|",
            ]
        )
        for tf, frac in m15_stats.items():
            lines.append(f"| {tf} | {frac:.3f} |")
        lines.extend(
            [
                "",
                (
                    "Interpretation: M15 features appear only when the strategy "
                    "executes on a compatible (sub-hour) timeframe. Higher "
                    "timeframes legitimately show NaNs."
                ),
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    LOGGER.info("Wrote Markdown summary to %s", path)


def _plot_top_variance_histograms(
    df: pd.DataFrame,
    out_dir: Path,
    top_n: int,
) -> None:
    if top_n <= 0:
        return
    if plt is None:
        LOGGER.warning("matplotlib not available; skipping histogram generation.")
        return

    numeric = df.select_dtypes(include=[np.number])
    if numeric.empty:
        LOGGER.warning("No numeric columns available for histograms.")
        return

    variance = numeric.var().dropna().sort_values(ascending=False)
    columns = variance.index[:top_n]
    plot_dir = out_dir / "histograms"
    plot_dir.mkdir(parents=True, exist_ok=True)

    for column in columns:
        series = numeric[column].dropna()
        if series.empty:
            continue
        plt.figure(figsize=(6, 4))
        plt.hist(series, bins=50, alpha=0.7, color="steelblue")
        plt.title(f"Histogram of {column}")
        plt.xlabel(column)
        plt.ylabel("Frequency")
        plt.tight_layout()
        plot_path = plot_dir / f"{column}.png"
        plt.savefig(plot_path)
        plt.close()
        LOGGER.debug("Wrote %s", plot_path)


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    _setup_logging(args.verbose)
    df = _load_dataframe(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = _basic_profile(df, args.output_dir)
    r_stats = _check_r_multiple_missing(df, args.output_dir)
    m15_stats = _check_lower_tf_features(df, args.output_dir)
    _plot_top_variance_histograms(df, args.output_dir, args.hist_top_variance)
    if args.report_path:
        _write_markdown_summary(args.report_path, summary, r_stats, m15_stats)
    LOGGER.info("Feature audit complete. Results written to %s", args.output_dir)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
