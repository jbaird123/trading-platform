"""Provenance collection for reproducibility."""

import hashlib
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from trading_platform.ai.campaigns.models import Provenance


class ProvenanceCollector:
    """Collects provenance metadata for campaign reproducibility."""

    def __init__(self, project_root: Path | None = None):
        """Initialize provenance collector.

        Args:
            project_root: Root directory of project. Defaults to current directory.
        """
        self.project_root = project_root or Path.cwd()

    def capture(self) -> Provenance:
        """Capture current provenance metadata.

        Returns:
            Provenance object with all metadata.

        Raises:
            RuntimeError: If git working tree is dirty.
        """
        # Check git status
        git_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=True,
        )

        if git_status.stdout.strip():
            raise RuntimeError(
                "Git working tree is dirty. Commit or stash changes before "
                "capturing provenance."
            )

        # Get git commit
        git_commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        git_commit = git_commit_result.stdout.strip()

        # Get DVC version
        dvc_version_result = subprocess.run(
            ["dvc", "version", "--machine-readable"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse DVC version from output (first line is version)
        dvc_version = dvc_version_result.stdout.strip().split()[0]

        # Get DVC data snapshot ID
        data_snapshot_result = subprocess.run(
            ["git", "rev-parse", "HEAD:data.dvc"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        data_snapshot_id = data_snapshot_result.stdout.strip()

        # Compute poetry.lock SHA256
        poetry_lock_path = self.project_root / "poetry.lock"
        poetry_lock_sha256 = self._compute_sha256(poetry_lock_path)

        # Get Python version
        version_info = sys.version_info
        python_version = f"{version_info[0]}.{version_info[1]}.{version_info[2]}"

        # Get platform
        platform_info = platform.platform()

        # Get current timestamp
        captured_at = datetime.now(timezone.utc).isoformat()

        return Provenance(
            git_commit=git_commit,
            poetry_lock_sha256=poetry_lock_sha256,
            python_version=python_version,
            platform=platform_info,
            dvc_version=dvc_version,
            data_snapshot_id=data_snapshot_id,
            captured_at=captured_at,
        )

    def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file.

        Args:
            file_path: Path to file.

        Returns:
            Hex-encoded SHA256 hash.
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
