"""Pytest fixtures for golden validation tests.

# Validates: [DH-2.13], [SE-3.9], [RV-9.1]
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import jsonschema
import pandas as pd
import pytest
import yaml

# Path constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
GOLDEN_DATA_ROOT = PROJECT_ROOT / "data" / "dvc" / "golden"
GOLDEN_STRATEGIES_ROOT = GOLDEN_DATA_ROOT / "strategies"
GOLDEN_CONFIG_ROOT = PROJECT_ROOT / "configs" / "golden_strategies"
SCHEMA_PATH = PROJECT_ROOT / "docs" / "schemas" / "golden_metadata.schema.json"


def load_and_validate_golden_metadata(metadata_path: Path) -> dict[str, Any]:
    """Loads metadata.json and validates against schema.

    Args:
        metadata_path: Path to metadata.json file

    Returns:
        Validated metadata dictionary

    Raises:
        jsonschema.ValidationError: If metadata doesn't match schema
        FileNotFoundError: If files don't exist
    """
    # Load schema and data
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    with open(metadata_path) as f:
        metadata = json.load(f)

    # Validate
    jsonschema.validate(instance=metadata, schema=schema)

    return dict(metadata)


@pytest.fixture(scope="session")
def ensure_dvc_data_pulled():
    """Ensures DVC golden data is pulled before tests run.

    This fixture runs once per test session and checks if DVC
    data exists. If not, it attempts to pull it.
    """
    # Check if golden data directory exists and has content
    if not GOLDEN_DATA_ROOT.exists():
        pytest.skip(f"Golden data directory {GOLDEN_DATA_ROOT} does not exist")

    # Check if .dvc files exist (indicating DVC is tracking this)
    dvc_files = list(GOLDEN_DATA_ROOT.glob("**/*.dvc"))

    if dvc_files:
        # Check if data files already exist locally
        # If they do, we don't need to pull from DVC
        has_local_data = False
        for dvc_file in dvc_files:
            # Get the actual data directory/file that this .dvc file points to
            data_path = dvc_file.with_suffix("")
            if data_path.exists():
                # Check if it's a directory with files or a file
                if data_path.is_dir():
                    if any(data_path.iterdir()):
                        has_local_data = True
                        break
                elif data_path.is_file():
                    has_local_data = True
                    break

        # Only try to pull if we don't have local data
        if not has_local_data:
            try:
                subprocess.run(
                    ["dvc", "pull", str(GOLDEN_DATA_ROOT)],
                    cwd=PROJECT_ROOT,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                pytest.skip(
                    "DVC pull failed - ensure DVC is configured " "and you have access"
                )
            except FileNotFoundError:
                pytest.skip("DVC not installed")

    return True


@pytest.fixture
def strategy_name(request) -> str:
    """Extracts strategy name from test name or marker.

    Returns:
        Strategy name (e.g., 'ema_crossover/baseline',
        'ema_crossover/20pip_stop')
    """
    # Try to extract from test name
    # Convention: test_<strategy_name>_<variation>_<test_description>
    test_name = request.node.name

    # Default strategies for common test names
    if "ema_crossover" in test_name:
        # Check for variation in test name
        # IMPORTANT: Check more specific variations first
        # (e.g., 20pip_stop_40pip_tp before 20pip_stop)
        if "20pip_stop_40pip_tp" in test_name:
            return "ema_crossover/20pip_stop_40pip_tp"
        elif "20pip_trailing_stop" in test_name:
            return "ema_crossover/20pip_trailing_stop"
        elif "20pip_stop" in test_name:
            return "ema_crossover/20pip_stop"
        elif "baseline" in test_name or "_ema_crossover_" in test_name:
            # Default to baseline for backward compatibility
            return "ema_crossover/baseline"
    elif "bb_mean_reversion" in test_name:
        return "bb_mean_reversion"
    elif "multi_indicator" in test_name:
        return "multi_indicator_strategy"

    # Check for marker
    marker = request.node.get_closest_marker("strategy")
    if marker and marker.args:
        return str(marker.args[0])

    # Default to baseline
    return "ema_crossover/baseline"


@pytest.fixture
def golden_strategy_paths(strategy_name: str) -> dict[str, Path]:
    """Returns all relevant paths for a golden strategy.

    Args:
        strategy_name: Name of strategy with optional variation
                       (e.g., 'ema_crossover/baseline',
                       'ema_crossover/20pip_stop')

    Returns:
        Dictionary with paths to data and config files
    """
    data_dir = GOLDEN_STRATEGIES_ROOT / strategy_name
    config_dir = GOLDEN_CONFIG_ROOT / strategy_name

    return {
        "data_dir": data_dir,
        "config_dir": config_dir,
        "ohlcv": data_dir / "ohlcv.csv",
        "trades": data_dir / "trades.csv",
        "equity_curve": data_dir / "equity_curve.csv",
        "metadata": data_dir / "metadata.json",
        "strategy_yaml": config_dir / "strategy.yaml",
        "rem_yaml": config_dir / "rem.yaml",
        "run_config_yaml": config_dir / "run_config.yaml",
        "pinescript": config_dir / "strategy.pine",
        "readme": config_dir / "README.md",
    }


@pytest.fixture
def golden_strategy_config(
    strategy_name: str,
    golden_strategy_paths: dict[str, Path],
) -> dict[str, Any]:
    """Loads strategy configuration YAML files.

    Args:
        strategy_name: Name of strategy
        golden_strategy_paths: Paths fixture

    Returns:
        Dictionary with parsed YAML configs
    """
    paths = golden_strategy_paths

    # Check if config files exist
    if not paths["strategy_yaml"].exists():
        pytest.skip(f"Strategy config not found: {paths['strategy_yaml']}")

    with open(paths["strategy_yaml"]) as f:
        strategy = yaml.safe_load(f)

    with open(paths["rem_yaml"]) as f:
        rem = yaml.safe_load(f)

    with open(paths["run_config_yaml"]) as f:
        run_config = yaml.safe_load(f)

    return {
        "strategy": strategy,
        "rem": rem,
        "run_config": run_config,
    }


@pytest.fixture
def golden_metadata(
    golden_strategy_paths: dict[str, Path],
) -> dict[str, Any]:
    """Loads and validates metadata.json for a strategy.

    Args:
        golden_strategy_paths: Paths fixture

    Returns:
        Validated metadata dictionary
    """
    metadata_path = golden_strategy_paths["metadata"]

    if not metadata_path.exists():
        pytest.skip(
            f"Metadata not found: {metadata_path}. " "Run TradingView export first."
        )

    return load_and_validate_golden_metadata(metadata_path)


@pytest.fixture
def tradingview_trades(
    golden_strategy_paths: dict[str, Path],
    golden_metadata: dict[str, Any],
    ensure_dvc_data_pulled: bool,
) -> pd.DataFrame:
    """Loads TradingView trade export CSV and filters to validation date range.

    Args:
        golden_strategy_paths: Paths fixture
        golden_metadata: Metadata fixture with date_range
        ensure_dvc_data_pulled: Session fixture ensuring data exists

    Returns:
        DataFrame with TradingView trades filtered to validation date range

    Raises:
        AssertionError: If timestamps are not in UTC format
    """
    trades_path = golden_strategy_paths["trades"]

    if not trades_path.exists():
        pytest.skip(
            f"TradingView trades not found: {trades_path}. "
            "Run TradingView export first."
        )

    df = pd.read_csv(trades_path)

    # Check timezone format before processing
    # Look for Date/Time column (TradingView's default)
    time_col = None
    for col in ["Date/Time", "Entry Time", "date_time", "time", "Time"]:
        if col in df.columns:
            time_col = col
            break

    if time_col is not None:
        # Get first non-null timestamp
        first_time = None
        for val in df[time_col]:
            if pd.notna(val):
                first_time = str(val)
                break

        if first_time:
            # Check if it's in UTC format
            # TradingView trades export doesn't include timezone markers in timestamps
            # so we can only check for explicit NON-UTC markers
            # Format: "2023-01-06 20:00" (no timezone suffix)

            # Check for -01:00 offset (Azores time, NOT pure UTC)
            if "-01:00" in first_time:
                pytest.fail(
                    f"TradingView trades export has -01:00 timezone offset!\n"
                    f"Found timestamp: {first_time}\n"
                    f"Expected format: 2023-01-06 20:00 (plain, no offset)\n"
                    f"\n"
                    f"In TradingView:\n"
                    f"1. Go to Settings (gear icon) → Chart Settings\n"
                    f"2. Set 'Timezone' to 'UTC (Reykjavik)' "
                    f"(NOT 'UTC (Azores)')\n"
                    f"3. Re-export the trades list\n"
                    f"\n"
                    f"Note: 'UTC (Azores)' includes DST offsets (-01:00), "
                    f"which is incorrect.\n"
                    f"Use 'UTC (Reykjavik)' for true UTC with no offsets.\n"
                )

            # Check for other clear non-UTC timezone markers
            has_bad_marker = any(
                marker in first_time
                for marker in ["-05:00", "-04:00", "-02:00", "-03:00", "EST", "EDT"]
            )

            if has_bad_marker:
                pytest.fail(
                    f"TradingView trades export has non-UTC timezone marker!\n"
                    f"Found timestamp: {first_time}\n"
                    f"Expected format: 2023-01-06 20:00 (plain UTC, no offset)\n"
                    f"\n"
                    f"In TradingView:\n"
                    f"1. Go to Settings (gear icon) → Chart Settings\n"
                    f"2. Set 'Timezone' to 'UTC (Reykjavik)'\n"
                    f"3. Re-export the trades list\n"
                    f"\n"
                    f"Note: The trades CSV doesn't include 'Z' suffix, but should be\n"
                    f"in UTC if TradingView timezone is set to 'UTC (Reykjavik)'.\n"
                )

    # Standardize column names (TradingView may vary)
    column_mapping = {
        "Entry Time": "entry_time",
        "Entry Price": "entry_price",
        "Exit Time": "exit_time",
        "Exit Price": "exit_price",
        "Side": "side",
        "Profit": "profit",
        "Cumulative Profit": "cumulative_profit",
        "Size": "size",
    }

    # Try to rename columns (may need adjustment based on actual exports)
    df = df.rename(columns=column_mapping)

    # Parse timestamps
    if "entry_time" in df.columns:
        df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    if "exit_time" in df.columns:
        df["exit_time"] = pd.to_datetime(df["exit_time"], utc=True)

    # Filter trades to validation date range if specified in metadata
    # This allows TradingView exports to include warmup data that gets filtered out
    #
    # IMPORTANT: When exporting from TradingView, always set the export start date
    # EARLIER than the validation start date (recommended: 100+ bars before).
    # This ensures:
    # 1. Indicators have enough data to warm up properly
    # 2. Early trades aren't filtered out by TradingView's internal logic
    # 3. Both systems detect the same number of crossovers
    #
    # The filtering below will automatically exclude trades outside the validation
    # range, so it's safe (and recommended) to export extra data at the beginning.
    date_range = golden_metadata.get("date_range")
    if date_range and "Date/Time" in df.columns:
        start_date = pd.to_datetime(date_range["start"], utc=True)
        end_date = pd.to_datetime(date_range["end"], utc=True)

        # Parse Date/Time column for filtering
        df["_filter_time"] = pd.to_datetime(df["Date/Time"], utc=True)

        # Filter: keep trades where entry is within validation range
        # For TradingView format, we need to look at entry rows (Type contains "Entry")
        mask_entry = df["Type"].str.contains("Entry", case=False, na=False)
        mask_date = (df["_filter_time"] >= start_date) & (
            df["_filter_time"] <= end_date
        )

        # Get trade numbers that have entries in the validation range
        valid_trade_nums = df[mask_entry & mask_date]["Trade #"].unique()

        # Keep all rows (entry and exit) for trades that entered in validation range
        df = df[df["Trade #"].isin(valid_trade_nums)].copy()

        # Drop the temporary filter column
        df = df.drop(columns=["_filter_time"])

    return df


@pytest.fixture
def tradingview_ohlcv(
    golden_strategy_paths: dict[str, Path],
    ensure_dvc_data_pulled: bool,
) -> pd.DataFrame:
    """Loads TradingView OHLCV export CSV.

    Args:
        golden_strategy_paths: Paths fixture
        ensure_dvc_data_pulled: Session fixture ensuring data exists

    Returns:
        DataFrame with OHLCV data

    Raises:
        AssertionError: If timestamps are not in UTC format
    """
    ohlcv_path = golden_strategy_paths["ohlcv"]

    if not ohlcv_path.exists():
        pytest.skip(
            f"TradingView OHLCV not found: {ohlcv_path}. "
            "Run TradingView export first."
        )

    # Read raw CSV to check timezone format
    df_raw = pd.read_csv(ohlcv_path)

    # Find time column
    time_col = None
    for col in ["time", "Time", "timestamp", "Timestamp"]:
        if col in df_raw.columns:
            time_col = col
            break

    if time_col is None:
        pytest.fail("No time column found in OHLCV CSV")

    # Check MULTIPLE timestamps for UTC format (not just first)
    # TradingView can have mixed formats if wrong UTC option is selected
    timestamps_to_check = [
        df_raw[time_col].iloc[0],
        df_raw[time_col].iloc[len(df_raw) // 2] if len(df_raw) > 1 else None,
        df_raw[time_col].iloc[-1] if len(df_raw) > 0 else None,
    ]

    for idx, ts in enumerate(timestamps_to_check):
        if ts is None:
            continue

        timestamp_str = str(ts)

        # Check for -01:00 offset (Azores time, NOT pure UTC)
        if "-01:00" in timestamp_str:
            pytest.fail(
                f"TradingView OHLCV export has -01:00 timezone offset (Azores time)!\n"
                f"Found timestamp at position {idx}: {timestamp_str}\n"
                f"Expected format: 2023-01-06T19:00:00Z (with Z suffix)\n"
                f"\n"
                f"In TradingView:\n"
                f"1. Go to Settings (gear icon) → Chart Settings\n"
                f"2. Set 'Timezone' to 'UTC (Reykjavik)' (NOT 'UTC (Azores)')\n"
                f"3. Re-export the chart data\n"
                f"\n"
                f"Note: 'UTC (Azores)' includes DST offsets (-01:00), "
                f"which is incorrect.\n"
                f"Use 'UTC (Reykjavik)' for true UTC with no offsets.\n"
            )

        # Check for other non-UTC timezone markers
        has_bad_offset = any(
            marker in timestamp_str
            for marker in [
                "-05:00",
                "-04:00",
                "-02:00",
                "-03:00",
                "-06:00",
                "EST",
                "EDT",
            ]
        )

        if has_bad_offset:
            pytest.fail(
                f"TradingView OHLCV export has non-UTC timezone offset!\n"
                f"Found timestamp at position {idx}: {timestamp_str}\n"
                f"Expected format: 2023-01-06T19:00:00Z (with Z suffix)\n"
                f"\n"
                f"In TradingView:\n"
                f"1. Go to Settings (gear icon) → Chart Settings\n"
                f"2. Set 'Timezone' to 'UTC (Reykjavik)'\n"
                f"3. Re-export the chart data\n"
            )

        # UTC timestamps should end with 'Z' (proper ISO 8601 UTC format)
        if not timestamp_str.endswith("Z"):
            pytest.fail(
                f"TradingView OHLCV export timestamps must end with 'Z' (UTC marker)!\n"
                f"Found timestamp at position {idx}: {timestamp_str}\n"
                f"Expected format: 2023-01-06T19:00:00Z\n"
                f"\n"
                f"In TradingView:\n"
                f"1. Go to Settings (gear icon) → Chart Settings\n"
                f"2. Set 'Timezone' to 'UTC (Reykjavik)'\n"
                f"3. Re-export the chart data\n"
                f"\n"
                f"The timestamps should have a 'Z' suffix indicating UTC.\n"
            )

    # Now parse normally
    df = df_raw.copy()

    # Standardize column names
    df = df.rename(
        columns={
            "time": "timestamp",
            "Time": "timestamp",
            "Volume": "volume",
        }
    )

    # Parse timestamp
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")

    # Add dummy volume column if not present (TradingView forex data often lacks volume)
    if "volume" not in df.columns:
        df["volume"] = 1.0

    return df


@pytest.fixture
def tradingview_ohlcv_1min(
    ensure_dvc_data_pulled: bool,
) -> pd.DataFrame:
    """Loads TradingView 1-minute OHLCV data for zoom validation.

    Args:
        ensure_dvc_data_pulled: Session fixture ensuring data exists

    Returns:
        DataFrame with 1-minute OHLCV data indexed by timestamp

    Raises:
        pytest.skip: If 1-minute data not found
    """
    # Path to 1-minute data
    ohlcv_1min_path = (
        GOLDEN_DATA_ROOT
        / "ohlcv"
        / "tradingview"
        / "full"
        / "eurusd"
        / "eurusd_1min.csv"
    )

    if not ohlcv_1min_path.exists():
        pytest.skip(
            f"TradingView 1-minute OHLCV not found: {ohlcv_1min_path}. "
            "1-minute data is required for zoom validation."
        )

    # Read CSV
    df = pd.read_csv(ohlcv_1min_path)

    # Standardize column names
    df = df.rename(
        columns={
            "time": "timestamp",
            "Time": "timestamp",
            "Volume": "volume",
        }
    )

    # Parse timestamp
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")

    # Add dummy volume column if not present
    if "volume" not in df.columns:
        df["volume"] = 1.0

    return df
