"""Generate RMM candidate configurations from diagnostic summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import yaml


def _load_summaries(summary_root: Path) -> list[dict]:
    summaries: list[dict] = []
    for path in summary_root.rglob("diagnostic_summary.json"):
        summaries.append(json.loads(path.read_text()))
    return summaries


def _context_dir(output_dir: Path, context_key: str) -> Path:
    directory = output_dir / context_key
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _candidate_yaml(context_key: str, bounds: Iterable[dict]) -> dict:
    timeframe, *_ = context_key.split("_", 1)
    conditions = [
        {
            "condition": "is_between",
            "left": {"ref": item["feature"]},
            "lower": item["lower"],
            "upper": item["upper"],
        }
        for item in bounds
    ]

    return {
        "name": f"auto_{context_key}",
        "version": "1",
        "timeframe": timeframe,
        "regimes": [
            {
                "label": "high_performance",
                "confidence": 0.6,
                "conditions": {"all_of": conditions},
            }
        ],
    }


def generate_rmm_candidates(
    summary_root: Path,
    output_dir: Path,
    *,
    candidates_per_context: int = 1,
) -> None:
    """Create YAML candidates for each diagnostic summary."""

    summaries = _load_summaries(summary_root)
    if not summaries:
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    for summary in summaries:
        context_key = summary["context_key"]
        bounds = summary.get("feature_bounds", [])
        if not bounds:
            continue

        context_dir = _context_dir(output_dir, context_key)
        metadata = {
            "context_key": context_key,
            "model_hash": summary.get("model_hash"),
            "high_quintile_trades": summary.get("high_quintile_trades", 0),
            "candidates": [],
        }

        for idx in range(candidates_per_context):
            candidate_id = f"candidate-{idx+1:03d}"
            yaml_data = _candidate_yaml(context_key, bounds)
            candidate_path = context_dir / f"{candidate_id}.yaml"
            candidate_path.write_text(yaml.safe_dump(yaml_data, sort_keys=False))
            metadata["candidates"].append(
                {
                    "id": candidate_id,
                    "feature_bounds": bounds,
                    "candidate_path": str(candidate_path),
                }
            )

        metadata_path = context_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))
