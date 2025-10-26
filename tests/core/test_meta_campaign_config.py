from __future__ import annotations

from pathlib import Path

import pytest
from trading_platform.core.meta_campaign_config import (
    MetaCampaignConfig,
)


def test_meta_campaign_config_loads_from_yaml(tmp_path: Path) -> None:
    """Test that MetaCampaignConfig can load from YAML with all fields."""
    yaml_content = """
meta_campaign_id: test_campaign
description: "Test campaign description"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EUR_USD
  execution_timeframes:
    - 15min
    - 1H

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

    assert config.meta_campaign_id == "test_campaign"
    assert config.description == "Test campaign description"
    assert len(config.run_grid.date_ranges) == 1
    assert config.run_grid.date_ranges[0]["start"] == "2020-01-01"
    assert len(config.run_grid.instruments) == 1
    assert config.run_grid.instruments[0] == "EUR_USD"
    assert len(config.run_grid.execution_timeframes) == 2
    assert len(config.strategy_profiles) == 1
    assert config.strategy_profiles[0].name == "test_profile"


def test_run_grid_date_ranges_validation(tmp_path: Path) -> None:
    """Test that date_ranges are validated correctly."""
    yaml_content = """
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
    - { start: "2021-01-01", end: "2021-12-31" }
  instruments:
    - EUR_USD
  execution_timeframes:
    - 15min

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10 }
"""
    yaml_file = tmp_path / "test_meta_campaign.yaml"
    yaml_file.write_text(yaml_content)

    config = MetaCampaignConfig.from_yaml(yaml_file)

    assert len(config.run_grid.date_ranges) == 2
    assert all("start" in dr and "end" in dr for dr in config.run_grid.date_ranges)


def test_run_grid_instruments_validation(tmp_path: Path) -> None:
    """Test that instruments list is validated."""
    yaml_content = """
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EUR_USD
    - GBP_USD
    - USD_JPY
  execution_timeframes:
    - 1H

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10 }
"""
    yaml_file = tmp_path / "test_meta_campaign.yaml"
    yaml_file.write_text(yaml_content)

    config = MetaCampaignConfig.from_yaml(yaml_file)

    assert len(config.run_grid.instruments) == 3
    assert all(isinstance(inst, str) for inst in config.run_grid.instruments)


def test_run_grid_execution_timeframes_validation(tmp_path: Path) -> None:
    """Test that execution_timeframes are validated against valid set."""
    yaml_content = """
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EUR_USD
  execution_timeframes:
    - 1min
    - 5min
    - 15min
    - 1H
    - 4H
    - 1D

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10 }
"""
    yaml_file = tmp_path / "test_meta_campaign.yaml"
    yaml_file.write_text(yaml_content)

    config = MetaCampaignConfig.from_yaml(yaml_file)

    valid_timeframes = {"1min", "5min", "15min", "1H", "4H", "1D"}
    assert all(tf in valid_timeframes for tf in config.run_grid.execution_timeframes)


def test_strategy_profile_with_risk(tmp_path: Path) -> None:
    """Test strategy profile with risk parameters."""
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
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: config/master_data_generation/rem/chandelier_stop_v1.yaml
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10, slow_length: 20 }
        rem_params: { atr_length: 22, atr_multiplier: 2.0 }
      - strategy_params: { fast_length: 20, slow_length: 50 }
        rem_params: { atr_length: 14, atr_multiplier: 2.5 }
"""
    yaml_file = tmp_path / "test_meta_campaign.yaml"
    yaml_file.write_text(yaml_content)

    config = MetaCampaignConfig.from_yaml(yaml_file)
    profile = config.strategy_profiles[0]

    assert profile.name == "trend_with_risk"
    assert profile.strategy_path is not None
    assert profile.rem_path is not None
    assert profile.archetype == "trend_following"
    assert len(profile.param_grid) == 2
    assert profile.param_grid[0].strategy_params["fast_length"] == 10
    assert profile.param_grid[0].rem_params is not None
    assert profile.param_grid[0].rem_params["atr_length"] == 22
    assert profile.has_risk() is True


def test_strategy_profile_without_risk(tmp_path: Path) -> None:
    """Test strategy profile without risk parameters (rem_path is null)."""
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
  - name: baseline_no_risk
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 9, slow_length: 21 }
      - strategy_params: { fast_length: 15, slow_length: 45 }
"""
    yaml_file = tmp_path / "test_meta_campaign.yaml"
    yaml_file.write_text(yaml_content)

    config = MetaCampaignConfig.from_yaml(yaml_file)
    profile = config.strategy_profiles[0]

    assert profile.name == "baseline_no_risk"
    assert profile.rem_path is None
    assert len(profile.param_grid) == 2
    assert profile.param_grid[0].rem_params is None
    assert profile.has_risk() is False


def test_meta_campaign_config_validates_required_fields(tmp_path: Path) -> None:
    """Test that missing required fields raise validation errors."""
    # Missing meta_campaign_id
    yaml_content_no_id = """
description: "Test"
run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EUR_USD
  execution_timeframes:
    - 15min
strategy_profiles:
  - name: test
    strategy_path: config/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: {}
"""
    yaml_file = tmp_path / "test_no_id.yaml"
    yaml_file.write_text(yaml_content_no_id)

    with pytest.raises((KeyError, ValueError, TypeError)):
        MetaCampaignConfig.from_yaml(yaml_file)

    # Missing run_grid
    yaml_content_no_grid = """
meta_campaign_id: test_campaign
description: "Test"
strategy_profiles:
  - name: test
    strategy_path: config/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: {}
"""
    yaml_file2 = tmp_path / "test_no_grid.yaml"
    yaml_file2.write_text(yaml_content_no_grid)

    with pytest.raises((KeyError, ValueError, TypeError)):
        MetaCampaignConfig.from_yaml(yaml_file2)

    # Missing strategy_profiles
    yaml_content_no_profiles = """
meta_campaign_id: test_campaign
description: "Test"
run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EUR_USD
  execution_timeframes:
    - 15min
"""
    yaml_file3 = tmp_path / "test_no_profiles.yaml"
    yaml_file3.write_text(yaml_content_no_profiles)

    with pytest.raises((KeyError, ValueError, TypeError)):
        MetaCampaignConfig.from_yaml(yaml_file3)


def test_file_not_found_error(tmp_path: Path) -> None:
    """Test that FileNotFoundError is raised for non-existent file."""
    non_existent_file = tmp_path / "does_not_exist.yaml"

    with pytest.raises(FileNotFoundError, match="Meta-campaign config not found"):
        MetaCampaignConfig.from_yaml(non_existent_file)


def test_invalid_yaml_format(tmp_path: Path) -> None:
    """Test that ValueError is raised for invalid YAML format."""
    yaml_file = tmp_path / "invalid.yaml"
    # Write a YAML that parses to a list instead of dict
    yaml_file.write_text("- item1\n- item2\n")

    with pytest.raises(ValueError, match="Invalid YAML format"):
        MetaCampaignConfig.from_yaml(yaml_file)


def test_date_range_missing_keys(tmp_path: Path) -> None:
    """Test that ValueError is raised when date_range is missing start or end."""
    yaml_content = """
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01" }
  instruments:
    - EUR_USD
  execution_timeframes:
    - 15min

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10 }
"""
    yaml_file = tmp_path / "test_missing_end.yaml"
    yaml_file.write_text(yaml_content)

    with pytest.raises(ValueError, match="Date range missing 'start' or 'end' key"):
        MetaCampaignConfig.from_yaml(yaml_file)


def test_invalid_timeframe(tmp_path: Path) -> None:
    """Test that ValueError is raised for invalid execution_timeframe."""
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
    - 2H

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/test.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10 }
"""
    yaml_file = tmp_path / "test_invalid_tf.yaml"
    yaml_file.write_text(yaml_content)

    with pytest.raises(ValueError, match="Invalid execution_timeframe: 2H"):
        MetaCampaignConfig.from_yaml(yaml_file)
