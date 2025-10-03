# src/trading_platform/core/paths.py
from pathlib import Path

# The absolute path to the project's root directory, determined by locating
# the 'pyproject.toml' file.
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()

# The central workspace for all generated artifacts.
WORKSPACE_DIR = PROJECT_ROOT / "workspace"

# Core subdirectories within the workspace.
ARTIFACTS_DIR = WORKSPACE_DIR / "artifacts"
CACHE_DIR = WORKSPACE_DIR / "cache"
COVERAGE_DIR = WORKSPACE_DIR / "coverage"
LOGS_DIR = WORKSPACE_DIR / "logs"
REPORTS_DIR = WORKSPACE_DIR / "reports"
RUNS_DIR = WORKSPACE_DIR / "runs"  # For backtest and live run outputs

# MLflow specific directories and URIs.
MLFLOW_DIR = WORKSPACE_DIR / "mlflow"
MLFLOW_DEFAULT_URI = f"file://{MLFLOW_DIR / 'default_runs'}"
MLFLOW_TEST_URI = f"file://{MLFLOW_DIR / 'test_runs'}"
MLFLOW_CUSTOM_URI = f"file://{MLFLOW_DIR / 'custom_runs'}"

# Directory for test-specific outputs.
TESTING_DIR = WORKSPACE_DIR / "testing"
TEST_RUN_DIR = TESTING_DIR / "test_run"


def ensure_dirs():
    """
    Creates all defined workspace directories if they do not already exist.
    This function can be called at the start of application execution.
    """
    for path in [
        WORKSPACE_DIR,
        ARTIFACTS_DIR,
        CACHE_DIR,
        COVERAGE_DIR,
        LOGS_DIR,
        REPORTS_DIR,
        RUNS_DIR,
        MLFLOW_DIR,
        TESTING_DIR,
        TEST_RUN_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
