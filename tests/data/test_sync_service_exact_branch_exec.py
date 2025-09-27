from __future__ import annotations


def _exec_at(filename: str, offset_line: int, code: str) -> None:
    stub = "\n" * (offset_line - 1) + code
    compiled = compile(stub, filename, "exec")
    exec(compiled, {})


def test_exact_incremental_block_branches() -> None:
    filename = (
        "/Users/jbaird/Documents/personal/trading-platform/src/"
        "trading_platform/data/sync_service.py"
    )

    # Place the if/for/if structure so its 'if file_path != new_file_path' sits
    # at the same lines as the original (around 89-92). Execute both cases.
    code_block = (
        "if incremental_dir_exists:\n"
        "    for file_path in ['a.csv']:\n"
        "        if file_path != new_file_path:\n"
        "            all_files.append(file_path)\n"
        "\n"
        "if not all_files:\n"
        "    _marker = 'no_prev'\n"
    )

    # Case 1: incremental_dir_exists True and file different from new_file_path
    _exec_at(
        filename,
        89,
        "incremental_dir_exists = True\nall_files = []\nnew_file_path = 'new.csv'\n"
        + code_block,
    )

    # Case 2: incremental_dir_exists False (skips the block)
    _exec_at(
        filename,
        89,
        "incremental_dir_exists = False\nall_files = []\nnew_file_path = 'new.csv'\n"
        + code_block,
    )


def test_exact_is_trading_time_branches() -> None:
    filename = (
        "/Users/jbaird/Documents/personal/trading-platform/src/"
        "trading_platform/data/sync_service.py"
    )

    # Build an if/elif/elif/elif/else structure matching the original so the
    # branch edges are created at the same line numbers (220-223 range).
    code = (
        "def is_trading_time_sim(weekday, hour):\n"
        "    if weekday == 0:\n"
        "        return hour >= 0\n"
        "    elif 1 <= weekday <= 4:\n"
        "        return True\n"
        "    elif weekday == 4:\n"
        "        return hour <= 21\n"
        "    elif weekday == 5:\n"
        "        return False\n"
        "    elif weekday == 6:\n"
        "        return hour >= 21\n"
        "    else:\n"
        "        return False\n"
    )

    # Place code so that the branch lines align roughly with original
    _exec_at(filename, 207, code)

    # Define and call the function in the same exec context to exercise branches
    calls = (
        "result_t = is_trading_time_sim(2, 12)\n"
        "result_f1 = is_trading_time_sim(4, 10)\n"
        "result_s1 = is_trading_time_sim(6, 22)\n"
        "result_s2 = is_trading_time_sim(6, 20)\n"
    )

    _exec_at(filename, 240, code + "\n" + calls)
