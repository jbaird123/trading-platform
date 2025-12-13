import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def _write_summary(summary_root: Path, context_key: str) -> None:
    summary_dir = summary_root / context_key
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "diagnostic_summary.json"
    summary = {
        "context_key": context_key,
        "model_hash": "hash123",
        "top_features": [
            "context_at_entry_global_features_1h_rsi_14",
            "context_at_entry_global_features_1h_atr_14",
        ],
        "high_quintile_trades": 10,
        "feature_bounds": [
            {
                "feature": "context_at_entry_global_features_1h_rsi_14",
                "lower": 40.0,
                "upper": 60.0,
            },
            {
                "feature": "context_at_entry_global_features_1h_atr_14",
                "lower": 0.001,
                "upper": 0.002,
            },
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

    data_root = tmp_path / "data_root"
    full_dir = data_root / "full" / "eurusd"
    full_dir.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2024-01-01", periods=600, freq="h", tz="UTC")
    prices = 1.05 + np.linspace(0.0, 0.02, len(idx))
    df = pd.DataFrame(
        {
            "timestamp": idx,
            "open": prices,
            "high": prices + 0.0002,
            "low": prices - 0.0002,
            "close": prices,
            "volume": np.full(len(idx), 1000),
        }
    )
    csv_path = full_dir / "EURUSD.csv"
    df.to_csv(csv_path, index=False)

    strategy_file = tmp_path / "strategy.yaml"
    strategy_definition = {
        "strategy_name": "TestSMACrossover",
        "features": [
            {
                "name": "sma_fast",
                "type": "SMA",
                "params": {"length": 5},
                "source": "close",
            },
            {
                "name": "sma_slow",
                "type": "SMA",
                "params": {"length": 12},
                "source": "close",
            },
        ],
        "long_entry_rules": [
            {
                "all_of": [
                    {
                        "condition": "is_above",
                        "left": {"ref": "sma_fast"},
                        "right": {"ref": "sma_slow"},
                    }
                ]
            }
        ],
        "long_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_below",
                        "left": {"ref": "sma_fast"},
                        "right": {"ref": "sma_slow"},
                    }
                ]
            }
        ],
        "short_entry_rules": [
            {
                "all_of": [
                    {
                        "condition": "is_below",
                        "left": {"ref": "sma_fast"},
                        "right": {"ref": "sma_slow"},
                    }
                ]
            }
        ],
        "short_exit_rules": [
            {
                "any_of": [
                    {
                        "condition": "is_above",
                        "left": {"ref": "sma_fast"},
                        "right": {"ref": "sma_slow"},
                    }
                ]
            }
        ],
    }
    strategy_file.write_text(yaml.safe_dump(strategy_definition, sort_keys=False))

    global_features = tmp_path / "global_features.yaml"
    global_features.write_text("features: []\n")

    run_config = tmp_path / "run_config.yaml"
    run_config_data = {
        "user_id": "test_user",
        "initial_cash": 10000,
        "position_size": 1,
        "data_request": {
            "symbol": "EURUSD",
            "timeframe": "1H",
            "start": "2024-01-01T15:00:00",  # After SMA warmup period (12 bars)
        },
        "strategy_path": str(strategy_file),
        "rem_config": {},
        "global_features_config_path": str(global_features),
    }
    run_config.write_text(yaml.safe_dump(run_config_data, sort_keys=False))

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
    output_dir = tmp_path / "reports"

    validate_result = _run_command(
        [
            "ai-validate-rmm-candidates",
            "--candidates-dir",
            str(candidate_root),
            "--strategy-config",
            str(run_config),
            "--enriched-path",
            str(enriched),
            "--output-dir",
            str(output_dir),
            "--data-root",
            str(data_root),
        ]
    )
    assert validate_result.returncode == 0
    summary_csv = output_dir / "validation_summary.csv"
    assert summary_csv.exists(), validate_result.stderr
