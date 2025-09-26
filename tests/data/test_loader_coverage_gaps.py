"""
Test coverage gaps for data loader module.
Targets specific lines that need coverage to reach 100%.
"""

import tempfile
from pathlib import Path

import pytest
import yaml


def test_loader_invalid_data_request():
    """Test loader with invalid data_request parameter (covers line 24)."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

    from trading_platform.data.loader import load_from_catalog

    # Test with non-dict data_request
    with pytest.raises(ValueError, match="data_request must be a dict"):
        load_from_catalog("not a dict")  # type: ignore[arg-type]


def test_loader_missing_symbol():
    """Test loader with missing or empty symbol (covers line 27)."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

    from trading_platform.data.loader import load_from_catalog

    # Test with empty symbol
    with pytest.raises(ValueError, match="data_request.symbol is required"):
        load_from_catalog({"symbol": ""})

    # Test with missing symbol key
    with pytest.raises(ValueError, match="data_request.symbol is required"):
        load_from_catalog({})

    # Test with None symbol
    with pytest.raises(ValueError, match="data_request.symbol is required"):
        load_from_catalog({"symbol": None})


def test_loader_catalog_not_found():
    """Test loader with missing catalog file (covers line 32)."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

    from trading_platform.data.loader import load_from_catalog

    # Test with non-existent catalog path
    with pytest.raises(FileNotFoundError, match="data catalog not found"):
        load_from_catalog(
            {"symbol": "EURUSD"}, catalog_path=Path("/non/existent/catalog.yaml")
        )


def test_loader_symbol_not_in_catalog():
    """Test loader with symbol not in catalog (covers lines 46-50)."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

    from trading_platform.data.loader import load_from_catalog

    # Create temporary catalog file without the requested symbol
    catalog_content = {"OTHER_SYMBOL": {"csv_path": "/some/path/other.csv"}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(catalog_content, f)
        catalog_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="symbol not in catalog: EURUSD"):
            load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)
    finally:
        catalog_path.unlink()

    # Test with empty catalog
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({}, f)
        catalog_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="symbol not in catalog: EURUSD"):
            load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)
    finally:
        catalog_path.unlink()

    # Test with invalid catalog entry (no csv_path)
    catalog_content_no_path = {
        "EURUSD": {
            "description": "Euro USD rate"
            # Missing csv_path
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(catalog_content_no_path, f)
        catalog_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="symbol not in catalog: EURUSD"):
            load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)
    finally:
        catalog_path.unlink()


def test_loader_empty_data_from_csv():
    """Test loader when CSV data is empty or invalid."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

    from trading_platform.data.loader import load_from_catalog

    # Create empty CSV file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as csv_f:
        csv_f.write("")  # Empty CSV
        csv_path = Path(csv_f.name)

    # Create catalog pointing to the empty CSV
    catalog_content = {"EURUSD": {"csv_path": str(csv_path)}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(catalog_content, f)
        catalog_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Loaded data is empty"):
            load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)
    finally:
        catalog_path.unlink()
        csv_path.unlink()


def test_loader_with_timeframe_resampling():
    """Test loader with timeframe parameter (covers branch 54->58)."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

    from trading_platform.data.loader import load_from_catalog

    # Create valid CSV file
    csv_content = (
        "UTCTime,Open,High,Low,Close,Volume\n"
        "2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000\n"
        "2023-01-01 00:01:00,1.05,1.15,0.95,1.1,1100\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as csv_f:
        csv_f.write(csv_content)
        csv_path = Path(csv_f.name)

    # Create catalog pointing to the CSV
    catalog_content = {"EURUSD": {"csv_path": str(csv_path)}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(catalog_content, f)
        catalog_path = Path(f.name)

    try:
        # Test with timeframe parameter
        df, flags = load_from_catalog(
            {"symbol": "EURUSD", "timeframe": "1H"}, catalog_path=catalog_path
        )

        assert not df.empty
        assert len(flags) == 0
        assert df.index.name == "timestamp"

        # Test without timeframe parameter (no resampling)
        df2, flags2 = load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)

        assert not df2.empty
        assert len(flags2) == 0

    finally:
        catalog_path.unlink()
        csv_path.unlink()


def test_loader_with_date_filters():
    """Test loader with start/end date parameters (covers branches 60->62, 62->65)."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

    from trading_platform.data.loader import load_from_catalog

    # Create CSV with multiple dates
    csv_content = """UTCTime,Open,High,Low,Close,Volume
2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000
2023-01-02 00:00:00,1.05,1.15,0.95,1.1,1100
2023-01-03 00:00:00,1.1,1.2,1.0,1.15,1200
2023-01-04 00:00:00,1.15,1.25,1.05,1.2,1300
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as csv_f:
        csv_f.write(csv_content)
        csv_path = Path(csv_f.name)

    # Create catalog
    catalog_content = {"EURUSD": {"csv_path": str(csv_path)}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(catalog_content, f)
        catalog_path = Path(f.name)

    try:
        # Test with start date filter
        df_start, _ = load_from_catalog(
            {"symbol": "EURUSD", "start": "2023-01-02"}, catalog_path=catalog_path
        )
        assert len(df_start) == 3  # Should exclude first row

        # Test with end date filter
        df_end, _ = load_from_catalog(
            {"symbol": "EURUSD", "end": "2023-01-03"}, catalog_path=catalog_path
        )
        assert len(df_end) == 3  # Should exclude last row

        # Test with both start and end filters
        df_both, _ = load_from_catalog(
            {"symbol": "EURUSD", "start": "2023-01-02", "end": "2023-01-03"},
            catalog_path=catalog_path,
        )
        assert len(df_both) == 2  # Should only include middle rows

        # Test without date filters
        df_all, _ = load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)
        assert len(df_all) == 4  # Should include all rows

    finally:
        catalog_path.unlink()
        csv_path.unlink()


def test_loader_edge_cases():
    """Test loader edge cases for better coverage."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

    from trading_platform.data.loader import load_from_catalog

    # Test with non-dict catalog content (malformed YAML)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("not_a_dict_but_a_list:\n- item1\n- item2")
        catalog_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="symbol not in catalog"):
            load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)
    finally:
        catalog_path.unlink()

    # Test with catalog entry that's not a dict
    catalog_content = {"EURUSD": "not_a_dict"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(catalog_content, f)
        catalog_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="symbol not in catalog"):
            load_from_catalog({"symbol": "EURUSD"}, catalog_path=catalog_path)
    finally:
        catalog_path.unlink()
