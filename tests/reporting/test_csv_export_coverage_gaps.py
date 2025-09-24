# Coverage gaps for reporting/csv_export.py - missing lines 71-77 (save_prices_csv function)
from __future__ import annotations

from pathlib import Path

import pandas as pd
from trading_platform.reporting.csv_export import save_prices_csv


def test_csv_export_save_prices_csv(tmp_path: Path):
    """Test save_prices_csv function coverage (lines 71-77)."""
    # Create sample OHLC data
    df = pd.DataFrame({
        'open': [1.1000, 1.1010, 1.1020],
        'high': [1.1015, 1.1025, 1.1030], 
        'low': [1.0995, 1.1005, 1.1015],
        'close': [1.1010, 1.1020, 1.1025],
        'volume': [100, 200, 150]  # Extra column to test column selection
    })
    
    # Set datetime index
    df.index = pd.date_range('2024-01-01', periods=3, freq='1H')
    
    # Save to CSV
    output_path = tmp_path / "test_prices.csv"
    result_path = save_prices_csv(output_path, df)
    
    # Verify file was created (lines 72-77)
    assert result_path == output_path
    assert output_path.exists()
    
    # Verify content has correct columns
    content = output_path.read_text()
    assert "time,open,high,low,close" in content
    assert "volume" not in content  # Should be excluded (line 75)
    
    # Verify parent directory was created (line 72)
    assert output_path.parent.exists()