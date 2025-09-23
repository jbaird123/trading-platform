from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src" / "trading_platform"


ALLOWED_CROSS_TOP_IMPORTS = {"core", "portfolio"}

# Files that serve as integrators and may import across modules
ALLOWLIST_PATHS = {
    SRC_ROOT / "cli.py",
    SRC_ROOT / "core" / "run.py",
    SRC_ROOT / "core" / "demo.py",
    SRC_ROOT / "core" / "sweeps.py",  # Parameter sweeps coordinate across modules
    SRC_ROOT / "backtester" / "core.py",  # Backtester integrates components
    SRC_ROOT / "regime_market_manager" / "engine.py",  # RMM coordinates modules
}

IMPORT_RE = re.compile(
    r"^from\s+trading_platform\.(?P<top>[a-z_]+)\.(?P<rest>[a-z0-9_\.]+)\s+import\s+",
)


def top_of_file(path: Path) -> str | None:
    try:
        rel = path.relative_to(SRC_ROOT)
    except Exception:
        return None
    parts = rel.parts
    if len(parts) >= 2:
        return parts[0]
    return None


def scan_file(path: Path) -> list[str]:
    if path in ALLOWLIST_PATHS:
        return []
    cur_top = top_of_file(path)
    if cur_top is None:
        return []
    violations: list[str] = []
    try:
        txt = path.read_text()
    except Exception:
        return []
    for i, line in enumerate(txt.splitlines(), start=1):
        m = IMPORT_RE.match(line.strip())
        if not m:
            continue
        imp_top = m.group("top")
        if imp_top == cur_top:
            continue
        if imp_top in ALLOWED_CROSS_TOP_IMPORTS:
            continue
        violations.append(
            f"{path.relative_to(PROJECT_ROOT)}:{i}: cross-module deep import "
            f"to '{imp_top}'; import via public API (__init__.py) or add to "
            f"allowlist if intentional."
        )
    return violations


def main() -> int:
    if not SRC_ROOT.exists():
        return 0
    violations: list[str] = []
    for p in SRC_ROOT.rglob("*.py"):
        violations.extend(scan_file(p))
    if violations:
        print("Boundary check violations detected:")
        for v in violations:
            print(" - ", v)
        return 1
    print("Boundary check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
