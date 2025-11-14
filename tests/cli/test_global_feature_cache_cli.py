from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from trading_platform.cli import _precompute_global_features_logic


def _write_sample_csv(path: Path) -> None:
    idx = pd.date_range("2023-01-01", periods=360, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "open": 1.1,
            "high": 1.2,
            "low": 1.0,
            "close": 1.15,
            "volume": 50.0,
        }
    )
    df.to_csv(path, index=False)


def _write_global_yaml(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "features:",
                '  - name: "m5_cli_ema"',
                '    type: "EMA"',
                '    params: {"length": 4}',
                '    timeframe: "5min"',
            ]
        )
    )


def test_precompute_global_features_cli_builds_cache(tmp_path) -> None:
    data_root = tmp_path / "data_root"
    csv_dir = data_root / "full" / "eurusd"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "eurusd_1min.csv"
    _write_sample_csv(csv_path)
    global_yaml = tmp_path / "global.yaml"
    _write_global_yaml(global_yaml)

    cache_root = tmp_path / "cache"
    args = argparse.Namespace(
        symbol="EUR_USD",
        data_root=str(data_root),
        config=str(global_yaml),
        timeframes=["5min"],
        overwrite=True,
        include_bar_windows=False,
        cache_root=str(cache_root),
    )

    result = _precompute_global_features_logic(args)
    assert result == 0

    metadata_files = list(cache_root.rglob("metadata.json"))
    assert len(metadata_files) == 1
    metadata = json.loads(metadata_files[0].read_text())
    assert "5min" in metadata.get("timeframes", {})
