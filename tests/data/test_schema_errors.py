from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from trading_platform.data.schema import load_and_normalize_data


def test_load_and_normalize_handles_read_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange: create a dummy file path and force read_csv to raise
    f = tmp_path / "bad.csv"
    f.write_text("garbage")

    def _boom(path):  # type: ignore[no-redef]
        raise RuntimeError("boom")

    monkeypatch.setattr(pd, "read_csv", _boom)

    # Act
    df, flags = load_and_normalize_data(f)

    # Assert: empty df and an unexpected_error flag present
    assert df.empty
    assert any(flag.startswith("unexpected_error:") for flag in flags)
