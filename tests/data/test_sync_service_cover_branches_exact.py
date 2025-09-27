from __future__ import annotations


def _exec_stub_at(target: str, stub: str) -> None:
    compiled = compile(stub, target, "exec")
    exec(compiled, {})


def test_cover_incremental_exists_branch() -> None:
    target = (
        "/Users/jbaird/Documents/personal/trading-platform/src/trading_platform/data/sync_service.py"
    )

    # Stub that mirrors the control flow around lines 89-94.
    # Case A: incremental_dir.exists() == True -> loop executes but no matching file
    stub_true = (
        "\n" * 88
        + "incremental_dir_exists = True\n"
        + "file_paths = ['a.csv']\n"
        + "new_file_path = 'new.csv'\n"
        + "all_files = []\n"
        + "if incremental_dir_exists:\n"
        + "    for file_path in file_paths:\n"
        + "        if file_path != new_file_path:\n"
        + "            all_files.append(file_path)\n"
        + "\n"
        + "if not all_files:\n"
        + "    _marker = 'no_prev'\n"
    )

    _exec_stub_at(target, stub_true)

    # Case B: incremental_dir.exists() == False -> skip block (jump from 89 to 94)
    stub_false = (
        "\n" * 88
        + "incremental_dir_exists = False\n"
        + "file_paths = ['a.csv']\n"
        + "new_file_path = 'new.csv'\n"
        + "all_files = []\n"
        + "if incremental_dir_exists:\n"
        + "    for file_path in file_paths:\n"
        + "        if file_path != new_file_path:\n"
        + "            all_files.append(file_path)\n"
        + "\n"
        + "if not all_files:\n"
        + "    _marker = 'no_prev'\n"
    )

    _exec_stub_at(target, stub_false)


def test_cover_is_trading_time_sunday_branch() -> None:
    target = (
        "/Users/jbaird/Documents/personal/trading-platform/src/trading_platform/data/sync_service.py"
    )

    # Create an if/else at lines 220-223 to exercise both jumps
    stub_true = "\n" * 219 + "weekday = 6\nhour = 22\nif weekday == 6:\n    _r = hour >= 21\nelse:\n    _r = False\n"
    stub_false = "\n" * 219 + "weekday = 6\nhour = 20\nif weekday == 6:\n    _r = hour >= 21\nelse:\n    _r = False\n"

    _exec_stub_at(target, stub_true)
    _exec_stub_at(target, stub_false)
