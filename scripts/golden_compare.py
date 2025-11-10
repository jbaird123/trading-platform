#!/usr/bin/env python3
"""Compare two tabular golden files and highlight discrepancies.

The script accepts any combination of CSV/Parquet inputs, aligns rows by an
optional index column list (or by positional order when no key is provided),
and reports:
  • row-count differences and rows unique to each file
  • missing/extra columns and column-order mismatches
  • per-column discrepancy summaries, including the top-N worst deltas for
    numeric columns and representative samples for non-numeric columns.

Example usage:
    poetry run python scripts/golden_compare.py \
        --new path/to/new.csv \
        --golden path/to/golden.csv \
        --index entry_time exit_time side
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd

NUM_SAMPLE_ROWS = 10


def load_frame(path: Path) -> pd.DataFrame:
    """Load a CSV or Parquet file into a DataFrame."""

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {path}")


def ensure_index(df: pd.DataFrame, index_cols: list[str] | None) -> pd.DataFrame:
    if index_cols:
        missing = [col for col in index_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing index column(s) {missing} in dataframe")
        return df.set_index(index_cols)
    return df.set_index(pd.RangeIndex(len(df)))


def summarize_numeric(
    column: str, new_series: pd.Series, golden_series: pd.Series
) -> str:
    abs_diff = (new_series - golden_series).abs()
    summary_lines = [
        (
            f"  ⋅ {column}: max_diff={abs_diff.max():.6g}, "
            f"mean_diff={abs_diff.mean():.6g}, rows={abs_diff.count()}"
        ),
    ]
    if not abs_diff.dropna().empty:
        samples = (
            pd.DataFrame(
                {
                    "new": new_series,
                    "golden": golden_series,
                    "abs_diff": abs_diff,
                }
            )
            .sort_values("abs_diff", ascending=False)
            .head(NUM_SAMPLE_ROWS)
        )
        summary_lines.append("    top discrepancies:")
        summary_lines.extend(
            [
                (
                    f"      {idx}: new={row['new']!r} golden={row['golden']!r} "
                    f"diff={row['abs_diff']:.6g}"
                )
                for idx, row in samples.iterrows()
            ]
        )
    return "\n".join(summary_lines)


def summarize_non_numeric(
    column: str, new_series: pd.Series, golden_series: pd.Series
) -> str:
    diff_mask = new_series != golden_series
    count = int(diff_mask.sum())
    if count == 0:
        return f"  ⋅ {column}: no differences"
    samples = (
        pd.DataFrame({"new": new_series, "golden": golden_series})
        .loc[diff_mask]
        .head(NUM_SAMPLE_ROWS)
    )
    lines = [f"  ⋅ {column}: {count} differing row(s)"]
    lines.append("    sample discrepancies:")
    lines.extend(
        [
            f"      {idx}: new={row['new']!r} golden={row['golden']!r}"
            for idx, row in samples.iterrows()
        ]
    )
    return "\n".join(lines)


def compare_frames(new_df: pd.DataFrame, golden_df: pd.DataFrame) -> None:
    new_idx = new_df.index
    golden_idx = golden_df.index
    new_only = sorted(set(new_idx) - set(golden_idx))
    golden_only = sorted(set(golden_idx) - set(new_idx))

    print("Row counts:")
    print(f"  new={len(new_df)} rows")
    print(f"  golden={len(golden_df)} rows")
    if new_only:
        print(
            "  rows only in new (showing up to "
            f"{NUM_SAMPLE_ROWS}): {new_only[:NUM_SAMPLE_ROWS]}"
        )
    if golden_only:
        print(
            "  rows only in golden (showing up to "
            f"{NUM_SAMPLE_ROWS}): {golden_only[:NUM_SAMPLE_ROWS]}"
        )

    new_cols = list(new_df.columns)
    golden_cols = list(golden_df.columns)
    missing_cols = [col for col in golden_cols if col not in new_cols]
    extra_cols = [col for col in new_cols if col not in golden_cols]
    if missing_cols:
        print(f"Missing columns (only in golden): {missing_cols}")
    if extra_cols:
        print(f"Extra columns (only in new): {extra_cols}")

    common_cols = [col for col in golden_cols if col in new_cols]
    if not common_cols:
        print("No overlapping columns to compare.")
        return

    if new_cols != golden_cols:
        print("Column order differs. First few common columns in each:")
        print(f"  new:    {new_cols[:NUM_SAMPLE_ROWS]}")
        print(f"  golden: {golden_cols[:NUM_SAMPLE_ROWS]}")

    aligned_new = new_df.loc[new_idx.intersection(golden_idx), common_cols]
    aligned_golden = golden_df.loc[new_idx.intersection(golden_idx), common_cols]

    print("\nPer-column discrepancies:")
    for col in common_cols:
        new_series = aligned_new[col]
        golden_series = aligned_golden[col]
        if pd.api.types.is_numeric_dtype(new_series) and pd.api.types.is_numeric_dtype(
            golden_series
        ):
            print(summarize_numeric(col, new_series, golden_series))
        else:
            print(summarize_non_numeric(col, new_series, golden_series))


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", required=True, type=Path, help="Path to the new file")
    parser.add_argument(
        "--golden", required=True, type=Path, help="Path to the golden reference file"
    )
    parser.add_argument(
        "--index",
        nargs="*",
        help="Optional list of columns to use as the comparison index",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    new_df = ensure_index(load_frame(args.new), args.index)
    golden_df = ensure_index(load_frame(args.golden), args.index)
    compare_frames(new_df, golden_df)


if __name__ == "__main__":
    main()
