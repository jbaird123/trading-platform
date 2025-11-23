from __future__ import annotations

import subprocess
from pathlib import Path


def test_meta_campaign_plan_requires_config_argument(tmp_path: Path) -> None:
    """Test that --config argument is required."""
    result = subprocess.run(
        ["poetry", "run", "tp", "meta-campaign-plan"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert (
        "--config is required" in result.stderr or "required" in result.stderr.lower()
    )


def test_meta_campaign_plan_generates_campaign_files(tmp_path: Path) -> None:
    """Test that campaign files are generated correctly."""
    # Create minimal meta-campaign config
    meta_config = tmp_path / "test_meta_campaign.yaml"
    meta_config.write_text("""
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EURUSD
  execution_timeframes:
    - 15min

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/ema_crossover.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10, slow_length: 20 }
      - strategy_params: { fast_length: 20, slow_length: 50 }
""")

    output_dir = tmp_path / "campaigns"
    output_dir.mkdir()

    result = subprocess.run(
        [
            "poetry",
            "run",
            "tp",
            "meta-campaign-plan",
            "--config",
            str(meta_config),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Should generate 1 campaign file with 2 runs in run_matrix
    # (1 instrument × 1 timeframe × 1 profile, with 2 param sets consolidated)
    generated_files = list(output_dir.glob("*.yaml"))
    assert len(generated_files) == 1


def test_meta_campaign_plan_output_yaml_structure(tmp_path: Path) -> None:
    """Test that generated YAML files have correct structure."""
    import yaml

    meta_config = tmp_path / "test_meta_campaign.yaml"
    meta_config.write_text("""
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EURUSD
  execution_timeframes:
    - 15min

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/ema_crossover.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10, slow_length: 20 }
""")

    output_dir = tmp_path / "campaigns"
    output_dir.mkdir()

    result = subprocess.run(
        [
            "poetry",
            "run",
            "tp",
            "meta-campaign-plan",
            "--config",
            str(meta_config),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0

    # Load one generated file and verify structure
    generated_files = list(output_dir.glob("*.yaml"))
    assert len(generated_files) == 1

    with open(generated_files[0]) as f:
        campaign_config = yaml.safe_load(f)

    # Verify required fields in new format with run_matrix
    assert "campaign_id" in campaign_config
    assert "execution_timeframe" in campaign_config
    assert campaign_config["execution_timeframe"] == "15min"
    assert "strategy_path" in campaign_config
    assert "strategy_archetype" in campaign_config
    assert "run_matrix" in campaign_config
    assert len(campaign_config["run_matrix"]) >= 1
    # Verify first run has required fields
    first_run = campaign_config["run_matrix"][0]
    assert "start_date" in first_run
    assert first_run["start_date"] == "2020-01-01"
    assert "end_date" in first_run
    assert "instrument" in first_run


def test_meta_campaign_plan_prints_summary(tmp_path: Path) -> None:
    """Test that command prints summary of generated campaigns."""
    meta_config = tmp_path / "test_meta_campaign.yaml"
    meta_config.write_text("""
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EURUSD
  execution_timeframes:
    - 15min

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/ema_crossover.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10 }
""")

    output_dir = tmp_path / "campaigns"
    output_dir.mkdir()

    result = subprocess.run(
        [
            "poetry",
            "run",
            "tp",
            "meta-campaign-plan",
            "--config",
            str(meta_config),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Generated" in result.stdout
    assert "campaign" in result.stdout.lower()


def test_meta_campaign_plan_overwrites_with_force_flag(tmp_path: Path) -> None:
    """Test that --force flag allows overwriting existing files."""
    meta_config = tmp_path / "test_meta_campaign.yaml"
    meta_config.write_text("""
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EURUSD
  execution_timeframes:
    - 15min

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/ema_crossover.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10 }
""")

    output_dir = tmp_path / "campaigns"
    output_dir.mkdir()

    # Generate once
    result1 = subprocess.run(
        [
            "poetry",
            "run",
            "tp",
            "meta-campaign-plan",
            "--config",
            str(meta_config),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result1.returncode == 0

    # Modify a generated file
    generated_files = list(output_dir.glob("*.yaml"))
    assert len(generated_files) == 1
    original_content = generated_files[0].read_text()
    generated_files[0].write_text(original_content + "\n# MODIFIED\n")

    # Generate again with --force
    result2 = subprocess.run(
        [
            "poetry",
            "run",
            "tp",
            "meta-campaign-plan",
            "--config",
            str(meta_config),
            "--output-dir",
            str(output_dir),
            "--force",
        ],
        capture_output=True,
        text=True,
    )
    assert result2.returncode == 0

    # Verify file was overwritten (MODIFIED comment should be gone)
    new_content = generated_files[0].read_text()
    assert "# MODIFIED" not in new_content


def test_meta_campaign_plan_fails_without_force_if_files_exist(tmp_path: Path) -> None:
    """Test that command fails if files exist and --force not provided."""
    meta_config = tmp_path / "test_meta_campaign.yaml"
    meta_config.write_text("""
meta_campaign_id: test_campaign
description: "Test"

run_grid:
  date_ranges:
    - { start: "2020-01-01", end: "2020-12-31" }
  instruments:
    - EURUSD
  execution_timeframes:
    - 15min

strategy_profiles:
  - name: test_profile
    strategy_path: config/strategy/ema_crossover.yaml
    rem_path: null
    archetype: trend_following
    param_grid:
      - strategy_params: { fast_length: 10 }
""")

    output_dir = tmp_path / "campaigns"
    output_dir.mkdir()

    # Generate once
    result1 = subprocess.run(
        [
            "poetry",
            "run",
            "tp",
            "meta-campaign-plan",
            "--config",
            str(meta_config),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result1.returncode == 0

    # Try to generate again without --force
    result2 = subprocess.run(
        [
            "poetry",
            "run",
            "tp",
            "meta-campaign-plan",
            "--config",
            str(meta_config),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )
    assert result2.returncode != 0
    assert (
        "existing" in result2.stderr.lower()
        or "--force" in result2.stderr
        or "already exists" in result2.stderr.lower()
    )
