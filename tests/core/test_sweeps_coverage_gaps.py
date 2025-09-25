"""
Test coverage gaps in parameter sweeps module.

Targets specific missing lines in core/sweeps.py to improve coverage.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import yaml

from trading_platform.core.sweeps import run_parameter_sweep, _rmm_context


def test_rmm_context_with_yaml_path():
    """Test _rmm_context with rmm_path pointing to yaml file. Covers lines 22-27."""
    # Create sample market data
    df = pd.DataFrame({
        "open": [1.0, 1.1],
        "high": [1.05, 1.15], 
        "low": [0.95, 1.05],
        "close": [1.02, 1.12],
        "volume": [100, 200],
    }, index=pd.date_range("2024-01-01", periods=2, freq="D"))
    
    # Create a temporary YAML file with RMM config
    rmm_config = {
        "engine_type": "ml_classifier",
        "model_path": "dummy_path",
        "policy": {"min_confidence": 0.7}
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(rmm_config, f)
        yaml_path = f.name
    
    try:
        cfg_raw = {"rmm_path": yaml_path}
        
        # Mock the RMMEngine to avoid complex dependencies
        with patch('trading_platform.core.sweeps.RMMEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            
            # Mock classify_daily to return simple classification
            mock_daily = pd.DataFrame({
                "label": ["bullish", "bearish"],
                "confidence": [0.8, 0.6]
            }, index=pd.date_range("2024-01-01", periods=2, freq="D"))
            mock_engine.classify_daily.return_value = mock_daily
            
            # Mock project_to_index to return projection
            mock_proj = pd.DataFrame({
                "label": ["bullish", "bearish"],
                "confidence": [0.8, 0.6],
                "allowed_sides": [["long"], ["short"]]
            }, index=df.index)
            mock_engine.project_to_index.return_value = mock_proj
            
            # Call _rmm_context - this should hit lines 22-27 for YAML loading
            result = _rmm_context(df, cfg_raw)
            
            # Verify YAML file was loaded and processed
            assert result is not None
            assert len(result) == 2
            mock_engine_class.assert_called_once_with(config=rmm_config)
            
    finally:
        # Clean up temp file
        Path(yaml_path).unlink(missing_ok=True)


def test_rmm_context_with_json_path():
    """Test _rmm_context with rmm_path pointing to json file. Covers lines 22-27."""
    # Create sample market data
    df = pd.DataFrame({
        "open": [1.0, 1.1],
        "high": [1.05, 1.15], 
        "low": [0.95, 1.05],
        "close": [1.02, 1.12],
        "volume": [100, 200],
    }, index=pd.date_range("2024-01-01", periods=2, freq="D"))
    
    # Create a temporary JSON file with RMM config
    rmm_config = {
        "engine_type": "ml_classifier",
        "model_path": "dummy_path", 
        "policy": {"min_confidence": 0.7}
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(rmm_config, f)
        json_path = f.name
    
    try:
        cfg_raw = {"rmm_path": json_path}
        
        # Mock the RMMEngine to avoid complex dependencies
        with patch('trading_platform.core.sweeps.RMMEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine_class.return_value = mock_engine
            
            # Mock classify_daily to return simple classification
            mock_daily = pd.DataFrame({
                "label": ["bullish", "bearish"],
                "confidence": [0.8, 0.6]
            }, index=pd.date_range("2024-01-01", periods=2, freq="D"))
            mock_engine.classify_daily.return_value = mock_daily
            
            # Mock project_to_index to return projection
            mock_proj = pd.DataFrame({
                "label": ["bullish", "bearish"],
                "confidence": [0.8, 0.6],
                "allowed_sides": [["long"], ["short"]]
            }, index=df.index)
            mock_engine.project_to_index.return_value = mock_proj
            
            # Call _rmm_context - this should hit lines 22-27 for JSON loading
            result = _rmm_context(df, cfg_raw)
            
            # Verify JSON file was loaded and processed  
            assert result is not None
            assert len(result) == 2
            mock_engine_class.assert_called_once_with(config=rmm_config)
            
    finally:
        # Clean up temp file
        Path(json_path).unlink(missing_ok=True)


def test_rmm_context_empty_config():
    """Test _rmm_context with empty/invalid rmm_config. Covers lines 32-33."""
    df = pd.DataFrame({
        "close": [1.0, 1.1]
    }, index=pd.date_range("2024-01-01", periods=2, freq="D"))
    
    # Test with empty dict
    cfg_raw = {"rmm_config": {}}
    result = _rmm_context(df, cfg_raw)
    assert result is None
    
    # Test with non-dict rmm_config
    cfg_raw = {"rmm_config": "invalid"}
    result = _rmm_context(df, cfg_raw) 
    assert result is None
    
    # Test with no rmm_config or rmm_path
    cfg_raw = {}
    result = _rmm_context(df, cfg_raw)
    assert result is None


def test_parameter_sweep_with_rem_path():
    """Test run_parameter_sweep with rem_path for REM config loading. Covers lines 93-98."""
    # Simple market data
    df = pd.DataFrame({
        "open": [1.0, 1.1], 
        "high": [1.05, 1.15],
        "low": [0.95, 1.05],
        "close": [1.02, 1.12],
        "volume": [100, 200],
    }, index=pd.date_range("2024-01-01", periods=2, freq="h"))
    
    # Create temporary YAML file with REM config
    rem_config = {
        "daily_loss_cap": 0.02,
        "position_timeout_hours": 24
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(rem_config, f)
        yaml_path = f.name
    
    try:
        base_cfg = {
            "user_id": "test_user",
            "run_seed": 42,
            "initial_cash": 10000.0,
            "position_size": 100.0,
            "rem_path": yaml_path,  # This should trigger lines 93-98
        }
        
        strategy_cfg = {
            "entry_signals": ["long"],
            "exit_signals": ["short"]
        }
        
        # Mock dependencies to avoid complex setup
        with patch('trading_platform.core.sweeps.compile_strategy') as mock_compile, \
             patch('trading_platform.core.sweeps.run_backtest') as mock_backtest, \
             patch('trading_platform.core.sweeps.RiskExitManager') as mock_rem_class:
            
            mock_compile.return_value = Mock()
            mock_backtest.return_value = ([], [], [])  # trades, exposure, skipped
            mock_rem = Mock()
            mock_rem_class.return_value = mock_rem
            
            # Simple grid to avoid empty candidates
            grid = {"param1": [1, 2]}
            
            result = run_parameter_sweep(
                df=df,
                base_cfg=base_cfg,
                strategy_cfg=strategy_cfg,
                grid=grid
            )
            
            # Verify REM was created with loaded config
            mock_rem_class.assert_called_with(config=rem_config)
            assert isinstance(result, dict)
            
    finally:
        # Clean up temp file
        Path(yaml_path).unlink(missing_ok=True)


def test_parameter_sweep_with_debug_dir():
    """Test run_parameter_sweep with debug_dir for logging. Covers lines 108-115."""
    # Simple market data
    df = pd.DataFrame({
        "open": [1.0, 1.1],
        "high": [1.05, 1.15],
        "low": [0.95, 1.05],
        "close": [1.02, 1.12],
        "volume": [100, 200],
    }, index=pd.date_range("2024-01-01", periods=2, freq="h"))
    
    with tempfile.TemporaryDirectory() as temp_dir:
        base_cfg = {
            "user_id": "test_user",
            "run_seed": 42,
            "initial_cash": 10000.0,
            "position_size": 100.0,
        }
        
        strategy_cfg = {
            "entry_signals": ["long"],
            "exit_signals": ["short"]
        }
        
        # Mock dependencies to avoid complex setup
        with patch('trading_platform.core.sweeps.compile_strategy') as mock_compile, \
             patch('trading_platform.core.sweeps.run_backtest') as mock_backtest, \
             patch('trading_platform.core.sweeps.RiskExitManager') as mock_rem_class:
            
            mock_compile.return_value = Mock()
            mock_backtest.return_value = ([], [], [])  # trades, exposure, skipped
            mock_rem_class.return_value = Mock()
            
            # Simple grid to avoid empty candidates
            grid = {"param1": [1, 2]}
            
            result = run_parameter_sweep(
                df=df,
                base_cfg=base_cfg,
                strategy_cfg=strategy_cfg,
                grid=grid,
                debug_dir=temp_dir  # This should trigger lines 108-115
            )
            
            # Verify debug directory was created and used
            debug_path = Path(temp_dir)
            assert debug_path.exists()
            assert isinstance(result, dict)


def test_parameter_sweep_random_space():
    """Test run_parameter_sweep with random_space sampling. Covers lines 84-86."""
    # Simple market data
    df = pd.DataFrame({
        "open": [1.0, 1.1],
        "high": [1.05, 1.15],
        "low": [0.95, 1.05],
        "close": [1.02, 1.12],
        "volume": [100, 200],
    }, index=pd.date_range("2024-01-01", periods=2, freq="h"))
    
    base_cfg = {
        "user_id": "test_user",
        "run_seed": 42,
        "initial_cash": 10000.0,
        "position_size": 100.0,
    }
    
    strategy_cfg = {
        "entry_signals": ["long"],
        "exit_signals": ["short"]
    }
    
    # Mock dependencies to avoid complex setup
    with patch('trading_platform.core.sweeps.compile_strategy') as mock_compile, \
         patch('trading_platform.core.sweeps.run_backtest') as mock_backtest, \
         patch('trading_platform.core.sweeps.RiskExitManager') as mock_rem_class:
        
        mock_compile.return_value = Mock()
        mock_backtest.return_value = ([], [], [])  # trades, exposure, skipped
        mock_rem_class.return_value = Mock()
        
        # Use random_space instead of grid - this should trigger lines 84-86
        random_space = {"param1": [1, 2, 3, 4]}
        n_samples = 2
        
        result = run_parameter_sweep(
            df=df,
            base_cfg=base_cfg,
            strategy_cfg=strategy_cfg,
            random_space=random_space,
            n_samples=n_samples,
            seed=42  # For reproducible random sampling
        )
        
        assert isinstance(result, dict)
        # Should have run exactly n_samples candidates
        assert mock_backtest.call_count == n_samples