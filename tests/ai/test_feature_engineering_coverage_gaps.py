"""
Test coverage gaps in AI Feature Engineering modules.

Targets specific missing lines in ai/feature_engineering/
modules to improve coverage.
"""

import importlib
import os
import runpy
import sys
from io import StringIO
from unittest.mock import patch

import pandas as pd


def test_feature_engineering_pipeline_main_block():
    """Test the __main__ execution block in pipeline.py. Covers lines 73-104."""

    # Add src to path if not already there
    test_dir = os.path.dirname(__file__)
    src_path = os.path.abspath(os.path.join(test_dir, "../../src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Capture stdout to verify the main block runs
    captured_output = StringIO()
    module_name = "trading_platform.ai.feature_engineering.pipeline"
    package_name = "trading_platform.ai.feature_engineering"

    saved_module = sys.modules.get(module_name)
    package = sys.modules.get(package_name)
    saved_attr = None
    if package is not None and hasattr(package, "pipeline"):
        saved_attr = package.pipeline
        delattr(package, "pipeline")
    if module_name in sys.modules:
        del sys.modules[module_name]

    with patch("sys.stdout", captured_output), patch("sys.argv", ["pipeline.py"]):
        try:
            runpy.run_module(module_name, run_name="__main__")
        except SystemExit:
            pass  # Ignore SystemExit if any
        finally:
            if saved_module is not None:
                sys.modules[module_name] = saved_module
            else:
                sys.modules.pop(module_name, None)

            package = sys.modules.get(package_name)
            if package is not None:
                if saved_attr is not None:
                    setattr(package, "pipeline", saved_attr)
                elif hasattr(package, "pipeline"):
                    delattr(package, "pipeline")
            elif saved_attr is not None:
                training_pkg = importlib.import_module(package_name)
                setattr(training_pkg, "pipeline", saved_attr)

    # Verify the main block executed
    output = captured_output.getvalue()
    assert "Running feature engineering for 2 features..." in output
    assert "Feature engineering complete." in output
    assert "DataFrame with new features:" in output


def test_feature_engineering_pipeline_example_data():
    """Test FeatureEngineeringPipeline with larger dataset to avoid NaN dropouts."""

    # Import here to avoid module import order issues
    from trading_platform.ai.feature_engineering.pipeline import (
        FeatureEngineeringPipeline,
    )

    # Create larger dataset to avoid all rows being dropped by indicators with window=14
    dates = pd.date_range("2023-01-01", periods=20, freq="D")
    data = {
        "timestamp": dates,
        "open": [1.0 + i * 0.01 for i in range(20)],
        "high": [1.1 + i * 0.01 for i in range(20)],
        "low": [0.95 + i * 0.01 for i in range(20)],
        "close": [1.05 + i * 0.01 for i in range(20)],
        "volume": [100 + i * 5 for i in range(20)],
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
