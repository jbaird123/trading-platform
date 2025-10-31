import json
import subprocess
from pathlib import Path


def _write_summary(summary_root: Path, context_key: str) -> None:
    summary_dir = summary_root / context_key
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "diagnostic_summary.json"
    summary = {
        "context_key": context_key,
        "model_hash": "hash123",
        "top_features": ["f1", "f2"],
        "high_quintile_trades": 10,
        "feature_bounds": [
            {"feature": "f1", "lower": 1.0, "upper": 2.0},
            {"feature": "f2", "lower": 0.2, "upper": 0.6},
        ],
        "summary_path": str(summary_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2))


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["poetry", "run", "tp", *args],
        capture_output=True,
        text=True,
    )


def test_ai_generate_rmm_candidates_command(tmp_path: Path) -> None:
    enriched = tmp_path / "rich.parquet"
    enriched.write_text("placeholder")
    model_dir = tmp_path / "models"
    output_dir = tmp_path / "artifacts"
    summary_root = output_dir / "diagnostic_summaries"
    _write_summary(summary_root, "1H_trend_following")

    result = _run_command(
        [
            "ai-generate-rmm-candidates",
            "--enriched-path",
            str(enriched),
            "--model-dir",
            str(model_dir),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert result.returncode == 0

    candidate_dir = output_dir / "candidates" / "1H_trend_following"
    candidate_files = list(candidate_dir.glob("candidate-*.yaml"))
    assert candidate_files, result.stderr


def test_ai_validate_rmm_candidates_command(tmp_path: Path) -> None:
    enriched = tmp_path / "rich.parquet"
    enriched.write_text("placeholder")
    model_dir = tmp_path / "models"
    artifacts_dir = tmp_path / "artifacts"
    summaries_dir = artifacts_dir / "diagnostic_summaries"
    _write_summary(summaries_dir, "1H_trend_following")

    generate_result = _run_command(
        [
            "ai-generate-rmm-candidates",
            "--enriched-path",
            str(enriched),
            "--model-dir",
            str(model_dir),
            "--output-dir",
            str(artifacts_dir),
        ]
    )
    assert generate_result.returncode == 0

    candidate_root = artifacts_dir / "candidates"
    strategy_config = tmp_path / "strategy.yaml"
    strategy_config.write_text("{}\n")
    output_dir = tmp_path / "reports"

    validate_result = _run_command(
        [
            "ai-validate-rmm-candidates",
            "--candidates-dir",
            str(candidate_root),
            "--strategy-config",
            str(strategy_config),
            "--enriched-path",
            str(enriched),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert validate_result.returncode == 0
    summary_csv = output_dir / "validation_summary.csv"
    assert summary_csv.exists(), validate_result.stderr
