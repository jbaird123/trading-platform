import json

from trading_platform.core.demo import generate_demo_run


def test_generate_demo_run_includes_instrument(tmp_path):
    # The user_id will be the directory name for the run
    user_id = "demo_test"
    # Use tmp_path for the runs_dir to avoid polluting the project root
    runs_dir = tmp_path / "runs"
    run_path = generate_demo_run(user_id=user_id, runs_dir=runs_dir)

    assert run_path.exists()

    config_path = run_path / "config.json"
    assert config_path.exists()

    with open(config_path) as f:
        config_data = json.load(f)

    assert "instrument" in config_data
    assert "symbol" in config_data["instrument"]
    assert config_data["instrument"]["symbol"] == "EURUSD"
