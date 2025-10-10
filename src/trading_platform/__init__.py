from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _ensure_cache_dir(path: Path) -> bool:
    """Try to make sure the given path is writable for numba caches."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".tp_numba_write_test"
        with probe.open("w") as fh:
            fh.write("0")
        probe.unlink(missing_ok=True)
    except OSError:
        return False
    else:
        return True


if "NUMBA_CACHE_DIR" in os.environ:
    _candidate = Path(os.environ["NUMBA_CACHE_DIR"]).expanduser()
    if not _ensure_cache_dir(_candidate):
        # Existing env var is unusable; fall back to repo-managed cache dirs.
        project_root = Path(__file__).resolve().parents[2]
        workspace_dir = project_root / "workspace"
        fallback_candidates = [
            workspace_dir / "cache" / "numba",
            project_root / ".cache" / "numba",
        ]
        for fallback in fallback_candidates:
            if _ensure_cache_dir(fallback):
                os.environ["NUMBA_CACHE_DIR"] = str(fallback)
                break
        else:
            _fallback = Path(tempfile.mkdtemp(prefix="numba_cache_"))
            os.environ["NUMBA_CACHE_DIR"] = str(_fallback)
else:
    # Configure numba cache directory before any imports that use numba.
    project_root = Path(__file__).resolve().parents[2]
    workspace_dir = project_root / "workspace"
    candidates = [
        workspace_dir / "cache" / "numba",
        project_root / ".cache" / "numba",
    ]
    for candidate in candidates:
        if _ensure_cache_dir(candidate):
            os.environ["NUMBA_CACHE_DIR"] = str(candidate)
            break
    else:
        _fallback = Path(tempfile.mkdtemp(prefix="numba_cache_"))
        os.environ["NUMBA_CACHE_DIR"] = str(_fallback)

__all__: list[str] = []
