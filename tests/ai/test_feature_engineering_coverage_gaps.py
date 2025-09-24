"""
Test coverage gaps in AI Feature Engineering modules.

Targets specific missing lines in ai/feature_engineering/ modules to improve coverage.
"""
import pandas as pd
import pytest
from unittest.mock import patch, call
from io import StringIO
import sys

from trading_platform.ai.feature_engineering.pipeline import FeatureEngineeringPipeline


def test_feature_engineering_pipeline_main_block():
    """Test the __main__ execution block in pipeline.py. Covers lines 73-104."""
    
    # Use runpy to execute the module as a script, which should be captured by coverage
    import runpy
    import sys
    import os
    from unittest.mock import patch
    from io import StringIO
    
    # Add src to path if not already there
    src_path = "/Users/jbaird/Documents/personal/trading-platform/src"
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    # Capture stdout to verify the main block runs
    captured_output = StringIO()
    
    with patch('sys.stdout', captured_output), patch('sys.argv', ['pipeline.py']):
        try:
            # Execute the module as a script
            runpy.run_module('trading_platform.ai.feature_engineering.pipeline', run_name='__main__')
        except SystemExit:
            pass  # Ignore SystemExit if any
    
    # Verify the main block executed
    output = captured_output.getvalue()
    assert "Running feature engineering for 2 features..." in output
    assert "Feature engineering complete." in output
    assert "DataFrame with new features:" in output


def test_feature_engineering_pipeline_example_data():
    """Test FeatureEngineeringPipeline with larger dataset to avoid NaN dropouts."""
    
    # Create larger dataset to avoid all rows being dropped by indicators with window=14
    dates = pd.date_range("2023-01-01", periods=20, freq='D')
    data = {
        "timestamp": dates,
        "open": [1.0 + i*0.01 for i in range(20)],
        "high": [1.1 + i*0.01 for i in range(20)],
        "low": [0.95 + i*0.01 for i in range(20)],
        "close": [1.05 + i*0.01 for i in range(20)],
        "volume": [100 + i*5 for i in range(20)],
    }
    sample_df = pd.DataFrame(data).set_index("timestamp")

    # Test both the buggy format from main block and the working format
    # This tests the actual main block behavior (using defaults due to bug)
    features_to_add_buggy = [
        {"kind": "sma", "length": 2},  # This will default to length=14 due to bug
        {"kind": "rsi", "length": 2},  # This will default to length=14 due to bug
    ]

    # Execute pipeline as in main block (demonstrates the bug)
    pipeline_buggy = FeatureEngineeringPipeline(sample_df)
    featured_df_buggy = pipeline_buggy.run(features_to_add_buggy)

    # Due to bug, it uses default length=14, so some rows may be present
    assert "close" in featured_df_buggy.columns  # Original column preserved
    assert "sma_14" in featured_df_buggy.columns  # Default length used
    assert "rsi_14" in featured_df_buggy.columns  # Default length used

    # Test proper format that actually works
    features_to_add_correct = [
        {"kind": "sma", "params": {"length": 2}},
        {"kind": "rsi", "params": {"length": 2}},
    ]

    pipeline_correct = FeatureEngineeringPipeline(sample_df)
    featured_df_correct = pipeline_correct.run(features_to_add_correct)

    # Validate results with correct format
    assert not featured_df_correct.empty
    assert "close" in featured_df_correct.columns  # Original column preserved
    assert "sma_2" in featured_df_correct.columns  # Correct length used
    assert "rsi_2" in featured_df_correct.columns  # Correct length used