import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from trading_platform.cli import (
    _get_git_commit,
    _load_config,
    cmd_ai_diagnose,
    cmd_compare,
    cmd_open_chart,
    cmd_run_backtest,
    cmd_run_live,
)


class TestGitCommitErrorHandling:
    """Test error handling in _get_git_commit function."""

    def test_get_git_commit_subprocess_error(self):
        """Tests _get_git_commit when subprocess fails. Covers lines 48-49."""
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.side_effect = subprocess.CalledProcessError(1, "git")
            result = _get_git_commit()
            assert result is None

    def test_get_git_commit_other_exception(self):
        """Tests _get_git_commit when other exception occurs. Covers lines 48-49."""
        with patch("subprocess.check_output") as mock_subprocess:
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
            with patch("builtins.__import__") as mock_import:

                def side_effect(name, *args, **kwargs):
                    if name == "yaml":
                        raise ImportError("No module named 'yaml'")
                    return __import__(name, *args, **kwargs)

                mock_import.side_effect = side_effect

                with pytest.raises(SystemExit) as exc_info:
                    _load_config(config_path)

                # Should exit with error message about PyYAML
                assert "PyYAML is not installed" in str(exc_info.value)


class TestDataProcessingErrorHandling:
    """Test error handling in data processing."""

    def test_run_backtest_without_config_argument(self):
        """run_backtest should error when --config is omitted."""
        # Create args namespace without config
        args = argparse.Namespace(config=None, user="test_user", demo=False)

        # Should return error code 2 and print error message
        result = cmd_run_backtest(args)
        assert result == 2


class TestArgumentParsingEdgeCases:
    """Test argument parsing edge cases."""

    def test_run_backtest_missing_config_file(self):
        """Tests error when config file doesn't exist. Covers error handling paths."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "nonexistent.json"
            Path(tmp_dir) / "run"

            # Create args namespace
            args = argparse.Namespace(config=config_path, user="test_user", demo=False)

            with pytest.raises(FileNotFoundError):
                cmd_run_backtest(args)

    def test_run_live_missing_config_file(self):
        """Tests error when live config file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "nonexistent.json"

            # Create args namespace
            args = argparse.Namespace(config=config_path, dry_run=False)

            with pytest.raises(FileNotFoundError):
                cmd_run_live(args)


class TestFileValidationEdgeCases:
    """Test file path validation edge cases."""

    def test_compare_invalid_brief_paths(self):
        """Tests compare command with invalid brief file paths."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create only one valid brief
            brief1_path = Path(tmp_dir) / "brief1.json"
            brief1_path.write_text('{"metadata": {"run_id": "test1"}}')

            brief2_path = Path(tmp_dir) / "nonexistent.json"

            # Create args namespace
            args = argparse.Namespace(
                a=brief1_path,
                b=brief2_path,
                out="comparison.html",
                last=0,
                runs_dir="runs",
                user=None,
            )

            # Should return error code and print error message instead of raising
            result = cmd_compare(args)
            assert result == 2  # Error code for missing file

    def test_ai_diagnose_invalid_brief_path(self):
        """Tests AI diagnose with invalid brief path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            brief_path = Path(tmp_dir) / "nonexistent.json"

            # Create args namespace
            args = argparse.Namespace(brief=brief_path)

            with pytest.raises(ValueError, match="No such file"):
                cmd_ai_diagnose(args)

    def test_open_chart_no_runs_found(self):
        """Tests open chart when no runs are found."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create args namespace with empty runs directory
            args = argparse.Namespace(runs_dir=tmp_dir, user=None, last=1, open=False)

            # Should return error code 2 and print "No runs found."
            result = cmd_open_chart(args)
            assert result == 2


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
            # Create truly invalid YAML with tab indentation (not allowed in YAML)
            config_path.write_text("invalid:\n\t- yaml: content\n\tmalformed")

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
                "strategy": None,  # Invalid strategy
                "risk_manager": {"enabled": False},
                "rmm": {"enabled": False},
            }
            config_path.write_text(json.dumps(config))

            # Create args namespace
            args = argparse.Namespace(config=config_path, user="test_user", demo=False)

            # Should raise ValidationError for None strategy
            from pydantic_core import ValidationError

            with pytest.raises(ValidationError):
                cmd_run_backtest(args)
