#!/usr/bin/env python3
"""Auto-update test registry from runs directory.

Usage:
  python tools/update_test_registry.py --strategy ema_crossover
  python tools/update_test_registry.py --strategy ema_crossover \
      --run runs/researcher/run_20251001_013755_utc
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Ensure the src directory is in the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from trading_platform.core import paths


def hash_config(config: dict) -> str:
    """Create deterministic hash of config for deduplication."""
    # Extract only relevant parts for comparison
    relevant = {
        "strategy_params": config.get("strategy_params", {}),
        "strategy_overrides": config.get("strategy_overrides", {}),
        "rem_path": config.get("rem_path"),
        "rmm_path": config.get("rmm_path"),
        "position_size": config.get("position_size"),
        "data_request": config.get("data_request"),
    }

    # Sort keys for deterministic hash
    config_str = json.dumps(relevant, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()[:16]


def extract_test_metadata(run_path: Path) -> dict | None:
    """Parse brief.json and config.json to extract test metadata."""
    brief_path = run_path / "brief.json"
    config_path = run_path / "config.json"

    if not brief_path.exists() or not config_path.exists():
        print(f"⚠️  Skipping {run_path.name} - missing brief or config")
        return None

    try:
        brief = json.load(open(brief_path))
        config = json.load(open(config_path))
    except Exception as e:
        print(f"⚠️  Error reading {run_path.name}: {e}")
        return None

    # Extract key metadata
    perf = brief.get("overall_performance", {})
    exit_eff = brief.get("exit_efficiency", {}).get("optimal_hold_analysis", {})

    # Extract strategy params
    strategy_params = config.get("strategy_params", {})
    overrides = config.get("strategy_overrides", {})

    # Merge overrides into params
    if "features" in overrides:
        for feature, params in overrides["features"].items():
            if feature == "ema_fast" and "length" in params:
                strategy_params["ema_fast"] = params["length"]
            elif feature == "ema_slow" and "length" in params:
                strategy_params["ema_slow"] = params["length"]

    # Build config snapshot
    config_snapshot = {
        "ema_fast": strategy_params.get(
            "ema_fast_length", strategy_params.get("ema_fast")
        ),
        "ema_slow": strategy_params.get(
            "ema_slow_length", strategy_params.get("ema_slow")
        ),
        "position_size": config.get("position_size"),
    }

    # Extract REM config (parse YAML to get trailing stop)
    rem_path = config.get("rem_path")
    if rem_path:
        try:
            rem_full_path = Path(rem_path)
            if not rem_full_path.is_absolute():
                rem_full_path = Path.cwd() / rem_path

            if rem_full_path.exists():
                rem_config = yaml.safe_load(open(rem_full_path))
                if "trailing_stop" in rem_config:
                    config_snapshot["trailing_stop"] = rem_config["trailing_stop"].get(
                        "price_offset"
                    )
                if "stop_loss" in rem_config:
                    config_snapshot["stop_loss"] = rem_config["stop_loss"].get(
                        "price_offset"
                    )
                if "take_profit" in rem_config:
                    config_snapshot["take_profit"] = rem_config["take_profit"].get(
                        "price_offset"
                    )
        except Exception as e:
            print(f"⚠️  Could not parse REM config: {e}")

    # RMM path
    config_snapshot["rmm"] = config.get("rmm_path")

    # Extract data period
    data_req = config.get("data_request", {})

    return {
        "test_id": run_path.name,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "description": f"Auto-imported from {run_path.name}",
        "run_path": str(run_path.relative_to(Path.cwd())),
        "config_hash": hash_config(config),
        "data_period": {
            "start": data_req.get("start"),
            "end": data_req.get("end"),
        },
        "config_snapshot": config_snapshot,
        "results": {
            "trades": perf.get("n_trades"),
            "pnl": perf.get("total_pnl"),
            "win_rate": perf.get("win_rate"),
            "avg_per_trade": None,  # Calculate if needed
            "exit_efficiency_20bar": exit_eff.get("if_held_20_bars"),
        },
        "insights": [],
        "status": "completed",
    }


def update_registry(
    strategy_name: str,
    registry_path: Path | None = None,
    run_path: Path | None = None,
):
    """Update test registry with new runs."""
    if registry_path is None:
        registry_path = Path(f"configs/strategies/{strategy_name}/test_registry.yaml")

    # Load existing registry
    if registry_path.exists():
        registry = yaml.safe_load(open(registry_path))
    else:
        print(f"⚠️  Registry not found: {registry_path}")
        print("Creating new registry...")
        registry = {
            "strategy": strategy_name,
            "instrument": "EUR_USD",
            "timeframe": "1H",
            "tests": [],
            "last_updated": None,
            "total_tests": 0,
            "auto_generated": True,
        }

    existing_run_ids = {test["test_id"] for test in registry["tests"]}
    existing_hashes = {test.get("config_hash") for test in registry["tests"]}

    # Find runs to process
    if run_path:
        # Single run mode
        runs_to_process = [run_path] if run_path.exists() else []
    else:
        # Scan all runs
        runs_dir = paths.RUNS_DIR / "researcher"
        if not runs_dir.exists():
            print(f"⚠️  Runs directory not found: {runs_dir}")
            return

        runs_to_process = sorted(runs_dir.glob("run_*"), reverse=True)

    new_tests = 0
    duplicate_configs = 0

    for run in runs_to_process:
        if run.name in existing_run_ids:
            continue  # Already in registry

        metadata = extract_test_metadata(run)
        if not metadata:
            continue

        # Check for duplicate configs
        if metadata["config_hash"] in existing_hashes:
            print(
                f"⚠️  Duplicate config: {run.name} "
                f"(hash: {metadata['config_hash'][:8]}...)"
            )
            duplicate_configs += 1
            # Still add it but mark as duplicate
            metadata["tags"] = metadata.get("tags", []) + ["duplicate_config"]

        # Add to registry (insert at beginning for newest-first)
        registry["tests"].insert(0, metadata)
        existing_run_ids.add(metadata["test_id"])
        existing_hashes.add(metadata["config_hash"])
        new_tests += 1
        print(f"✅ Added: {run.name}")

    # Update metadata
    registry["last_updated"] = datetime.now().isoformat()
    registry["total_tests"] = len(registry["tests"])
    registry["auto_generated"] = True

    # Save registry
    with open(registry_path, "w") as f:
        yaml.dump(registry, f, default_flow_style=False, sort_keys=False, width=120)

    print(f"\n📊 Registry updated: {registry_path}")
    print(f"   Total tests: {registry['total_tests']}")
    print(f"   New tests added: {new_tests}")
    if duplicate_configs > 0:
        print(f"   ⚠️  Duplicate configs found: {duplicate_configs}")


def check_if_tested(
    strategy_name: str, config: dict, registry_path: Path | None = None
):
    """Check if a config has already been tested."""
    if registry_path is None:
        registry_path = Path(f"configs/strategies/{strategy_name}/test_registry.yaml")

    if not registry_path.exists():
        print(f"⚠️  No registry found: {registry_path}")
        return None

    registry = yaml.safe_load(open(registry_path))
    config_hash = hash_config(config)

    # Find matching tests
    matches = [
        test for test in registry["tests"] if test.get("config_hash") == config_hash
    ]

    if matches:
        print(f"\n⚠️  This config has already been tested {len(matches)} time(s):\n")
        for match in matches:
            print(f"   Test ID: {match['test_id']}")
            print(f"   Date: {match['date']}")
            results = match["results"]
            print(
                f"   Results: {results['pnl']:.2f} PnL, "
                f"{results['trades']} trades, {results['win_rate']:.1%} WR"
            )
            print(f"   Run: {match['run_path']}")
            print()
        return matches

    print("✅ This is a new config - not previously tested")
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update test registry from runs")
    parser.add_argument(
        "--strategy", required=True, help="Strategy name (e.g., ema_crossover)"
    )
    parser.add_argument("--run", help="Specific run path to add (optional)")
    parser.add_argument("--check-config", help="Check if config file has been tested")

    args = parser.parse_args()

    if args.check_config:
        # Check if config has been tested
        config_path = Path(args.check_config)
        if not config_path.exists():
            print(f"⚠️  Config not found: {config_path}")
            exit(1)

        if config_path.suffix == ".yaml":
            config = yaml.safe_load(open(config_path))
        else:
            config = json.load(open(config_path))

        check_if_tested(args.strategy, config)
    else:
        # Update registry
        run_path = Path(args.run) if args.run else None
        update_registry(args.strategy, run_path=run_path)
