"""
Test coverage gaps for data schema module.
Targets specific lines that need coverage to reach 100%.
"""
import pytest
import pandas as pd
from unittest.mock import patch


def test_schema_missing_unknown_columns():
    """Test schema validation with missing or unknown columns (covers lines 69-72)."""
    import sys
    import os
    import tempfile
    from pathlib import Path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    
    from trading_platform.data.schema import load_and_normalize_data
    
    # Test case with missing required columns
    # Create a temporary CSV with missing columns
    csv_content_missing = "UTCTime,Open\n2023-01-01 00:00:00,1.0\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content_missing)
        temp_path_missing = Path(f.name)
    
    try:
        result, quality_flags = load_and_normalize_data(temp_path_missing)
        
        # Should return empty DataFrame due to missing columns
        assert result.empty
        assert len(quality_flags) == 1
        assert "unexpected_columns" in quality_flags[0]
        assert "missing=" in quality_flags[0]
    finally:
        temp_path_missing.unlink()
    
    # Test case with unknown columns
    csv_content_unknown = "UTCTime,Open,High,Low,Close,Volume,UnknownCol\n2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000,test\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content_unknown)
        temp_path_unknown = Path(f.name)
    
    try:
        result, quality_flags = load_and_normalize_data(temp_path_unknown)
        
        # Should return empty DataFrame due to unknown columns
        assert result.empty 
        assert len(quality_flags) == 1
        assert "unexpected_columns" in quality_flags[0]
        assert "unknown=" in quality_flags[0]
    finally:
        temp_path_unknown.unlink()
    
    # Test case with both missing and unknown columns
    csv_content_both = "UTCTime,Open,UnknownCol\n2023-01-01 00:00:00,1.0,test\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content_both)
        temp_path_both = Path(f.name)
    
    try:
        result, quality_flags = load_and_normalize_data(temp_path_both)
        
        # Should return empty DataFrame due to both issues
        assert result.empty
        assert len(quality_flags) == 1
        assert "unexpected_columns" in quality_flags[0]
        assert "missing=" in quality_flags[0] and "unknown=" in quality_flags[0]
    finally:
        temp_path_both.unlink()


def test_schema_successful_normalization():
    """Test successful schema normalization to ensure existing functionality works."""
    import sys
    import os
    import tempfile
    from pathlib import Path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    
    from trading_platform.data.schema import load_and_normalize_data
    
    # Test case with correct columns
    csv_content_correct = "UTCTime,Open,High,Low,Close,Volume\n2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content_correct)
        temp_path_correct = Path(f.name)
    
    try:
        result, quality_flags = load_and_normalize_data(temp_path_correct)
        
        # Should successfully normalize
        assert not result.empty
        assert len(quality_flags) == 0
        # timestamp becomes the index, not a column
        assert result.index.name == 'timestamp'
        assert 'open' in result.columns
    finally:
        temp_path_correct.unlink()


def test_schema_normalized_columns_missing_unknown():
    """Test schema validation with already normalized columns having missing or unknown (covers lines 56-62)."""
    import sys
    import os
    import tempfile
    from pathlib import Path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    
    from trading_platform.data.schema import load_and_normalize_data
    
    # Test case with normalized column names but missing columns
    csv_content_missing = "timestamp,open\n2023-01-01 00:00:00,1.0\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content_missing)
        temp_path = Path(f.name)
    
    try:
        result, quality_flags = load_and_normalize_data(temp_path)
        
        # Should return empty DataFrame due to missing columns
        assert result.empty
        assert len(quality_flags) == 1
        assert "unexpected_columns" in quality_flags[0]
        assert "missing=" in quality_flags[0]
    finally:
        temp_path.unlink()
    
    # Test case with normalized column names but unknown columns
    csv_content_unknown = "timestamp,open,high,low,close,volume,unknown_col\n2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000,test\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content_unknown)
        temp_path = Path(f.name)
    
    try:
        result, quality_flags = load_and_normalize_data(temp_path)
        
        # Should return empty DataFrame due to unknown columns
        assert result.empty
        assert len(quality_flags) == 1
        assert "unexpected_columns" in quality_flags[0]
        assert "unknown=" in quality_flags[0]
    finally:
        temp_path.unlink()


def test_schema_missing_timestamp():
    """Test schema validation when timestamp column is completely missing (covers lines 75-77)."""
    import sys
    import os
    import tempfile
    from pathlib import Path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    
    from trading_platform.data.schema import load_and_normalize_data
    
    # Test case with no timestamp column at all
    csv_content_no_timestamp = "open,high,low,close,volume\n1.0,1.1,0.9,1.05,1000\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content_no_timestamp)
        temp_path = Path(f.name)
    
    try:
        result, quality_flags = load_and_normalize_data(temp_path)
        
        # Should return empty DataFrame due to missing timestamp
        assert result.empty
        assert len(quality_flags) == 2
        assert "missing_timestamp" in quality_flags
        assert any("columns:" in flag for flag in quality_flags)
    finally:
        temp_path.unlink()


def test_schema_exception_handling():
    """Test schema exception handling (covers lines 85-89)."""
    import sys
    import os
    import tempfile
    from pathlib import Path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    
    from trading_platform.data.schema import load_and_normalize_data
    
    # Test case with invalid timestamp that will cause parsing error
    csv_content_bad_timestamp = "UTCTime,Open,High,Low,Close,Volume\ninvalid-date,1.0,1.1,0.9,1.05,1000\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content_bad_timestamp)
        temp_path = Path(f.name)
    
    try:
        result, quality_flags = load_and_normalize_data(temp_path)
        
        # Should return empty DataFrame due to parsing error
        assert result.empty
        assert len(quality_flags) == 1
        assert "unexpected_error" in quality_flags[0]
    finally:
        temp_path.unlink()


def test_schema_resample_ohlc():
    """Test resample_ohlc function (covers lines 102-110)."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    
    from trading_platform.data.schema import resample_ohlc
    
    # Create a sample DataFrame with timestamp index
    dates = pd.date_range('2023-01-01', periods=4, freq='1min')
    df = pd.DataFrame({
        'open': [1.0, 1.1, 1.2, 1.3],
        'high': [1.05, 1.15, 1.25, 1.35],
        'low': [0.95, 1.05, 1.15, 1.25],
        'close': [1.02, 1.12, 1.22, 1.32],
        'volume': [100, 200, 300, 400]
    }, index=dates)
    
    # Test resampling to 2-minute intervals
    resampled = resample_ohlc(df, '2min')
    
    # Should have 2 rows (4 minutes resampled to 2-minute intervals)
    assert len(resampled) == 2
    assert 'open' in resampled.columns
    assert 'high' in resampled.columns
    assert 'low' in resampled.columns
    assert 'close' in resampled.columns
    assert 'volume' in resampled.columns


def test_schema_normalized_columns_success():
    """Test successful processing with already normalized columns (covers branch 58->80)."""
    import sys
    import os
    import tempfile
    from pathlib import Path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    
    from trading_platform.data.schema import load_and_normalize_data
    
    # Test case with correct normalized column names
    csv_content_normalized = "timestamp,open,high,low,close,volume\n2023-01-01 00:00:00,1.0,1.1,0.9,1.05,1000\n"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content_normalized)
        temp_path = Path(f.name)
    
    try:
        result, quality_flags = load_and_normalize_data(temp_path)
        
        # Should successfully normalize without column mapping needed
        assert not result.empty
        assert len(quality_flags) == 0
        assert result.index.name == 'timestamp'
        assert 'open' in result.columns
        assert len(result) == 1
    finally:
        temp_path.unlink()