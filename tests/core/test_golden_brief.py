# ruff: noqa: E501
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from trading_platform.backtester.core import _run_backtest_simulation
from trading_platform.core.config import RunConfig
from trading_platform.core.run import finalize_run
from trading_platform.data.schema import load_and_normalize_data
from trading_platform.portfolio.trade import Trade
from trading_platform.reporting.brief import compute_data_quality
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import compile_strategy

# Fields that are dynamic and should be ignored during comparison
KEYS_TO_IGNORE = {
    "timestamp",
    "run_id",
    "git_commit",
    "python_version",
    "platform",
    "timezone",
    "app_version",
    "config_snapshot_hash",  # This will change if we so much as add a comment
    "instrument_defs_hash",
}


def assert_briefs_equal(actual: dict[str, Any], golden: dict[str, Any], path: str = ""):
    """
    Recursively asserts that two brief dictionaries are equal, ignoring
    dynamic fields and using pytest.approx for floats.
    """
    assert isinstance(actual, dict)
    assert isinstance(golden, dict)

    actual_keys = set(actual.keys())
    golden_keys = set(golden.keys())

    # Check for missing or extra keys at the current level
    missing_keys = golden_keys - actual_keys
    extra_keys = actual_keys - golden_keys
    assert not missing_keys, f"Missing keys in actual brief at '{path}': {missing_keys}"
    assert not extra_keys, f"Extra keys in actual brief at '{path}': {extra_keys}"

    for key in sorted(golden_keys):
        new_path = f"{path}.{key}" if path else key
        if key in KEYS_TO_IGNORE:
            continue

        actual_val = actual[key]
        golden_val = golden[key]

        if isinstance(golden_val, dict):
            assert_briefs_equal(actual_val, golden_val, new_path)
        elif isinstance(golden_val, list):
            assert isinstance(actual_val, list)
            assert len(actual_val) == len(
                golden_val
            ), f"List length differs at '{new_path}'"
            for i, item in enumerate(golden_val):
                if isinstance(item, dict):
                    assert_briefs_equal(actual_val[i], item, f"{new_path}[{i}]")
                elif isinstance(item, float):
                    assert actual_val[i] == pytest.approx(
                        item
                    ), f"Float differs at '{new_path}[{i}]'"
                else:
                    assert actual_val[i] == item, f"Value differs at '{new_path}[{i}]'"
        elif isinstance(golden_val, float):
            assert actual_val == pytest.approx(
                golden_val
            ), f"Float differs at '{new_path}'"
        else:
            assert actual_val == golden_val, f"Value differs at '{new_path}'"


def test_brief_matches_golden_master(tmp_path: Path, request):
    """
    Runs a backtest with a fixed configuration and compares the output brief
    against a 'golden master' version to detect any regressions.
    """
    # 1. Define paths
    fixture_dir = Path("tests/fixtures/golden_run")
    config_path = fixture_dir / "run_config.yaml"
    golden_brief_path = fixture_dir / "golden_brief.json"
    run_output_path = tmp_path

    # 2. Load all configs
    cfg_raw = yaml.safe_load(config_path.read_text())
    strat_cfg = yaml.safe_load((fixture_dir / cfg_raw["strategy"]).read_text())
    rem_cfg = yaml.safe_load((fixture_dir / cfg_raw["rem"]).read_text())
    data_path = fixture_dir / cfg_raw["data"]["source"]

    # 3. Prepare backtest inputs
    df, dq_flags = load_and_normalize_data(data_path)
    data_quality_report = compute_data_quality(df)
    data_quality_report["loader_flags"] = dq_flags

    strat_cfg["parameters"] = strat_cfg.get("parameters", {})
    strategy = compile_strategy(strat_cfg)
    signals = strategy.generate_signals(df)
    rem = RiskExitManager(config=rem_cfg)

    initial_cash = 100000.0
    cfg_for_validation = cfg_raw.copy()

    # Remove CLI-only/legacy fields
    cfg_for_validation.pop("rem", None)
    cfg_for_validation.pop("regime_market_manager", None)
    cfg_for_validation.pop("data", None)
    cfg_for_validation.pop("costs", None)

    cfg_for_validation["strategy"] = strat_cfg
    cfg_for_validation["rem_config"] = rem_cfg
    cfg_for_validation["run_id"] = "golden_run_test"  # Use a different run_id
    cfg_for_validation["initial_cash"] = initial_cash
    # Keep the original instrument from config (don't override symbol)
    # The symbol from the fixture config file will be used
    run_config = RunConfig.model_validate(cfg_for_validation)

    # 4. Run the backtest
    res = _run_backtest_simulation(
        market_data=df,
        signals=signals,
        strategy=strategy,
        config=run_config,
        rem=rem,
        return_exposure=True,
        return_skips=True,
    )
    # Unpack results with proper type casting to satisfy mypy
    skips: list[dict[str, Any]] = []
    if isinstance(res, tuple):
        if len(res) == 3:
            trades = cast(list[Trade], res[0])
            exposure = cast(list[tuple[datetime, float]], res[1])
            skips = cast(list[dict[str, Any]], res[2])
        else:
            trades = cast(list[Trade], res[0])
            exposure = cast(list[tuple[datetime, float]], res[1])
    else:
        trades = cast(list[Trade], res)
        exposure = []

    # 5. Generate the brief in a temporary location
    from trading_platform.cli import _get_git_commit

    meta = {
        "strategy_name": strategy.name,
        "run_id": run_config.run_id,
        "git_commit": _get_git_commit(),
        "run_seed": run_config.run_seed,
    }
    params_snapshot = strat_cfg.get("parameters", {})

    recommendations = [
        {
            "id": "consider_adx_filter_for_entries",
            "title": "Consider ADX Filter for Entries",
            "description": "The strategy has a high trade count and low win rate. Consider adding an ADX filter to entry rules to improve signal quality.",
            "rule": "Consider ADX Filter for Entries",
            "severity": "info",
            "suggested_action": "Add ADX filter to entry rules.",
        }
    ]
    finalize_run(
        run_path=run_output_path,
        meta=meta,
        params=params_snapshot,
        trades=trades,
        initial_cash=initial_cash,
        config=run_config,
        exposure_curve=exposure,
        data_quality=data_quality_report,
        skipped_trades=skips,
        recommendations=recommendations,
    )

    # 6. Load both briefs and compare them
    generated_brief_path = run_output_path / "brief.json"
    assert generated_brief_path.exists()

    actual_brief = json.loads(generated_brief_path.read_text())

    try:
        update_golden = request.config.getoption("--update-golden")
    except ValueError:
        update_golden = False

    if update_golden:
        golden_brief_path.write_text(json.dumps(actual_brief, indent=2))
        pytest.skip("Golden master file updated.")

    golden_brief = json.loads(golden_brief_path.read_text())

    # Validate skipped_trades structure
    assert isinstance(actual_brief["skipped_trades"], list)
    # Note: Test doesn't run with RMM, so we may have 0 skips
    if len(actual_brief["skipped_trades"]) >= 1:
        first_skip = actual_brief["skipped_trades"][0]
        required_keys = {
            "symbol",
            "side",
            "size",
            "entry_time",
            "skip_reason",
            "counterfactual_pnl",
            "counterfactual_mfe_currency",
            "counterfactual_mae_currency",
        }

        for key in required_keys:
            assert key in first_skip, f"Missing required key '{key}' in skipped trade"

    assert_briefs_equal(actual_brief, golden_brief)
