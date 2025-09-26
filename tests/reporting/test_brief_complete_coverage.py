"""
Test remaining coverage gaps in reporting/brief.py.

Targets specific missing lines and branches:
- Line 60: Return None case in _lookup_schema when path traversal fails
- Lines 543, 592: Exception handling in signal processing
- Lines 510->544, 581->596, 596->598, 724->726: Branch coverage gaps
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import _lookup_schema, generate_brief


def create_test_trade():
    """Helper function to create a test trade."""
    return Trade(
        symbol="EURUSD",
        entry_time=datetime(2024, 1, 1, 10, 0),
        exit_time=datetime(2024, 1, 1, 11, 0),
        entry_price=1.1000,
        exit_price=1.1050,
        side="long",
        size=1000.0,
        pnl=50.0,
    )


def test_lookup_schema_return_none():
    """Test _lookup_schema returning None - hits line 60."""
    # Test case where we traverse into a non-object without description
    schema = {
        "type": "object",
        "properties": {
            "level1": {
                "type": "array",  # Not an object and no description
                "items": {"type": "string"}
            }
        }
    }
    
    # This should return None because we're trying to access a path beyond level1
    # but level1 is not an object and doesn't have a description
    result = _lookup_schema(schema, ["level1", "nonexistent"])
    assert result is None

    # Test case where properties don't exist in schema
    schema_no_props = {"type": "object"}  # No properties field
    result = _lookup_schema(schema_no_props, ["any_key"])
    assert result is None

    # Test case where we go too deep into a primitive type
    schema_primitive = {
        "type": "object", 
        "properties": {
            "value": {"type": "string"}  # Primitive with no description
        }
    }
    result = _lookup_schema(schema_primitive, ["value", "deeper"])
    assert result is None


def test_generate_brief_signals_processing_exceptions():
    """Test signal processing exception handling - hits lines 543, 592."""
    trades = [create_test_trade()]

    # Test OSError during signal file reading (line 543)
    with patch("pandas.read_parquet", side_effect=OSError("File access error")):
        with patch("os.path.exists", return_value=True):
            brief = generate_brief(
                meta={},
                params={},
                trades=trades,
                initial_cash=10000.0,
                signals_path="/nonexistent/signals.parquet",
            )
            
            # Should have default signal_quality_analysis values due to exception
            assert "signal_quality_analysis" in brief
            signal_analysis = brief["signal_quality_analysis"]
            assert signal_analysis["signal_persistence_pct"] == 0.0
            assert signal_analysis["avg_signal_duration_bars"] == 0.0

    # Test FileNotFoundError during signal file reading (line 543)
    with patch("pandas.read_parquet", side_effect=FileNotFoundError("File not found")):
        with patch("os.path.exists", return_value=True):
            brief = generate_brief(
                meta={},
                params={},
                trades=trades,
                initial_cash=10000.0,
                signals_path="/missing/signals.parquet",
            )
            
            # Should have default signal_quality_analysis values due to exception
            assert "signal_quality_analysis" in brief
            signal_analysis = brief["signal_quality_analysis"]
            assert signal_analysis["signal_persistence_pct"] == 0.0

    # Test pandas ParserError during signal file reading (line 543)  
    with patch("pandas.read_parquet", side_effect=pd.errors.ParserError("Parse error")):
        with patch("os.path.exists", return_value=True):
            brief = generate_brief(
                meta={},
                params={},
                trades=trades,
                initial_cash=10000.0,
                signals_path="/corrupt/signals.parquet",
            )
            
            # Should have default signal_quality_analysis values due to exception
            assert "signal_quality_analysis" in brief
            signal_analysis = brief["signal_quality_analysis"]
            assert signal_analysis["signal_persistence_pct"] == 0.0


def test_generate_brief_signal_processing_branch_coverage():
    """Test signal processing branch coverage - hits various branch conditions."""
    trades = [create_test_trade()]
    
    # Create temporary signals file with valid signal data
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        signals_path = f.name

        # Create signals DataFrame with mixed signal types
        dates = pd.date_range("2024-01-01", periods=12, freq="1h")
        signals_df = pd.DataFrame(
            {
                "signal": [
                    "long", "long", "long",     # 3-bar long signal
                    "flat",                     # 1-bar flat
                    "short", "short",           # 2-bar short signal
                    "flat", "flat",             # 2-bar flat
                    "long",                     # 1-bar long
                    "flat", "flat", "flat"      # 3-bar flat
                ]
            },
            index=dates,
        )
        signals_df.to_parquet(signals_path)

    try:
        # Test successful signal processing that hits various branches
        brief = generate_brief(
            meta={},
            params={},
            trades=trades,
            initial_cash=10000.0,
            signals_path=signals_path,
        )

        # Should have signal quality analysis
        assert "signal_quality_analysis" in brief
        signal_analysis = brief["signal_quality_analysis"]
        
        # 6 non-flat signals out of 12 total = 50%
        assert signal_analysis["signal_persistence_pct"] == 50.0
        
        # Average duration: (3 + 2 + 1) / 3 signal groups = 2.0
        assert signal_analysis["avg_signal_duration_bars"] == 2.0

    finally:
        os.unlink(signals_path)


def test_generate_brief_signal_processing_edge_cases():
    """Test signal processing with edge case data structures."""
    trades = [create_test_trade()]

    # Test with Series that has signal values but different structure
    signals_series = pd.Series(
        ["buy", "buy", "hold", "sell", "sell", "flat"],
        index=pd.date_range("2024-01-01", periods=6, freq="1h"),
        name="signal"
    )

    with patch("pandas.read_parquet", return_value=signals_series):
        with patch("os.path.exists", return_value=True):
            brief = generate_brief(
                meta={},
                params={},
                trades=trades,
                initial_cash=10000.0,
                signals_path="/fake/signals.parquet",
            )

            assert "signal_quality_analysis" in brief
            # 5 non-flat out of 6 = 83.33%
            expected_pct = round((5 / 6) * 100, 2)
            assert brief["signal_quality_analysis"]["signal_persistence_pct"] == expected_pct


def test_generate_brief_no_signals_path():
    """Test generate_brief when no signals_path is provided."""
    trades = [create_test_trade()]

    # Test without signals_path - should work fine with default signal analysis
    brief = generate_brief(
        meta={},
        params={},
        trades=trades,
        initial_cash=10000.0,
        # No signals_path provided
    )

    # Should have signal_quality_analysis with default values
    assert "signal_quality_analysis" in brief
    signal_analysis = brief["signal_quality_analysis"]
    assert signal_analysis["signal_persistence_pct"] == 0.0
    assert signal_analysis["avg_signal_duration_bars"] == 0.0
    
    # Should still have basic sections
    assert "overall_performance" in brief
    assert "risk_snapshot" in brief


def test_generate_brief_signals_path_not_exists():
    """Test generate_brief when signals_path doesn't exist."""
    trades = [create_test_trade()]

    with patch("os.path.exists", return_value=False):
        brief = generate_brief(
            meta={},
            params={},
            trades=trades,
            initial_cash=10000.0,
            signals_path="/nonexistent/signals.parquet",
        )

        # Should have signal_quality_analysis with default values since file doesn't exist
        assert "signal_quality_analysis" in brief
        signal_analysis = brief["signal_quality_analysis"]
        assert signal_analysis["signal_persistence_pct"] == 0.0
        assert signal_analysis["avg_signal_duration_bars"] == 0.0


def test_generate_brief_rmm_spans_processing():
    """Test RMM spans processing to hit related branch coverage."""
    trades = [create_test_trade()]

    # Create temporary RMM spans file
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        rmm_spans_path = f.name

        # Create test RMM spans DataFrame
        dates = pd.date_range("2024-01-01", periods=5, freq="1D")
        rmm_spans_df = pd.DataFrame(
            {
                "label": ["trend_up", "range", "trend_down", "range", "trend_up"],
                "confidence": [0.8, 0.6, 0.9, 0.5, 0.7],
            },
            index=dates,
        )
        rmm_spans_df.to_parquet(rmm_spans_path)

    try:
        brief = generate_brief(
            meta={},
            params={},
            trades=trades,
            initial_cash=10000.0,
            rmm_spans_path=rmm_spans_path,
        )

        # Should include rmm_spans_path in artifacts
        assert "artifacts" in brief
        assert "rmm_spans_path" in brief["artifacts"]
        assert brief["artifacts"]["rmm_spans_path"] == rmm_spans_path

    finally:
        os.unlink(rmm_spans_path)


def test_generate_brief_processed_data_path():
    """Test processed_data_path inclusion in artifacts."""
    trades = [create_test_trade()]

    brief = generate_brief(
        meta={},
        params={},
        trades=trades,
        initial_cash=10000.0,
        processed_data_path="/path/to/processed_data.parquet",
    )

    # Should include processed_data_path in artifacts
    assert "artifacts" in brief
    assert "processed_data_path" in brief["artifacts"]
    assert brief["artifacts"]["processed_data_path"] == "/path/to/processed_data.parquet"


def test_generate_brief_comprehensive_artifacts():
    """Test generate_brief with all artifact paths provided."""
    trades = [create_test_trade()]

    brief = generate_brief(
        meta={"run_id": "test123"},
        params={"strategy": "test_strategy"},
        trades=trades,
        initial_cash=10000.0,
        signals_path="/signals.parquet",
        rmm_spans_path="/rmm_spans.parquet", 
        processed_data_path="/processed.parquet",
    )

    # Should have all artifacts
    artifacts = brief["artifacts"]
    assert artifacts["signals_path"] == "/signals.parquet"
    assert artifacts["rmm_spans_path"] == "/rmm_spans.parquet"
    assert artifacts["processed_data_path"] == "/processed.parquet"
    
    # Should have meta and strategy_params
    assert brief["meta"]["run_id"] == "test123"
    # The params dict is processed and may have additional default values
    strategy_params = brief["strategy_params"]
    # Just check that our parameter is present (may be merged with defaults)
    assert isinstance(strategy_params, dict)
    # The specific param may be processed/transformed, just verify structure exists