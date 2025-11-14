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
from typing import Hashable, Sequence

import numpy as np
import pandas as pd

NUM_SAMPLE_ROWS = 10
COL_WIDTH = 24
INDENT = "      "


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
    column: str,
    new_series: pd.Series,
    golden_series: pd.Series,
    row_ids: pd.Series | None,
    entry_times: pd.Series | None,
    entry_label: str | None,
) -> str:
    new_isna = new_series.isna()
    golden_isna = golden_series.isna()
    nan_mismatch = new_isna ^ golden_isna

    abs_diff = (new_series - golden_series).abs()
    value_mismatch = (~new_isna & ~golden_isna) & (abs_diff > 0)
    diff_mask = nan_mismatch | value_mismatch
    diff_count = int(diff_mask.sum())
    if diff_count == 0:
        return f"  ⋅ {column}: no differences"

    max_diff = abs_diff[value_mismatch].max() if value_mismatch.any() else float("nan")
    mean_diff = (
        abs_diff[value_mismatch].mean() if value_mismatch.any() else float("nan")
    )
    samples = (
        pd.DataFrame(
            {
                "new": new_series,
                "golden": golden_series,
                "abs_diff": abs_diff,
                "is_nan_mismatch": nan_mismatch,
            }
        )
        .loc[diff_mask]
        .sort_values(
            ["is_nan_mismatch", "abs_diff"],
            ascending=[True, False],
        )
        .head(NUM_SAMPLE_ROWS)
    )

    header_cols = ["trade#"]
    include_entry = entry_times is not None
    if include_entry:
        header_cols.append(entry_label or "entry_time")
    header_cols += ["new", "golden", "Δ"]

    lines = [
        f"  ⋅ {column}: {diff_count} differing row(s)",
        _format_table_header(header_cols),
    ]
    for idx, row in samples.iterrows():
        idx_key: Hashable = idx
        trade_no = row_ids.at[idx_key] if row_ids is not None else ""
        if include_entry and entry_times is not None:
            entry_val = _normalize_value(entry_times.at[idx_key])
        else:
            entry_val = ""
        new_val = _normalize_value(row["new"])
        golden_val = _normalize_value(row["golden"])
        diff_val = row["abs_diff"] if not row["is_nan_mismatch"] else np.nan
        display_diff = (
            "nan" if row["is_nan_mismatch"] else f"{_normalize_value(diff_val):.6g}"
        )
        if include_entry:
            lines.append(
                _format_row(trade_no, entry_val, new_val, golden_val, display_diff)
            )
        else:
            lines.append(_format_row(trade_no, new_val, golden_val, display_diff))

    if value_mismatch.any():
        lines.append(
            f"{INDENT}Δ stats (excluding NaN mismatches): "
            f"max={max_diff:.6g}, mean={mean_diff:.6g}"
        )
    return "\n".join(lines)


def summarize_non_numeric(
    column: str,
    new_series: pd.Series,
    golden_series: pd.Series,
    row_ids: pd.Series | None,
    entry_times: pd.Series | None,
    entry_label: str | None,
) -> str:
    new_isna = new_series.isna()
    golden_isna = golden_series.isna()
    both_na = new_isna & golden_isna
    nan_mismatch = new_isna ^ golden_isna
    value_diff = (~both_na) & (new_series != golden_series)
    diff_mask = nan_mismatch | value_diff
    count = int(diff_mask.sum())
    if count == 0:
        return f"  ⋅ {column}: no differences"
    samples = (
        pd.DataFrame({"new": new_series, "golden": golden_series})
        .loc[diff_mask]
        .head(NUM_SAMPLE_ROWS)
    )
    header_cols = ["trade#"]
    include_entry = entry_times is not None
    if include_entry:
        header_cols.append(entry_label or "entry_time")
    header_cols += ["new", "golden"]

    lines = [
        f"  ⋅ {column}: {count} differing row(s)",
        _format_table_header(header_cols),
    ]
    for idx, row in samples.iterrows():
        idx_key: Hashable = idx
        trade_no = row_ids.at[idx_key] if row_ids is not None else ""
        if include_entry and entry_times is not None:
            entry_val = _normalize_value(entry_times.at[idx_key])
        else:
            entry_val = ""
        new_val = _normalize_value(row["new"])
        golden_val = _normalize_value(row["golden"])
        if include_entry:
            lines.append(_format_row(trade_no, entry_val, new_val, golden_val))
        else:
            lines.append(_format_row(trade_no, new_val, golden_val))
    return "\n".join(lines)


def _normalize_value(value):
    if isinstance(value, (np.generic,)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


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
        print("Column order differs. First mismatched positions:")
        max_len = max(len(new_cols), len(golden_cols))
        mismatch_rows: list[tuple[int, str | None, str | None]] = []
        for idx in range(max_len):
            new_col = new_cols[idx] if idx < len(new_cols) else None
            golden_col = golden_cols[idx] if idx < len(golden_cols) else None
            if new_col != golden_col:
                mismatch_rows.append((idx, new_col, golden_col))
            if len(mismatch_rows) >= NUM_SAMPLE_ROWS:
                break
        if mismatch_rows:
            for idx, new_col, golden_col in mismatch_rows:
                print(f"  idx {idx}: new={new_col!r} " f"golden={golden_col!r}")
        else:
            print("  (No mismatch within preview window.)")

    aligned_index = new_idx.intersection(golden_idx)
    aligned_new = new_df.loc[aligned_index, common_cols]
    aligned_golden = golden_df.loc[aligned_index, common_cols]

    row_id_series: pd.Series | None = None
    if not aligned_new.empty:
        row_id_series = pd.Series(
            range(1, len(aligned_new) + 1), index=aligned_new.index
        )
    entry_col, entry_time_series = _detect_entry_series(aligned_new)

    print("\nPer-column discrepancies:")
    for col in common_cols:
        new_series = aligned_new[col]
        golden_series = aligned_golden[col]
        if (
            pd.api.types.is_numeric_dtype(new_series)
            and pd.api.types.is_numeric_dtype(golden_series)
            and not (
                pd.api.types.is_bool_dtype(new_series)
                or pd.api.types.is_bool_dtype(golden_series)
            )
        ):
            print(
                summarize_numeric(
                    col,
                    new_series,
                    golden_series,
                    row_id_series,
                    entry_time_series,
                    entry_col,
                )
            )
        else:
            print(
                summarize_non_numeric(
                    col,
                    new_series,
                    golden_series,
                    row_id_series,
                    entry_time_series,
                    entry_col,
                )
            )


def _detect_entry_series(
    df: pd.DataFrame,
) -> tuple[str | None, pd.Series | None]:
    candidates = ["entry_time", "platform_entry_time"]
    for name in candidates:
        if name in df.columns:
            return name, df[name]
    idx = df.index
    if isinstance(idx, pd.MultiIndex):
        for name in candidates:
            if name in idx.names:
                return name, pd.Series(idx.get_level_values(name), index=idx)
    else:
        for name in candidates:
            if idx.name == name:
                return name, pd.Series(idx, index=idx)
    return None, None


def _format_table_header(columns: Sequence[str]) -> str:
    header = _format_row(*columns)
    divider = _format_row(*["-" * (COL_WIDTH - 2) for _ in columns])
    return "\n".join([header, divider])


def _format_row(*values) -> str:
    def render(value: object) -> str:
        return f"{str(value):<{COL_WIDTH}}"

    return INDENT + " ".join(render(v) for v in values)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
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


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    compare_paths(args.new, args.golden, args.index)


def compare_paths(
    new_path: Path, golden_path: Path, index_cols: list[str] | None = None
) -> None:
    new_df = ensure_index(load_frame(new_path), index_cols)
    golden_df = ensure_index(load_frame(golden_path), index_cols)
    compare_frames(new_df, golden_df)


if __name__ == "__main__":
    main()
