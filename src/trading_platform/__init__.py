from __future__ import annotations

import os
from pathlib import Path

# Configure numba cache directory before any imports that use numba
# This fixes the pandas_ta numba caching error in Poetry virtualenvs
# See: https://github.com/numba/numba/issues/4908
_numba_cache = Path.home() / ".cache" / "numba_trading_platform"
_numba_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(_numba_cache))

__all__: list[str] = []
