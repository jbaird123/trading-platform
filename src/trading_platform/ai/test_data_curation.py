"""Tests for ML data curation pipeline."""

import json
from pathlib import Path

import pandas as pd


def test_run_curation_pipeline(tmp_path: Path):
    """Test that run_curation_pipeline aggregates trades from multiple briefs."""
    from trading_platform.ai.data_curation import run_curation_pipeline

    # Create mock brief files
    run1_dir = tmp_path / "run1"
    run1_dir.mkdir()
    brief1 = {
        "trades": [
            {"entry_time": "2023-01-01T00:00:00", "pnl": 100.0},
            {"entry_time": "2023-01-01T01:00:00", "pnl": 50.0},
        ]
    }
    (run1_dir / "brief.json").write_text(json.dumps(brief1))

    run2_dir = tmp_path / "run2"
    run2_dir.mkdir()
    brief2 = {
        "trades": [
            {"entry_time": "2023-01-02T00:00:00", "pnl": -25.0},
        ]
    }
    (run2_dir / "brief.json").write_text(json.dumps(brief2))

    # Run curation pipeline
    output_file = tmp_path / "output.parquet"
    run_curation_pipeline(source_dir=tmp_path, output_file=output_file)

    # Assertions
    assert output_file.exists()

    # Read back and verify
    df = pd.read_parquet(output_file)
    assert len(df) == 3  # 2 trades from brief1 + 1 trade from brief2
    assert "pnl" in df.columns
    assert "entry_time" in df.columns
