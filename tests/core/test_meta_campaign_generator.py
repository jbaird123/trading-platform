from __future__ import annotations

from pathlib import Path

from trading_platform.core.meta_campaign_config import MetaCampaignConfig
from trading_platform.core.meta_campaign_generator import (
    calculate_cartesian_product,
    campaign_config_to_yaml_dict,
    generate_campaign_filename,
)


def test_calculate_cartesian_product_single_profile(tmp_path: Path) -> None:
    """Test cartesian product calculation with a single profile."""
    yaml_content = """
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EUR_USD
    - GBP_USD
  execution_timeframes:
    - 15min
    - 1H

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10, slow_length: 20 }
      - strategy_params: { fast_length: 20, slow_length: 50 }
"""
    yaml_file = tmp_path / "test_meta_campaign.yaml"
    yaml_file.write_text(yaml_content)

    config = MetaCampaignConfig.from_yaml(yaml_file)
    campaigns = calculate_cartesian_product(config)

    # Expected: 1 date_range × 2 instruments × 2 timeframes × 2 param_sets = 8
    assert len(campaigns) == 8


def test_calculate_cartesian_product_multiple_profiles(tmp_path: Path) -> None:
    """Test cartesian product with multiple strategy profiles."""
    yaml_content = """
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EUR_USD
  execution_timeframes:
    - 15min

strategy_profiles:
  - name: trend_with_risk
    strategy_path: config/strategy/test.yaml
    rem_path: config/rem/test.yaml
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10 }
        rem_params: { atr_length: 14 }

  - name: baseline_no_risk
    strategy_path: config/strategy/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 20 }
"""
    yaml_file = tmp_path / "test_meta_campaign.yaml"
    yaml_file.write_text(yaml_content)

    config = MetaCampaignConfig.from_yaml(yaml_file)
    campaigns = calculate_cartesian_product(config)

    # Expected: 1 date_range × 1 instrument × 1 timeframe × (1 + 1) profiles = 2
    assert len(campaigns) == 2

    # Verify one campaign is from each profile
    profile_names = {c["profile_name"] for c in campaigns}
    assert profile_names == {"trend_with_risk", "baseline_no_risk"}


def test_campaign_config_includes_all_dimensions(tmp_path: Path) -> None:
    """Test that generated campaigns include all required dimensions."""
    yaml_content = """
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EUR_USD
  execution_timeframes:
    - 15min

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/test.yaml
    rem_path: config/rem/test.yaml
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10, slow_length: 20 }
        rem_params: { atr_length: 14, atr_multiplier: 2.0 }
"""
    yaml_file = tmp_path / "test_meta_campaign.yaml"
    yaml_file.write_text(yaml_content)

    config = MetaCampaignConfig.from_yaml(yaml_file)
    campaigns = calculate_cartesian_product(config)

    assert len(campaigns) == 1
    campaign = campaigns[0]

    # Verify all required fields are present
    assert "date_range" in campaign
    assert campaign["date_range"]["start"] == "2020-01-01"
    assert campaign["date_range"]["end"] == "2020-12-31"
    assert campaign["instrument"] == "EUR_USD"
    assert campaign["execution_timeframe"] == "15min"
    assert campaign["strategy_path"] == "config/strategy/test.yaml"
    assert campaign["rem_path"] == "config/rem/test.yaml"
    assert campaign["archetype"] == "trend_following"
    assert campaign["strategy_params"] == {"fast_length": 10, "slow_length": 20}
    assert campaign["rem_params"] == {"atr_length": 14, "atr_multiplier": 2.0}
    assert campaign["meta_campaign_id"] == "test_campaign"
    assert campaign["profile_name"] == "test_profile"


def test_generate_campaign_filename() -> None:
    """Test campaign filename generation."""
    filename = generate_campaign_filename(
        meta_campaign_id="trend_following_model_generation",
        profile_name="trend_with_risk",
        instrument="EUR_USD",
        timeframe="15min",
        param_index=0,
    )

    assert (
        filename
        == "trend_following_model_generation_trend_with_risk_EUR_USD_15min_00.yaml"
    )


def test_generate_campaign_filename_with_larger_index() -> None:
    """Test campaign filename with larger param_index."""
    filename = generate_campaign_filename(
        meta_campaign_id="test_campaign",
        profile_name="test_profile",
        instrument="GBP_USD",
        timeframe="1H",
        param_index=23,
    )

    assert filename == "test_campaign_test_profile_GBP_USD_1H_23.yaml"


def test_campaign_config_to_yaml_dict(tmp_path: Path) -> None:
    """Test conversion of campaign config to YAML-compatible dict."""
    # Create mock strategy and rem files
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text("strategy_type: ema_crossover\n")

    rem_path = tmp_path / "rem.yaml"
    rem_path.write_text("rem_type: chandelier_stop\n")

    campaign = {
        "meta_campaign_id": "test_campaign",
        "profile_name": "test_profile",
        "date_range": {"start": "2020-01-01", "end": "2020-12-31"},
        "instrument": "EUR_USD",
        "execution_timeframe": "15min",
        "strategy_path": str(strategy_path),
        "rem_path": str(rem_path),
        "archetype": "trend_following",
        "strategy_params": {"fast_length": 10, "slow_length": 20},
        "rem_params": {"atr_length": 14, "atr_multiplier": 2.0},
    }

    yaml_dict = campaign_config_to_yaml_dict(campaign)

    # Verify structure
    assert "start_date" in yaml_dict
    assert yaml_dict["start_date"] == "2020-01-01"
    assert "end_date" in yaml_dict
    assert yaml_dict["end_date"] == "2020-12-31"
    assert "instrument" in yaml_dict
    assert yaml_dict["instrument"] == "EUR_USD"
    assert "execution_timeframe" in yaml_dict
    assert yaml_dict["execution_timeframe"] == "15min"
    assert "strategy" in yaml_dict
    assert "rem" in yaml_dict
    assert "archetype" in yaml_dict
    assert yaml_dict["archetype"] == "trend_following"
    assert "metadata" in yaml_dict
    assert yaml_dict["metadata"]["meta_campaign_id"] == "test_campaign"
    assert yaml_dict["metadata"]["profile_name"] == "test_profile"
    assert "git_commit" in yaml_dict["metadata"]


def test_campaign_config_to_yaml_dict_without_rem(tmp_path: Path) -> None:
    """Test conversion when rem_path is None (no risk profile)."""
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text("strategy_type: ema_crossover\n")

    campaign = {
        "meta_campaign_id": "test_campaign",
        "profile_name": "baseline_no_risk",
        "date_range": {"start": "2020-01-01", "end": "2020-12-31"},
        "instrument": "EUR_USD",
        "execution_timeframe": "15min",
        "strategy_path": str(strategy_path),
        "rem_path": None,
        "archetype": "trend_following",
        "strategy_params": {"fast_length": 10, "slow_length": 20},
        "rem_params": None,
    }

    yaml_dict = campaign_config_to_yaml_dict(campaign)

    # Verify rem is None or not included
    assert yaml_dict.get("rem") is None or "rem" not in yaml_dict
    assert "strategy" in yaml_dict
    assert yaml_dict["metadata"]["profile_name"] == "baseline_no_risk"


def test_campaign_config_to_yaml_dict_with_nonexistent_files(tmp_path: Path) -> None:
    """Test conversion when strategy/rem files don't exist."""
    campaign = {
        "meta_campaign_id": "test_campaign",
        "profile_name": "test_profile",
        "date_range": {"start": "2020-01-01", "end": "2020-12-31"},
        "instrument": "EUR_USD",
        "execution_timeframe": "15min",
        "strategy_path": str(tmp_path / "nonexistent_strategy.yaml"),
        "rem_path": str(tmp_path / "nonexistent_rem.yaml"),
        "archetype": "trend_following",
        "strategy_params": {"fast_length": 10, "slow_length": 20},
        "rem_params": {"atr_length": 14},
    }

    yaml_dict = campaign_config_to_yaml_dict(campaign)

    # Should still work, just with empty base configs
    assert "strategy" in yaml_dict
    assert yaml_dict["strategy"] == {"fast_length": 10, "slow_length": 20}
    # REM should not be included when file doesn't exist
    assert "rem" not in yaml_dict or yaml_dict.get("rem") is None


def test_campaign_config_to_yaml_dict_with_nonexistent_strategy_only(
    tmp_path: Path,
) -> None:
    """Test conversion when only strategy file doesn't exist."""
    campaign = {
        "meta_campaign_id": "test_campaign",
        "profile_name": "test_profile",
        "date_range": {"start": "2020-01-01", "end": "2020-12-31"},
        "instrument": "EUR_USD",
        "execution_timeframe": "15min",
        "strategy_path": str(tmp_path / "nonexistent_strategy.yaml"),
        "rem_path": None,
        "archetype": "trend_following",
        "strategy_params": {"fast_length": 10, "slow_length": 20},
        "rem_params": None,
    }

    yaml_dict = campaign_config_to_yaml_dict(campaign)

    # Should still work with just strategy_params
    assert "strategy" in yaml_dict
    assert yaml_dict["strategy"] == {"fast_length": 10, "slow_length": 20}
