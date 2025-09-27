import json
import shutil
from pathlib import Path

from trading_platform.core.demo import generate_demo_run


def test_generate_demo_run_includes_instrument():
    try:
        # The user_id will be the directory name for the run
        user_id = "demo_test"
        run_path = generate_demo_run(user_id=user_id)

        # The actual run directory is inside the user's directory
        run_name = run_path.name
        full_run_path = Path("runs") / user_id / run_name

        assert full_run_path.exists()

        config_path = full_run_path / "config.json"
        assert config_path.exists()

        with open(config_path) as f:
            config_data = json.load(f)

        assert "instrument" in config_data
        assert "symbol" in config_data["instrument"]
        assert config_data["instrument"]["symbol"] == "EURUSD"
    finally:
        # Clean up the created runs directory
        if Path("runs").exists():
            shutil.rmtree("runs")
