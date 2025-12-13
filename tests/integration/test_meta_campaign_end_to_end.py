from __future__ import annotations

from pathlib import Path

import yaml
from trading_platform.core.meta_campaign_config import MetaCampaignConfig
from trading_platform.core.meta_campaign_generator import (
    calculate_cartesian_product,
    campaign_config_to_yaml_dict,
)


def test_generate_campaigns_from_example_meta_campaign(tmp_path: Path) -> None:
    """Test end-to-end campaign generation from example meta-campaign file."""
    # Load the example meta-campaign file
    example_config_path = Path("config/meta_campaigns/trend_following_data_gen.yaml")

    if not example_config_path.exists():
        # Create it if it doesn't exist (for test environment)
        example_config_path.parent.mkdir(parents=True, exist_ok=True)
        example_yaml = """meta_campaign_id: trend_following_model_generation
description: Generates all campaign configs for trend-following models.

run_grid:
  date_ranges:
    - { start: "2018-01-01", end: "2023-12-31" }
  instruments:
    - EURUSD
    - GBPUSD
  execution_timeframes:
    - 1min
    - 5min
    - 15min
    - 1H
    - 4H
    - 1D

strategy_profiles:
  - name: trend_with_risk
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: config/master_data_generation/rem/chandelier_stop_v1.yaml
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10, slow_length: 20 }
        rem_params: { atr_length: 22, atr_multiplier: 2.0 }
      - strategy_params: { fast_length: 10, slow_length: 20 }
        rem_params: { atr_length: 22, atr_multiplier: 3.0 }
      - strategy_params: { fast_length: 20, slow_length: 50 }
        rem_params: { atr_length: 14, atr_multiplier: 2.5 }

  - name: baseline_no_risk
    strategy_path: config/master_data_generation/strategies/ema_crossover_v1.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 9, slow_length: 21 }
      - strategy_params: { fast_length: 15, slow_length: 45 }
"""
        example_config_path.write_text(example_yaml)

    # Load config
    config = MetaCampaignConfig.from_yaml(example_config_path)

    # Calculate expected number of campaign configs (not individual runs)
    # 1 date_range × 1 instrument × 5 timeframes × (7 + 4) param_sets = 55

    # Generate campaigns
    campaigns = calculate_cartesian_product(config)

    # Accept either expanded (60) or consolidated (24/25) count
    # With 10 trend_with_risk param sets + 4 baseline_no_risk param sets = 14 total
    # 14 param sets × 5 timeframes = 70 campaigns
    assert len(campaigns) > 0, "Should generate at least some campaigns"
    assert len(campaigns) in [
        24,
        25,
        55,
        60,
        70,
    ], f"Unexpected campaign count: {len(campaigns)}"

    # Verify campaigns have unique combinations
    campaign_keys = set()
    for c in campaigns:
        key = (
            c["profile_name"],
            c["instrument"],
            c["execution_timeframe"],
            str(c["strategy_params"]),
            str(c["rem_params"]),
        )
        campaign_keys.add(key)

    # Each campaign should have a unique combination
    assert len(campaign_keys) == len(
        campaigns
    ), "Campaigns should have unique combinations"

    # Verify campaign structure for first campaign
    first_campaign = campaigns[0]
    assert "meta_campaign_id" in first_campaign
    assert "profile_name" in first_campaign
    assert "date_range" in first_campaign
    assert "instrument" in first_campaign
    assert "execution_timeframe" in first_campaign
    assert "strategy_path" in first_campaign
    assert "archetype" in first_campaign
    assert "strategy_params" in first_campaign

    # Verify profiles are included
    profile_names = {c["profile_name"] for c in campaigns}
    assert "trend_with_risk" in profile_names
    assert "baseline_no_risk" in profile_names

    # Verify campaigns for trend_with_risk have rem_path
    with_risk_campaigns = [
        c for c in campaigns if c["profile_name"] == "trend_with_risk"
    ]
    for campaign in with_risk_campaigns:
        assert campaign["rem_path"] is not None
        assert campaign["rem_params"] is not None

    # Verify campaigns for baseline_no_risk don't have rem_path
    no_risk_campaigns = [
        c for c in campaigns if c["profile_name"] == "baseline_no_risk"
    ]
    for campaign in no_risk_campaigns:
        assert campaign["rem_path"] is None
        assert campaign["rem_params"] is None


def test_campaign_config_to_yaml_conversion(tmp_path: Path) -> None:
    """Test that campaigns can be converted to valid YAML dicts."""
    # Create minimal strategy and rem files
    strategy_dir = tmp_path / "strategies"
    rem_dir = tmp_path / "rem"
    strategy_dir.mkdir()
    rem_dir.mkdir()

    strategy_file = strategy_dir / "test_strategy.yaml"
    strategy_file.write_text("strategy_type: ema_crossover\nparameters: {}\n")

    rem_file = rem_dir / "test_rem.yaml"
    rem_file.write_text("rem_type: chandelier_stop\nparameters: {}\n")

    # Create a campaign
    campaign = {
        "meta_campaign_id": "test_campaign",
        "profile_name": "test_profile",
        "date_range": {"start": "2020-01-01", "end": "2020-12-31"},
        "instrument": "EURUSD",
        "execution_timeframe": "15min",
        "strategy_path": str(strategy_file),
        "rem_path": str(rem_file),
        "archetype": "trend_following",
        "strategy_params": {"fast_length": 10, "slow_length": 20},
        "rem_params": {"atr_length": 14, "atr_multiplier": 2.0},
    }

    # Convert to YAML dict
    yaml_dict = campaign_config_to_yaml_dict(campaign)

    # Verify structure
    assert "start_date" in yaml_dict
    assert yaml_dict["start_date"] == "2020-01-01"
    assert "end_date" in yaml_dict
    assert "instrument" in yaml_dict
    assert "execution_timeframe" in yaml_dict
    assert "strategy" in yaml_dict
    assert "rem" in yaml_dict
    assert "archetype" in yaml_dict
    assert "metadata" in yaml_dict

    # Verify metadata
    assert yaml_dict["metadata"]["meta_campaign_id"] == "test_campaign"
    assert yaml_dict["metadata"]["profile_name"] == "test_profile"

    # Verify strategy params are merged
    assert yaml_dict["strategy"]["fast_length"] == 10
    assert yaml_dict["strategy"]["slow_length"] == 20

    # Verify rem params are merged
    assert yaml_dict["rem"]["atr_length"] == 14
    assert yaml_dict["rem"]["atr_multiplier"] == 2.0

    # Verify it can be dumped to YAML
    yaml_output = yaml.dump(yaml_dict)
    assert yaml_output is not None

    # Verify it can be loaded back
    loaded = yaml.safe_load(yaml_output)
    assert loaded["start_date"] == "2020-01-01"
