from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def check_time_series_gaps(
    df: pd.DataFrame, max_gap_minutes: int = 1440
) -> list[dict[str, Any]]:
    """
    Check for gaps in time series data.

    Args:
        df: DataFrame with 'timestamp' column
        max_gap_minutes: Maximum allowed gap in minutes

    Returns:
        List of dicts with {start_time, end_time, gap_minutes}
    """
    if "timestamp" not in df.columns or len(df) < 2:
        return []

    df = df.sort_values("timestamp")
    time_diffs = df["timestamp"].diff()

    gaps = []
    for idx in range(1, len(df)):
        diff = time_diffs.iloc[idx]
        # Check if diff is not NaT and is a timedelta
        if diff is not pd.NaT and hasattr(diff, "total_seconds"):
            gap_minutes = diff.total_seconds() / 60
            if gap_minutes > max_gap_minutes:
                gaps.append(
                    {
                        "start_time": df.iloc[idx - 1]["timestamp"],
                        "end_time": df.iloc[idx]["timestamp"],
                        "gap_minutes": gap_minutes,
                    }
                )

    return gaps


def check_timestamp_consistency(df: pd.DataFrame) -> list[str]:
    """
    Check timestamp consistency (monotonic, no duplicates).

    Args:
        df: DataFrame with 'timestamp' column

    Returns:
        List of error messages
    """
    if "timestamp" not in df.columns:
        return ["No 'timestamp' column found"]

    issues = []

    # Check if monotonically increasing
    if not df["timestamp"].is_monotonic_increasing:
        issues.append("Timestamps are not monotonically increasing")

    # Check for duplicates
    duplicates = df["timestamp"].duplicated().sum()
    if duplicates > 0:
        issues.append(f"Found {duplicates} duplicate timestamps")

    return issues


def validate_parquet_file(file_path: Path) -> dict[str, Any]:
    """
    Validate a single parquet file.

    Args:
        file_path: Path to parquet file

    Returns:
        Dict with {file, status, gaps, timestamp_issues, error}
    """
    try:
        df = pd.read_parquet(file_path)

        gaps = check_time_series_gaps(df)
        timestamp_issues = check_timestamp_consistency(df)

        return {
            "file": file_path,
            "status": "valid",
            "gaps": gaps,
            "timestamp_issues": timestamp_issues,
        }
    except Exception as e:
        return {
            "file": file_path,
            "status": "corrupted",
            "error": str(e),
        }


def validate_all_data(data_dir: Path, instruments: list[str]) -> dict[str, Any]:
    """
    Validate all data files for given instruments.

    Args:
        data_dir: Directory containing parquet files
        instruments: List of instrument names to check

    Returns:
        Summary dict with totals and issues
    """
    results = []
    total_files = 0
    total_issues = 0

    for instrument in instruments:
        # Find parquet files for this instrument
        pattern = f"*{instrument}*.parquet"
        files = list(data_dir.glob(pattern))

        for file_path in files:
            total_files += 1
            result = validate_parquet_file(file_path)
            results.append(result)

            if result["status"] == "corrupted":
                total_issues += 1
            elif result.get("gaps") or result.get("timestamp_issues"):
                total_issues += 1

    return {
        "total_files": total_files,
        "total_issues": total_issues,
        "results": results,
        "issues": [
            r
            for r in results
            if r["status"] != "valid" or r.get("gaps") or r.get("timestamp_issues")
        ],
    }
