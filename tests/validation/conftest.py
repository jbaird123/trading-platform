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
        Strategy name (e.g., 'ema_crossover')
    """
    # Try to extract from test name
    # Convention: test_<strategy_name>_<test_description>
    test_name = request.node.name

    # Default strategies for common test names
    if "ema_crossover" in test_name:
        return "ema_crossover"
    elif "bb_mean_reversion" in test_name:
        return "bb_mean_reversion"
    elif "multi_indicator" in test_name:
        return "multi_indicator_strategy"

    # Check for marker
    marker = request.node.get_closest_marker("strategy")
    if marker and marker.args:
        return str(marker.args[0])

    # Default
    return "ema_crossover"


@pytest.fixture
def golden_strategy_paths(strategy_name: str) -> dict[str, Path]:
    """Returns all relevant paths for a golden strategy.

    Args:
        strategy_name: Name of strategy (e.g., 'ema_crossover')

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
    ensure_dvc_data_pulled: bool,
) -> pd.DataFrame:
    """Loads TradingView trade export CSV.

    Args:
        golden_strategy_paths: Paths fixture
        ensure_dvc_data_pulled: Session fixture ensuring data exists

    Returns:
        DataFrame with TradingView trades
    """
    trades_path = golden_strategy_paths["trades"]

    if not trades_path.exists():
        pytest.skip(
            f"TradingView trades not found: {trades_path}. "
            "Run TradingView export first."
        )

    df = pd.read_csv(trades_path)

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
    """
    ohlcv_path = golden_strategy_paths["ohlcv"]

    if not ohlcv_path.exists():
        pytest.skip(
            f"TradingView OHLCV not found: {ohlcv_path}. "
            "Run TradingView export first."
        )

    df = pd.read_csv(ohlcv_path)

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
