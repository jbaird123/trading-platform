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
        "top_features": [
            "context_at_entry_global_features_1h_rsi_14",
            "context_at_entry_global_features_1h_atr_14",
        ],
        "high_quintile_trades": 15,
        "feature_bounds": [
            {
                "feature": "context_at_entry_global_features_1h_rsi_14",
                "lower": 41.4,
                "upper": 58.6,
            },
            {
                "feature": "context_at_entry_global_features_1h_atr_14",
                "lower": 0.001,
                "upper": 0.002,
            },
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
            "left": {"ref": "1h_rsi_14"},
            "right": 41.4,
        },
        {
            "condition": "is_below",
            "left": {"ref": "1h_rsi_14"},
            "right": 58.6,
        },
        {
            "condition": "is_above",
            "left": {"ref": "1h_atr_14"},
            "right": 0.001,
        },
        {
            "condition": "is_below",
            "left": {"ref": "1h_atr_14"},
            "right": 0.002,
        },
    ]

    metadata_path = context_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    assert metadata["context_key"] == "1H_trend_following"
    assert (
        metadata["candidates"][0]["feature_bounds"][0]["feature"]
        == "context_at_entry_global_features_1h_rsi_14"
    )


def test_generate_rmm_candidates_filters_unsupported_features(tmp_path: Path) -> None:
    summary_root = tmp_path / "summaries"
    summary_root.mkdir()

    context_dir = summary_root / "1H_trend_following"
    context_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "context_key": "1H_trend_following",
        "model_hash": "hash123",
        "feature_bounds": [
            {
                "feature": "context_at_entry_strategy_features_ema_fast",
                "lower": 1.0,
                "upper": 2.0,
            },
            {
                "feature": "context_at_entry_global_features_1h_rsi_14",
                "lower": 40.0,
                "upper": 60.0,
            },
        ],
        "summary_path": str(context_dir / "diagnostic_summary.json"),
    }
    (context_dir / "diagnostic_summary.json").write_text(json.dumps(summary, indent=2))

    output_dir = tmp_path / "candidates"
    generate_rmm_candidates(summary_root, output_dir, candidates_per_context=1)

    candidate_path = output_dir / "1H_trend_following" / "candidate-001.yaml"
    candidate = yaml.safe_load(candidate_path.read_text())
    feature_refs = [
        cond["left"]["ref"]
        for cond in candidate["regimes"][0]["conditions"]["all_of"]
        if "left" in cond
    ]
    assert "context_at_entry_strategy_features_ema_fast" not in feature_refs
    assert "1h_rsi_14" in feature_refs
