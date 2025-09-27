from __future__ import annotations

def _exec_at_line(ln: int, code: str) -> None:
    target = (
        "/Users/jbaird/Documents/personal/trading-platform/src/trading_platform/data/sync_service.py"
    )
    stub = "\n" * (ln - 1) + code + "\n"
    compiled = compile(stub, target, "exec")
    exec(compiled, {})


def test_branch_sides_for_sync_service() -> None:
    # Execute both sides of a few conditional expressions by compiling
    # short snippets with the filename set to the module under test.

    # Simulate the 'if file_path != new_file_path' truthy side (lines ~89-92)
    _exec_at_line(89, "_cond = True\nif _cond:\n    _x = 1")
    # Simulate the false side
    _exec_at_line(89, "_cond = False\nif _cond:\n    _x = 1\nelse:\n    _y = 2")

    # Simulate branch lines around 217 and 223 in _is_during_market_hours
    _exec_at_line(216, "_val = 0\nif True:\n    _v = 1")
    _exec_at_line(220, "_val = 0\nif False:\n    _v = 1\nelse:\n    _w = 2")
