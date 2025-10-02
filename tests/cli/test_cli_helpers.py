"""Tests for CLI helper functions."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


def test_get_git_commit_success() -> None:
    """Test _get_git_commit returns short hash on success."""
    # Validates: [REQ-CLI-HELPER-001] Get git commit hash
    from trading_platform.cli import _get_git_commit

    with patch("trading_platform.cli.subprocess.check_output") as mock_check:
        mock_check.return_value = b"abc123\n"
        result = _get_git_commit()
        assert result == "abc123"


def test_get_git_commit_failure() -> None:
    """Test _get_git_commit returns None on failure."""
    # Validates: [REQ-CLI-HELPER-002] Handle git command failure
    from trading_platform.cli import _get_git_commit

    with patch("trading_platform.cli.subprocess.check_output") as mock_check:
        mock_check.side_effect = Exception("git not found")
        result = _get_git_commit()
        assert result is None


def test_load_config_json(tmp_path: Path) -> None:
    """Test _load_config loads JSON files."""
    # Validates: [REQ-CLI-HELPER-003] Load JSON config
    from trading_platform.cli import _load_config

    config_path = tmp_path / "config.json"
    config_data = {"test": "value", "number": 42}
    config_path.write_text(json.dumps(config_data))

    result = _load_config(config_path)
    assert result == config_data


def test_load_config_yaml(tmp_path: Path) -> None:
    """Test _load_config loads YAML files."""
    # Validates: [REQ-CLI-HELPER-004] Load YAML config
    pytest.importorskip("yaml")

    from trading_platform.cli import _load_config

    config_path = tmp_path / "config.yaml"
    config_path.write_text("test: value\nnumber: 42")

    result = _load_config(config_path)
    assert result["test"] == "value"
    assert result["number"] == 42


def test_find_last_briefs_returns_most_recent(tmp_path: Path) -> None:
    """Test _find_last_briefs returns N most recent briefs by mtime."""
    # Validates: [REQ-CLI-HELPER-005] Find last N briefs
    from trading_platform.cli import _find_last_briefs
    import time

    runs_dir = tmp_path / "runs"
    user_dir = runs_dir / "test_user"
    user_dir.mkdir(parents=True)

    # Create 3 run directories with briefs at different times
    for i in range(3):
        run_dir = user_dir / f"run_{i}"
        run_dir.mkdir()
        brief = run_dir / "brief.json"
        brief.write_text(json.dumps({"run_id": f"run_{i}"}))
        time.sleep(0.01)  # Ensure different mtimes

    results = _find_last_briefs(runs_dir, "test_user", 2)

    assert len(results) == 2
    # Should return most recent (run_2 and run_1)
    assert "run_2" in str(results[0]) or "run_1" in str(results[0])


def test_find_last_briefs_nonexistent_dir(tmp_path: Path) -> None:
    """Test _find_last_briefs returns empty list for nonexistent directory."""
    # Validates: [REQ-CLI-HELPER-006] Handle nonexistent runs directory
    from trading_platform.cli import _find_last_briefs

    results = _find_last_briefs(tmp_path / "nonexistent", "user", 5)
    assert results == []


def test_find_last_briefs_no_user_specified(tmp_path: Path) -> None:
    """Test _find_last_briefs searches runs_dir directly when no user."""
    # Validates: [REQ-CLI-HELPER-007] Search without user subdirectory
    from trading_platform.cli import _find_last_briefs

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True)

    # Create run directly in runs_dir
    run_dir = runs_dir / "run_0"
    run_dir.mkdir()
    brief = run_dir / "brief.json"
    brief.write_text(json.dumps({"run_id": "run_0"}))

    results = _find_last_briefs(runs_dir, None, 1)

    assert len(results) == 1
    assert "run_0" in str(results[0])
