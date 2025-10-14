"""Golden Validation Utilities

This module provides standardized utilities for loading and validating
golden test data from TradingView exports. All golden validation tests
MUST use these utilities to ensure consistent behavior.

GOLDEN VALIDATION CONTRACT:
===========================

1. DATA EXPORT RANGES:
   - TradingView exports ALWAYS contain MORE data than the validation range
   - Export includes warmup period (1 month before validation start)
   - Export may include extra data beyond validation end
   - Tests MUST filter to exact validation range from metadata.json

2. WARMUP PERIOD:
   - Hardcoded to 2022-12-01 for hourly strategies
   - Validation period starts 2023-01-01 (1 month after warmup)
   - 100 bars is INSUFFICIENT - use 1 month (~720 bars for hourly)
   - Any OHLCV data before warmup start is IGNORED

3. VALIDATION RANGE FILTERING:
   - Platform trades: Filter by entry_time within [start, end]
   - TradingView trades: Filter by entry_time within [start, end]
   - Date range comes from metadata.json "date_range" field
   - Filtering happens AFTER backtest runs (backtest uses extended data)

4. TIMEZONE REQUIREMENTS:
   - ALL timestamps MUST be UTC (no other timezones allowed)
   - CSV exports use UTC (Reykjavik) timezone from TradingView
   - Validation enforces UTC-only with explicit checks
   - Non-UTC timestamps cause ValidationError

5. TRADE COUNTING:
   - Only count closed trades (exclude "end_of_data" exits)
   - Match on entry_time within validation range
   - Total trades in CSV ≠ validation range trades

For detailed explanation, see: docs/validation/golden_validation_guide.md
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd


class GoldenValidationError(Exception):
    """Raised when golden validation data doesn't meet requirements."""

    pass


# Hardcoded warmup start for hourly strategies
# This is 1 month before validation period start (2023-01-01)
WARMUP_START_HOURLY = pd.Timestamp("2022-12-01", tz="UTC")


def validate_utc_timezone_ohlcv(
    df: pd.DataFrame, datetime_col: str, source_name: str
) -> None:
    """Validates OHLCV datetime has UTC timestamps with 'Z' suffix.

    OHLCV data from TradingView MUST be exported with UTC (Reykjavik)
    timezone, which produces timestamps with 'Z' suffix (e.g.,
    '2023-01-06T19:00:00Z').

    WARNING: Do NOT use UTC (Azores) - it includes DST offsets
    (-01:00) which are NOT pure UTC!

    See: configs/golden_strategies/ema_crossover/UTC_TIMEZONE_REQUIREMENTS.md

    Args:
        df: DataFrame containing datetime column
        datetime_col: Name of datetime column to validate
        source_name: Name of data source (for error messages)

    Raises:
        GoldenValidationError: If non-UTC timestamps are found or have DST offsets
    """
    if datetime_col not in df.columns:
        raise GoldenValidationError(
            f"{source_name}: Column '{datetime_col}' not found in DataFrame"
        )

    # Check if column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df[datetime_col]):
        raise GoldenValidationError(
            f"{source_name}: Column '{datetime_col}' is not a datetime type. "
            f"Got: {df[datetime_col].dtype}"
        )

    # Check timezone
    if df[datetime_col].dt.tz is None:
        raise GoldenValidationError(
            f"{source_name}: Column '{datetime_col}' is timezone-naive. "
            "All OHLCV timestamps MUST be UTC with 'Z' suffix.\n"
            "In TradingView: Settings → Chart → Timezone → 'UTC (Reykjavik)'\n"
            "WARNING: Do NOT use 'UTC (Azores)' - it includes DST offsets!"
        )

    # Verify it's UTC
    tz_name = str(df[datetime_col].dt.tz)
    if tz_name not in ["UTC", "UTC+00:00", "UTC+0"]:
        raise GoldenValidationError(
            f"{source_name}: Column '{datetime_col}' has non-UTC timezone: {tz_name}. "
            "All OHLCV timestamps MUST be UTC.\n"
            "In TradingView: Settings → Chart → Timezone → 'UTC (Reykjavik)'\n"
            "WARNING: Do NOT use 'UTC (Azores)' - it includes DST offsets!"
        )


def load_and_validate_ohlcv(
    file_path: Path,
    validation_range: dict[str, str] | None = None,
    warmup_start: pd.Timestamp = WARMUP_START_HOURLY,
) -> pd.DataFrame:
    """Loads OHLCV data with explicit UTC validation and filtering.

    This function enforces the golden validation contract:
    - Validates all timestamps are UTC
    - Filters to [warmup_start, validation_end] range
    - Ignores any data before warmup_start

    Args:
        file_path: Path to OHLCV CSV file
        validation_range: Dict with 'start' and 'end' keys (validation period)
        warmup_start: Start of warmup period (default: 2022-12-01)

    Returns:
        DataFrame with filtered OHLCV data, UTC timestamps

    Raises:
        GoldenValidationError: If data doesn't meet requirements
    """
    if not file_path.exists():
        raise GoldenValidationError(f"OHLCV file not found: {file_path}")

    # Load data
    df = pd.read_csv(file_path, parse_dates=["time"])

    # Validate UTC timezone (OHLCV files have timezone info in timestamps)
    validate_utc_timezone_ohlcv(df, "time", f"OHLCV({file_path.name})")

    # Set as index
    df = df.set_index("time")
    df.index.name = "timestamp"

    # Add volume column if missing (some exports don't include it)
    if "volume" not in df.columns:
        df["volume"] = 1.0

    # Filter to extended range if validation_range provided
    if validation_range:
        end_date = pd.to_datetime(validation_range["end"], utc=True) + timedelta(
            days=1, seconds=-1
        )

        # CRITICAL: Use warmup_start, not validation start
        # This ensures we have enough data for indicator warmup
        df = df[(df.index >= warmup_start) & (df.index <= end_date)].copy()

        if len(df) == 0:
            raise GoldenValidationError(
                f"No OHLCV data found in range [{warmup_start}, {end_date}]"
            )

    return df


def load_and_validate_tradingview_trades(
    file_path: Path,
    validation_range: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Loads TradingView trades with filtering.

    This function enforces the golden validation contract:
    - ASSUMES all timestamps are UTC (TradingView trades CSV has no timezone info)
    - Filters to validation range by entry_time
    - Excludes open trades
    - Pairs entry/exit rows into single trade rows

    NOTE: TradingView trades CSV does NOT contain timezone information.
    Timestamps are assumed to be in UTC (Reykjavik) based on TradingView
    export settings. Only OHLCV files contain explicit timezone markers
    that can be validated.

    Args:
        file_path: Path to TradingView trades CSV
        validation_range: Dict with 'start' and 'end' keys

    Returns:
        DataFrame with one row per trade, filtered to validation range

    Raises:
        GoldenValidationError: If data doesn't meet requirements
    """
    if not file_path.exists():
        raise GoldenValidationError(f"TradingView trades file not found: {file_path}")

    # Load raw CSV with UTC assumption
    # TradingView trades CSV has no timezone markers, assumed UTC
    df = pd.read_csv(file_path)

    # Parse Date/Time column as UTC
    if "Date/Time" not in df.columns:
        raise GoldenValidationError(
            f"TradingView({file_path.name}): Missing 'Date/Time' column"
        )

    df["Date/Time"] = pd.to_datetime(df["Date/Time"], utc=True)

    # Filter out open trades
    if "Signal" in df.columns:
        df = df[df["Signal"] != "Open"].copy()

    # Parse into trade objects
    trades = []
    if "Trade #" not in df.columns:
        raise GoldenValidationError(
            f"TradingView({file_path.name}): Missing 'Trade #' column"
        )

    trade_numbers = df["Trade #"].unique()

    for trade_num in trade_numbers:
        trade_rows = df[df["Trade #"] == trade_num]

        # Find entry and exit rows
        entry_rows = trade_rows[trade_rows["Type"].str.contains("Entry", case=False)]
        exit_rows = trade_rows[trade_rows["Type"].str.contains("Exit", case=False)]

        if len(entry_rows) == 0 or len(exit_rows) == 0:
            continue

        entry_row = entry_rows.iloc[0]
        exit_row = exit_rows.iloc[0]

        # Determine side
        signal = entry_row.get("Signal", "")
        if "Long" in str(signal):
            side = "long"
        elif "Short" in str(signal):
            side = "short"
        else:
            side = "unknown"

        entry_time = entry_row.get("Date/Time")
        exit_time = exit_row.get("Date/Time")

        # CRITICAL: Filter by validation range BEFORE adding to trades list
        # This ensures we only compare trades that entered during validation
        if validation_range:
            start_date = pd.to_datetime(validation_range["start"], utc=True)
            end_date = pd.to_datetime(validation_range["end"], utc=True)

            if not (start_date <= entry_time <= end_date):
                # Skip trades outside validation period
                continue

        trades.append(
            {
                "trade_num": trade_num,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": entry_row.get("Price USD"),
                "exit_price": exit_row.get("Price USD"),
                "pnl": entry_row.get("Net P&L USD"),
                "side": side,
            }
        )

    return pd.DataFrame(trades)


def filter_platform_trades_to_validation_range(
    trades: list[Any],
    validation_range: dict[str, str],
) -> list[dict]:
    """Filters platform trades to validation range.

    Args:
        trades: List of Trade objects from backtest
        validation_range: Dict with 'start' and 'end' keys

    Returns:
        List of trade dictionaries filtered to validation range
    """
    start_date = pd.to_datetime(validation_range["start"], utc=True)
    end_date = pd.to_datetime(validation_range["end"], utc=True)

    filtered = []
    for trade in trades:
        # Skip force-closed trades (TradingView doesn't close at end)
        if trade.exit_reason == "end_of_data":
            continue

        # Filter by entry_time within validation range
        if start_date <= trade.entry_time <= end_date:
            filtered.append(
                {
                    "entry_time": trade.entry_time,
                    "exit_time": trade.exit_time,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "pnl": trade.pnl,
                    "side": trade.side,
                }
            )

    return filtered
