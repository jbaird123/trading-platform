"""Generate RMM candidate configurations from diagnostic summaries."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml
from trading_platform.core.config import GlobalFeatureSetConfig
from trading_platform.core.paths import PROJECT_ROOT


def _to_plain_feature_spec(feature: dict) -> dict:
    spec = dict(feature)
    source = spec.get("source")
    if source is not None and hasattr(source, "value"):
        spec["source"] = source.value
    return spec


@lru_cache(maxsize=1)
def _global_feature_lookup() -> dict[str, dict]:
    """Map context feature names to global feature specs."""

    global_path = PROJECT_ROOT / "config" / "features" / "global.yaml"
    if not global_path.exists():
        return {}

    raw_cfg = yaml.safe_load(global_path.read_text()) or {}
    model = GlobalFeatureSetConfig.model_validate(raw_cfg, context={"is_global": True})

    lookup: dict[str, dict] = {}
    for feature in model.features:
        spec = _to_plain_feature_spec(feature.model_dump())
        context_key = f"context_at_entry_global_features_{spec['name']}"
        lookup[context_key] = spec
    return lookup


def _normalize_feature_name(feature_name: str) -> tuple[str | None, dict | None]:
    """Return (normalized_name, spec) for a diagnostic feature."""

    lookup = _global_feature_lookup()
    spec = lookup.get(feature_name)
    if spec is None:
        return None, None
    return spec["name"], spec


def _is_supported_feature(feature_name: str) -> bool:
    name, spec = _normalize_feature_name(feature_name)
    return name is not None and spec is not None


def _load_summaries(summary_root: Path) -> list[dict]:
    summaries: list[dict] = []
    for path in summary_root.rglob("diagnostic_summary.json"):
        summaries.append(json.loads(path.read_text()))
    return summaries


def _context_dir(output_dir: Path, context_key: str) -> Path:
    directory = output_dir / context_key
    directory.mkdir(parents=True, exist_ok=True)
    return directory


MAX_FEATURE_PREDICATES = 4


def _candidate_yaml(context_key: str, bounds: Iterable[dict]) -> dict:
    timeframe, *_ = context_key.split("_", 1)
    conditions: list[dict] = []
    feature_specs: dict[str, dict] = {}
    for item in bounds:
        normalized_name, spec = _normalize_feature_name(item["feature"])
        if not normalized_name or spec is None:
            continue

        if normalized_name in feature_specs:
            continue
        if len(feature_specs) >= MAX_FEATURE_PREDICATES:
            continue

        feature_specs.setdefault(normalized_name, spec)
        feature_ref = {"ref": normalized_name}
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
        "features": list(feature_specs.values()),
        "policy": {
            "min_confidence": 0.6,
            "allow_labels": ["high_performance"],
        },
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
