import json
from pathlib import Path

import yaml
from trading_platform.ai.pipeline.candidate_generator import generate_rmm_candidates


def _write_summary(root: Path, context: str) -> Path:
    context_dir = root / context
    context_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "context_key": context,
        "model_hash": "hash123",
        "top_features": ["f1", "f2"],
        "high_quintile_trades": 15,
        "feature_bounds": [
            {"feature": "f1", "lower": 1.1, "upper": 1.9},
            {"feature": "f2", "lower": 0.2, "upper": 0.6},
        ],
        "summary_path": str(context_dir / "diagnostic_summary.json"),
    }
    path = context_dir / "diagnostic_summary.json"
    path.write_text(json.dumps(summary, indent=2))
    return path


def test_generate_rmm_candidates_creates_yaml(tmp_path: Path) -> None:
    summary_root = tmp_path / "summaries"
    summary_root.mkdir()
    _write_summary(summary_root, "1H_trend_following")

    output_dir = tmp_path / "candidates"
    generate_rmm_candidates(summary_root, output_dir, candidates_per_context=1)

    context_dir = output_dir / "1H_trend_following"
    candidate_files = sorted(context_dir.glob("candidate-*.yaml"))
    assert len(candidate_files) == 1

    candidate = yaml.safe_load(candidate_files[0].read_text())
    assert candidate["timeframe"] == "1H"
    conditions = candidate["regimes"][0]["conditions"]["all_of"]
    assert conditions == [
        {
            "condition": "is_above",
            "left": {"ref": "f1"},
            "right": 1.1,
        },
        {
            "condition": "is_below",
            "left": {"ref": "f1"},
            "right": 1.9,
        },
        {
            "condition": "is_above",
            "left": {"ref": "f2"},
            "right": 0.2,
        },
        {
            "condition": "is_below",
            "left": {"ref": "f2"},
            "right": 0.6,
        },
    ]

    metadata_path = context_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    assert metadata["context_key"] == "1H_trend_following"
    assert metadata["candidates"][0]["feature_bounds"][0]["lower"] == 1.1
