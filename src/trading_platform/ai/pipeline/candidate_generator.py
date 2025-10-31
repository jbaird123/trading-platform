"""Generate RMM candidate configurations from diagnostic summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import yaml


def _is_supported_feature(feature_name: str) -> bool:
    """Return True if feature can be referenced safely in RMM config."""

    allowed_prefixes = (
        "context_at_entry_global_",
        "context_at_entry_features_global_",
    )
    return any(feature_name.startswith(prefix) for prefix in allowed_prefixes)


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
    conditions: list[dict] = []
    for item in bounds:
        if not _is_supported_feature(item["feature"]):
            continue
        feature_ref = {"ref": item["feature"]}
        lower_bound = float(item["lower"])
        upper_bound = float(item["upper"])
        conditions.append(
            {
                "condition": "is_above",
                "left": feature_ref,
                "right": lower_bound,
            }
        )
        conditions.append(
            {
                "condition": "is_below",
                "left": feature_ref,
                "right": upper_bound,
            }
        )

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
        filtered_bounds = [
            item for item in bounds if _is_supported_feature(item.get("feature", ""))
        ]
        if not filtered_bounds:
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
            yaml_data = _candidate_yaml(context_key, filtered_bounds)
            if not yaml_data["regimes"][0]["conditions"]["all_of"]:
                continue
            candidate_path = context_dir / f"{candidate_id}.yaml"
            candidate_path.write_text(yaml.safe_dump(yaml_data, sort_keys=False))
            metadata["candidates"].append(
                {
                    "id": candidate_id,
                    "feature_bounds": filtered_bounds,
                    "candidate_path": str(candidate_path),
                }
            )

        metadata_path = context_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))
