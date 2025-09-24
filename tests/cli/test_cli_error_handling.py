import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from trading_platform.cli import (
    _get_git_commit,
    _load_config,
    cmd_run_backtest,
    cmd_run_live,
    cmd_compare,
    cmd_ai_diagnose,
    cmd_open_chart
)


class TestGitCommitErrorHandling:
    """Test error handling in _get_git_commit function."""
    
    def test_get_git_commit_subprocess_error(self):
        """Tests _get_git_commit when subprocess fails. Covers lines 48-49."""
        with patch('subprocess.check_output') as mock_subprocess:
            mock_subprocess.side_effect = subprocess.CalledProcessError(1, "git")
            result = _get_git_commit()
            assert result is None
    
    def test_get_git_commit_other_exception(self):
        """Tests _get_git_commit when other exception occurs. Covers lines 48-49."""
        with patch('subprocess.check_output') as mock_subprocess:
            mock_subprocess.side_effect = OSError("Git not found")
            result = _get_git_commit()
            assert result is None


class TestConfigLoadingErrorHandling:
    """Test error handling in configuration loading."""
    
    def test_load_config_yaml_import_error(self):
        """Tests _load_config when PyYAML import fails. Covers lines 56-61."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "test.yaml"
            config_path.write_text("key: value")
            
            # Mock the yaml import to raise ImportError
            with patch('builtins.__import__') as mock_import:
                def side_effect(name, *args, **kwargs):
                    if name == 'yaml':
                        raise ImportError("No module named 'yaml'")
                    return __import__(name, *args, **kwargs)
                
                mock_import.side_effect = side_effect
                
                with pytest.raises(SystemExit) as exc_info:
                    _load_config(config_path)
                
                # Should exit with error message about PyYAML
                assert "PyYAML is not installed" in str(exc_info.value)


class TestDataProcessingErrorHandling:
    """Test error handling in data processing."""
    
    def test_run_backtest_data_processing_exception(self):
        """Tests data processing exception handling. Covers lines 109-110."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_path = Path(tmp_dir)
            
            # Create a minimal valid config
            config = {
                "data_request": {"symbol": "EURUSD", "timeframe": "1H"},
                "strategy": {"strategy_name": "test"},
                "risk_manager": {"enabled": False},
                "rmm": {"enabled": False}
            }
            config_path = run_path / "config.json"
            config_path.write_text(json.dumps(config))
            
            # Mock load_from_catalog to return data, then mock df.to_parquet to raise exception
            mock_df = Mock()
            mock_df.to_parquet.side_effect = OSError("Permission denied")
            
            with patch('trading_platform.cli.load_from_catalog') as mock_load:
                with patch('trading_platform.cli.run_backtest') as mock_backtest:
                    with patch('trading_platform.cli.finalize_run') as mock_finalize:
                        mock_load.return_value = (mock_df, [])
                        mock_backtest.return_value = Mock(successful=True)
                        
                        # Should not raise exception, should handle gracefully
                        result = cmd_run_backtest(config_path, run_path)
                        
                        # Verify it tried to save and caught the exception
                        mock_df.to_parquet.assert_called_once()


class TestArgumentParsingEdgeCases:
    """Test argument parsing edge cases."""
    
    def test_run_backtest_missing_config_file(self):
        """Tests error when config file doesn't exist. Covers error handling paths."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "nonexistent.json"
            run_path = Path(tmp_dir) / "run"
            
            with pytest.raises(FileNotFoundError):
                cmd_run_backtest(config_path, run_path)
    
    def test_run_live_missing_config_file(self):
        """Tests error when live config file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "nonexistent.json"
            
            with pytest.raises(FileNotFoundError):
                cmd_run_live(config_path)


class TestFileValidationEdgeCases:
    """Test file path validation edge cases."""
    
    def test_compare_invalid_brief_paths(self):
        """Tests compare command with invalid brief file paths."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create only one valid brief
            brief1_path = Path(tmp_dir) / "brief1.json"
            brief1_path.write_text('{"metadata": {"run_id": "test1"}}')
            
            brief2_path = Path(tmp_dir) / "nonexistent.json"
            
            with pytest.raises(FileNotFoundError):
                cmd_compare(brief1_path, brief2_path)
    
    def test_ai_diagnose_invalid_brief_path(self):
        """Tests AI diagnose with invalid brief path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            brief_path = Path(tmp_dir) / "nonexistent.json"
            
            with pytest.raises(FileNotFoundError):
                cmd_ai_diagnose(brief_path)
    
    def test_open_chart_invalid_brief_path(self):
        """Tests open chart with invalid brief path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            brief_path = Path(tmp_dir) / "nonexistent.json"
            
            with pytest.raises(FileNotFoundError):
                cmd_open_chart(brief_path)


class TestConfigurationLoadingFailures:
    """Test configuration loading failure scenarios."""
    
    def test_load_config_malformed_json(self):
        """Tests _load_config with malformed JSON."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "bad.json"
            config_path.write_text('{"invalid": json}')  # Invalid JSON
            
            with pytest.raises(json.JSONDecodeError):
                _load_config(config_path)
    
    def test_load_config_malformed_yaml(self):
        """Tests _load_config with malformed YAML."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "bad.yaml"
            config_path.write_text('invalid:\n  - yaml: content\n    missing: bracket')
            
            # Only test if PyYAML is available
            try:
                import yaml
                with pytest.raises(yaml.YAMLError):
                    _load_config(config_path)
            except ImportError:
                pytest.skip("PyYAML not available for YAML error testing")


class TestCommandExecutionErrorPaths:
    """Test command execution error handling."""
    
    def test_run_backtest_with_invalid_strategy_config(self):
        """Tests run_backtest with invalid strategy configuration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            run_path = Path(tmp_dir) / "run"
            run_path.mkdir()
            
            # Config with invalid strategy
            config = {
                "data_request": None,  # Will trigger toy data
                "strategy": None,      # Invalid strategy
                "risk_manager": {"enabled": False},
                "rmm": {"enabled": False}
            }
            config_path.write_text(json.dumps(config))
            
            # Mock dependencies to focus on strategy handling
            with patch('trading_platform.cli.run_backtest') as mock_backtest:
                with patch('trading_platform.cli.finalize_run') as mock_finalize:
                    # Should handle None strategy gracefully by using defaults
                    mock_backtest.return_value = Mock(successful=True)
                    
                    result = cmd_run_backtest(config_path, run_path)
                    
                    # Verify backtest was called (meaning it handled the None strategy)
                    mock_backtest.assert_called_once()