"""Tests for ProvenanceCollector."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from trading_platform.ai.campaigns.provenance import ProvenanceCollector


@pytest.fixture
def mock_git_commit():
    """Mock git commit hash."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="abc1234567890def\n", returncode=0)
        yield mock_run


@pytest.fixture
def mock_poetry_lock(tmp_path):
    """Mock poetry.lock file."""
    lock_file = tmp_path / "poetry.lock"
    lock_file.write_text("# Poetry lock file\n[metadata]\nlock-version = '2.0'\n")
    return lock_file


def test_capture_returns_provenance_with_all_fields(tmp_path):
    """Test that capture() returns Provenance with all required fields."""
    # Create poetry.lock in tmp_path
    poetry_lock = tmp_path / "poetry.lock"
    poetry_lock.write_text("# Poetry lock\n")

    collector = ProvenanceCollector(project_root=tmp_path)

    with patch("platform.platform", return_value="Darwin-25.0.0"):
        with patch("sys.version_info", (3, 13, 8, "final", 0)):
            with patch("subprocess.run") as mock_run:
                # Mock git status (clean)
                git_status = MagicMock(stdout="", returncode=0)
                # Mock git commit
                git_commit = MagicMock(stdout="abc123\n", returncode=0)
                # Mock DVC version (proper format: "DVC version: X.Y.Z")
                dvc_version = MagicMock(stdout="DVC version: 3.63.0\n", returncode=0)
                # Mock data snapshot
                data_snapshot = MagicMock(stdout="d4t4v3rs10n\n", returncode=0)

                mock_run.side_effect = [
                    git_status,
                    git_commit,
                    dvc_version,
                    data_snapshot,
                ]

                provenance = collector.capture()

                assert provenance.git_commit == "abc123"
                assert provenance.python_version == "3.13.8"
                assert provenance.platform == "Darwin-25.0.0"
                assert provenance.dvc_version == "3.63.0"
                assert provenance.data_snapshot_id == "d4t4v3rs10n"
                assert len(provenance.poetry_lock_sha256) == 64  # SHA256 hex length
                assert provenance.captured_at  # Should be ISO timestamp


def test_capture_raises_if_git_dirty(tmp_path):
    """Test that capture() raises if git working tree is dirty."""
    collector = ProvenanceCollector(project_root=tmp_path)

    with patch("subprocess.run") as mock_run:
        # Mock git status showing dirty tree
        mock_run.return_value = MagicMock(stdout="M file.py\n", returncode=0)

        with pytest.raises(RuntimeError, match="dirty"):
            collector.capture()


def test_capture_computes_poetry_lock_sha256(tmp_path):
    """Test that capture() computes SHA256 of poetry.lock."""
    # Create poetry.lock in tmp_path
    poetry_lock = tmp_path / "poetry.lock"
    poetry_lock.write_text("# Poetry lock file\n[metadata]\nlock-version = '2.0'\n")

    collector = ProvenanceCollector(project_root=tmp_path)

    with patch("subprocess.run") as mock_run:
        # Mock git clean status
        git_status = MagicMock(stdout="", returncode=0)
        # Mock git commit
        git_commit = MagicMock(stdout="abc123\n", returncode=0)
        # Mock DVC version
        dvc_version = MagicMock(stdout="3.63.0\n", returncode=0)
        # Mock data snapshot
        data_snapshot = MagicMock(stdout="d4t4v3rs10n\n", returncode=0)

        mock_run.side_effect = [
            git_status,
            git_commit,
            dvc_version,
            data_snapshot,
        ]

        with patch("platform.platform", return_value="Darwin"):
            with patch("sys.version_info", (3, 13, 8, "final", 0)):
                provenance = collector.capture()

                # SHA256 should be 64 hex characters
                assert len(provenance.poetry_lock_sha256) == 64
                assert all(
                    c in "0123456789abcdef" for c in provenance.poetry_lock_sha256
                )


def test_capture_gets_dvc_data_snapshot(tmp_path):
    """Test that capture() gets DVC data snapshot ID."""
    # Create poetry.lock in tmp_path
    poetry_lock = tmp_path / "poetry.lock"
    poetry_lock.write_text("# Poetry lock\n")

    collector = ProvenanceCollector(project_root=tmp_path)

    with patch("subprocess.run") as mock_run:
        # Mock git clean status
        git_status = MagicMock(stdout="", returncode=0)
        # Mock git commit
        git_commit = MagicMock(stdout="abc123\n", returncode=0)
        # Mock DVC version
        dvc_version = MagicMock(stdout="3.63.0\n", returncode=0)
        # Mock data snapshot
        data_snapshot = MagicMock(stdout="snapshot123\n", returncode=0)

        mock_run.side_effect = [
            git_status,
            git_commit,
            dvc_version,
            data_snapshot,
        ]

        with patch("platform.platform", return_value="Darwin"):
            with patch("sys.version_info", (3, 13, 8, "final", 0)):
                provenance = collector.capture()

                assert provenance.data_snapshot_id == "snapshot123"


def test_captured_at_is_iso_timestamp(tmp_path):
    """Test that captured_at is valid ISO 8601 timestamp."""
    # Create poetry.lock in tmp_path
    poetry_lock = tmp_path / "poetry.lock"
    poetry_lock.write_text("# Poetry lock\n")

    collector = ProvenanceCollector(project_root=tmp_path)

    with patch("subprocess.run") as mock_run:
        # Mock all subprocess calls
        git_status = MagicMock(stdout="", returncode=0)
        git_commit = MagicMock(stdout="abc123\n", returncode=0)
        dvc_version = MagicMock(stdout="3.63.0\n", returncode=0)
        data_snapshot = MagicMock(stdout="d4t4\n", returncode=0)

        mock_run.side_effect = [
            git_status,
            git_commit,
            dvc_version,
            data_snapshot,
        ]

        with patch("platform.platform", return_value="Darwin"):
            with patch("sys.version_info", (3, 13, 8, "final", 0)):
                provenance = collector.capture()

                # Should be parseable as ISO timestamp
                timestamp = datetime.fromisoformat(provenance.captured_at)
                assert timestamp.tzinfo is not None  # Should have timezone
