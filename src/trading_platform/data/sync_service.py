"""Data synchronization service for automated market data updates."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd


def get_last_sync_date(files: list[Path]) -> date | None:
    """Extract the most recent 'toDate' from a list of data filenames.

    Args:
        files: List of Path objects representing data files with date ranges

    Returns:
        The most recent end date found in the filenames, or None if no dates found

    Example:
        Given files like ['eurusd_interval_min_1_20240101_20240531.csv'],
        extracts and returns date(2024, 5, 31)
    """
    if not files:
        return None

    # Pattern to match the date range in filenames like:
    # eurusd_interval_min_1_20240101_20240531.csv
    # Group 2 captures the 'toDate' (second date)
    date_pattern = r"(\d{8})_(\d{8})"

    latest_date = None

    for file_path in files:
        filename = file_path.name
        match = re.search(date_pattern, filename)

        if match:
            # Extract the toDate (second date group)
            to_date_str = match.group(2)

            # Parse the date string (YYYYMMDD format)
            try:
                file_date = datetime.strptime(to_date_str, "%Y%m%d").date()

                # Keep track of the most recent date
                if latest_date is None or file_date > latest_date:
                    latest_date = file_date

            except ValueError:
                # Skip files with invalid date formats
                continue

    return latest_date


def verify_data_continuity(
    symbol: str, data_root: Path, new_file_path: Path
) -> None:
    """Verify data continuity between existing files and newly downloaded data.
    
    Checks for unexpected gaps during normal forex market hours while allowing
    expected weekend market closures.
    
    Args:
        symbol: The financial instrument symbol (e.g., "EUR/USD")
        data_root: Root directory where data files are stored
        new_file_path: Path to the newly created incremental file
        
    Raises:
        RuntimeError: If an unexpected data gap is detected during market hours
    """
    normalized_symbol = symbol.replace("/", "").lower()
    
    # Find all existing data files for this symbol (excluding the new file)
    full_symbol_dir = data_root / "full" / normalized_symbol
    incremental_dir = data_root / "incremental" / normalized_symbol
    
    all_files = []
    
    # Collect full files
    if full_symbol_dir.exists():
        pattern = f"{normalized_symbol}_*.csv"
        for file_path in full_symbol_dir.glob(pattern):
            all_files.append(file_path)
    
    # Collect incremental files (excluding the new one)
    if incremental_dir.exists():
        for file_path in incremental_dir.glob("*.csv"):
            if file_path != new_file_path:
                all_files.append(file_path)
    
    if not all_files:
        print("  No previous files found - skipping continuity check")
        return
    
    # Find the most recent existing file by examining actual data timestamps
    latest_file = None
    latest_timestamp = None
    
    for file_path in all_files:
        try:
            # Read last line of each file to get the latest timestamp
            df = pd.read_csv(file_path)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                file_last_ts = df.iloc[-1]['timestamp']
                
                if latest_timestamp is None or file_last_ts > latest_timestamp:
                    latest_timestamp = file_last_ts
                    latest_file = file_path
        except Exception as e:
            print(f"  Warning: Could not read {file_path}: {e}")
            continue
    
    if latest_file is None or latest_timestamp is None:
        print("  Could not determine latest timestamp - skipping continuity check")
        return
    
    # Read first timestamp from the new file
    try:
        new_df = pd.read_csv(new_file_path)
        if new_df.empty:
            print("  New file is empty - skipping continuity check")
            return
            
        new_df['timestamp'] = pd.to_datetime(new_df['timestamp'])
        first_new_timestamp = new_df.iloc[0]['timestamp']
    except Exception as e:
        print(f"  Warning: Could not read new file {new_file_path}: {e}")
        return
    
    # Calculate the gap
    gap = first_new_timestamp - latest_timestamp
    gap_minutes = gap.total_seconds() / 60
    
    print(f"  Last existing data: {latest_timestamp}")
    print(f"  First new data: {first_new_timestamp}")
    print(f"  Gap: {gap} ({gap_minutes:.0f} minutes)")
    
    # Check if this is an expected weekend closure
    if _is_expected_weekend_gap(latest_timestamp, first_new_timestamp):
        print("  ✓ Gap is expected weekend market closure")
        return
    
    # Check for unexpected gaps during market hours
    if gap_minutes > 1:  # Allow for normal 1-minute intervals
        # If gap is during market hours, this is an error
        if _is_during_market_hours(latest_timestamp, first_new_timestamp):
            raise RuntimeError(
                f"Unexpected data gap detected during market hours: "
                f"{gap} ({gap_minutes:.0f} minutes) between "
                f"{latest_timestamp} and {first_new_timestamp}"
            )
        else:
            print(f"  ✓ Gap appears to be during market closure")
    else:
        print("  ✓ Data appears continuous")


def _is_expected_weekend_gap(last_ts: pd.Timestamp, first_ts: pd.Timestamp) -> bool:
    """Check if the gap represents a normal weekend forex market closure.
    
    Forex markets typically close Friday evening (~21:00 UTC) and reopen
    Sunday evening (~21:00 UTC).
    """
    # Convert to UTC if not already
    if last_ts.tz is None:
        last_ts = last_ts.tz_localize('UTC')
    if first_ts.tz is None:
        first_ts = first_ts.tz_localize('UTC')
        
    # Check if last timestamp is Friday evening (after 20:00 UTC)
    last_is_friday_evening = (
        last_ts.weekday() == 4 and  # Friday
        last_ts.hour >= 20
    )
    
    # Check if first timestamp is Sunday evening or Monday morning (before 06:00 UTC)
    first_is_weekend_end = (
        (first_ts.weekday() == 6 and first_ts.hour >= 20) or  # Sunday evening
        (first_ts.weekday() == 0 and first_ts.hour <= 6)      # Monday early morning
    )
    
    gap_hours = (first_ts - last_ts).total_seconds() / 3600
    
    # Weekend gap should be roughly 46-52 hours
    is_weekend_duration = 44 <= gap_hours <= 54
    
    return last_is_friday_evening and first_is_weekend_end and is_weekend_duration


def _is_during_market_hours(last_ts: pd.Timestamp, first_ts: pd.Timestamp) -> bool:
    """Check if the gap occurs during normal forex trading hours.
    
    Forex markets trade 24/5 (Monday ~00:00 UTC to Friday ~21:00 UTC).
    Only return True if the gap is clearly within continuous trading periods,
    not across weekend boundaries.
    """
    # Convert to UTC if not already
    if last_ts.tz is None:
        last_ts = last_ts.tz_localize('UTC')
    if first_ts.tz is None:
        first_ts = first_ts.tz_localize('UTC')
    
    def is_trading_time(ts):
        weekday = ts.weekday()
        hour = ts.hour
        
        # Monday 00:00 to Friday 21:00 UTC (approximately)
        if weekday == 0:  # Monday
            return hour >= 0  # From midnight Monday
        elif 1 <= weekday <= 4:  # Tuesday to Friday
            return True  # All day
        elif weekday == 4:  # Friday
            return hour <= 21  # Until 21:00 Friday
        elif weekday == 5:  # Saturday
            return False  # No trading
        elif weekday == 6:  # Sunday
            return hour >= 21  # From 21:00 Sunday
        else:
            return False
    
    # If this crosses a weekend boundary, it's not "during market hours"
    if _is_expected_weekend_gap(last_ts, first_ts):
        return False
    
    # Both timestamps should be during trading hours for this to be a market hours gap
    return is_trading_time(last_ts) and is_trading_time(first_ts)


def download_and_save_data(
    symbol: str, start_date: date, end_date: date, data_root: Path
) -> None:
    """Download and save market data for a given symbol and date range.

    Uses the dukascopy-python library to fetch minute-level data from
    Dukascopy and saves it in the expected format for the trading platform.

    Args:
        symbol: The financial instrument symbol (e.g., "EUR/USD")
        start_date: Start date for data download
        end_date: End date for data download
        data_root: Root directory where data files should be saved
    """
    from datetime import datetime

    from dukascopy_python import INTERVAL_MIN_1, OFFER_SIDE_BID, fetch

    # Validate date range
    today = date.today()
    if start_date > today:
        print(f"! Start date {start_date} is in the future")
        return

    if end_date > today:
        print(f"! Adjusting end date from {end_date} to {today}")
        end_date = today

    # Normalize symbol for file naming
    normalized_symbol = symbol.replace("/", "").lower()

    print(f"Downloading {symbol} data from {start_date} to {end_date}")

    try:
        # Convert dates to datetime objects for dukascopy-python
        # Note: end_date is interpreted as start of that day (not end of day)
        # to match reference implementation behavior
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())

        # Fetch data using dukascopy-python library
        print("  Fetching data from Dukascopy...")
        df = fetch(
            instrument=symbol,
            interval=INTERVAL_MIN_1,
            offer_side=OFFER_SIDE_BID,
            start=start_dt,
            end=end_dt,
        )

        if df is not None and not df.empty:
            print(f"    ✓ Got {len(df)} minute candles")

            # Save to incremental directory
            incremental_dir = data_root / "incremental" / normalized_symbol
            incremental_dir.mkdir(parents=True, exist_ok=True)

            filename = (
                f"{normalized_symbol}_interval_minute_1_"
                f"{start_date.strftime('%Y%m%d')}_"
                f"{end_date.strftime('%Y%m%d')}.csv"
            )
            output_path = incremental_dir / filename

            # Save DataFrame with timestamp index as column (to match expected format)
            df.reset_index().to_csv(output_path, index=False)
            print(f"✓ Saved {len(df)} minute candles to {output_path}")
            
            # Verify data continuity
            print("  Verifying data continuity...")
            verify_data_continuity(symbol, data_root, output_path)
        else:
            print("! No data was returned from Dukascopy")

    except Exception as e:
        print(f"! Error fetching data from Dukascopy: {e}")
        import traceback

        traceback.print_exc()
