from __future__ import annotations

import json
from pathlib import Path


def test_example_configs_parse():
    for fname in [
        Path("docs/examples/backtest_config.json"),
        Path("docs/examples/live_config.json"),
    ]:
        assert fname.exists()
        data = json.loads(fname.read_text())
        assert isinstance(data, dict)
