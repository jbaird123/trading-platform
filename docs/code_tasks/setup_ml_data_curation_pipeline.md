# ML Data Curation Pipeline Implementation Plan

This document outlines the steps to create a robust pipeline for curating machine learning training data from backtest results, with versioning handled by DVC and remote storage on AWS S3.

**Branch Name:** `feature/ml-data-curation`

Before starting, create and switch to the specified branch:
`git checkout -b feature/ml-data-curation`

---

### Phase 1: Setup and Core Logic

1.  [ ] **Create Storage Directories:**
    -   Create the new nested directory structure: `data/dvc/processed/training_sets/`. This path will store the curated datasets.

2.  [ ] **Update .gitignore:**
    -   Open the root `.gitignore` file.
    -   Add the following line to ensure DVC-tracked data is not committed to the repository:
        ```
        /data/dvc/
        ```

3.  [ ] **Write Test for Curation Script CLI Entrypoint:**
    -   In `tests/cli/test_cli.py`, add a new test function `test_cmd_ai_curate_data`.
    -   This test should use `unittest.mock.patch` to mock the `trading_platform.ai.data_curation.run_curation_pipeline` function (which does not exist yet).
    -   The test will invoke the main CLI function with the arguments `ai-curate-data --source-dir /fake/dir --output-file /fake/file.parquet`.
    -   Assert that the mocked `run_curation_pipeline` function was called exactly once with the correct arguments.

4.  [ ] **Implement Curation Script CLI Entrypoint:**
    -   In `src/trading_platform/cli.py`:
        -   Import a new (not-yet-created) function: `from trading_platform.ai.data_curation import run_curation_pipeline`.
        -   Create a new command function `cmd_ai_curate_data(args: argparse.Namespace) -> int`.
        -   This function will call `run_curation_pipeline(source_dir=Path(args.source_dir), output_file=Path(args.output_file))` and return 0.
        -   In the `main()` function, add a new subparser for the `ai-curate-data` command. It should have two required arguments: `--source-dir` and `--output-file`.
        -   Set its default function to `cmd_ai_curate_data`.

5.  [ ] **Write Test for Trade Data Extraction:**
    -   Create a new file: `src/trading_platform/ai/feature_engineering/test_trade_extractor.py`.
    -   In this file, create a test function `test_extract_trades_from_brief`.
    -   The test should use a sample `brief.json` structure (as a dictionary) containing a `trades` array with at least two trades. Each trade must have nested `entry_context` and `exit_context` objects with mock indicator data.
    -   The test will call a new function `extract_trades_from_brief(brief_data)` with this dictionary.
    -   Assert that the function returns a pandas DataFrame.
    -   Assert that the DataFrame has 2 rows.
    -   Assert that the DataFrame columns are flattened correctly (e.g., a column named `entry_context_RSI_14` exists).

6.  [ ] **Implement Trade Data Extraction Logic:**
    -   Create a new file: `src/trading_platform/ai/feature_engineering/trade_extractor.py`.
    -   Create the function `extract_trades_from_brief(brief_data: dict) -> pd.DataFrame`.
    -   This function will:
        -   Access the `trades` list from the `brief_data` dictionary.
        -   Use `pandas.json_normalize` to flatten each trade object into a tabular format. The `sep` argument should be `_`.
        -   Return the resulting DataFrame.

7.  [ ] **Write Test for Curation Pipeline Orchestrator:**
    -   Create a new file: `src/trading_platform/ai/test_data_curation.py`.
    -   Create a test function `test_run_curation_pipeline`.
    -   This test will use `pathlib.Path` and `tmp_path` to create a temporary directory structure simulating research results (e.g., `tmp_path/run1/brief.json`, `tmp_path/run2/brief.json`).
    -   Each mock `brief.json` should be a valid JSON string containing a `trades` list.
    -   The test will call `run_curation_pipeline(source_dir=tmp_path, output_file=tmp_path / 'output.parquet')`.
    -   Assert that the `output.parquet` file is created.
    -   Read the Parquet file back into a DataFrame and assert that it contains the correct total number of trades from all mock briefs.

8.  [ ] **Implement Curation Pipeline Orchestrator:**
    -   Create a new file: `src/trading_platform/ai/data_curation.py`.
    -   Create the function `run_curation_pipeline(source_dir: Path, output_file: Path)`.
    -   This function will:
        -   Use `source_dir.rglob('brief.json')` to find all brief files.
        -   Initialize an empty list to hold DataFrames.
        -   Loop through each found `brief.json` file.
        -   Inside the loop, read the JSON data, call `extract_trades_from_brief`, and append the resulting DataFrame to the list.
        -   After the loop, use `pd.concat` to merge all DataFrames in the list.
        -   Save the final, aggregated DataFrame to `output_file` using `df.to_parquet()`.

### Phase 2: DVC and S3 Remote Setup

9.  [ ] **Initialize DVC:**
    -   In your terminal at the project root, run the command `dvc init`.
    -   This will create DVC-related files and directories (e.g., `.dvc/`).
    -   Commit the newly created files to git: `git add .dvc .dvcignore && git commit -m "build: Initialize DVC"`

10. [ ] **Configure DVC S3 Remote:**
    -   **Prerequisites**: Ensure you have an AWS S3 bucket and your local environment is configured with AWS credentials (e.g., via `aws configure`).
    -   Add the S3 bucket as a DVC remote. Replace `your-bucket-name` with your actual S3 bucket name.
        ```bash
        dvc remote add s3_storage s3://your-bucket-name/dvc-storage
        ```
    -   Set the new remote as the default for all push and pull operations.
        ```bash
        dvc remote default s3_storage
        ```
    -   Commit the DVC configuration changes to Git.
        ```bash
        git add .dvc/config
        git commit -m "build: Configure DVC S3 remote storage"
        ```

### Phase 3: Track and Push Data to S3

11. [ ] **Run Curation and Push Data to S3:**
    -   First, run the curation script on a real research directory to generate the initial training set. Example command:
        ```bash
        poetry run python -m trading_platform.cli ai-curate-data --source-dir workspace/research/campaign_20251005_discovery/ --output-file data/dvc/processed/training_sets/master_trade_log.parquet
        ```
    -   Next, add the generated dataset to DVC tracking:
        ```bash
        dvc add data/dvc/processed/training_sets/master_trade_log.parquet
        ```
    -   Push the tracked data from your local DVC cache to the S3 remote:
        ```bash
        dvc push
        ```
    -   Commit the DVC pointer file to git:
        ```bash
        git add data/dvc/processed/training_sets/master_trade_log.parquet.dvc
        git commit -m "data: Track and push initial master trade log"
        ```

12. [ ] **Relocate, Track, and Push Market Data to S3:**
    -   Create the new directory for raw data:
        ```bash
        mkdir -p data/dvc/raw
        ```
    -   Move the existing market data directories:
        ```bash
        mv data/full data/dvc/raw/
        mv data/incremental data/dvc/raw/
        ```
    -   Add the relocated directories to DVC tracking:
        ```bash
        dvc add data/dvc/raw/full
        dvc add data/dvc/raw/incremental
        ```
    -   Push the tracked directories to the S3 remote:
        ```bash
        dvc push
        ```
    -   Commit the new DVC pointer files:
        ```bash
        git add data/dvc/raw/full.dvc data/dvc/raw/incremental.dvc
        git commit -m "data: Track and push market data directories"
        ```

### Phase 4: Update Dependent Code

13. [ ] **Centralize Raw Data Path:**
    -   Open `src/trading_platform/core/paths.py`.
    -   Add a new constant `RAW_DATA_DIR` that points to the new location for raw market data:
        ```python
        RAW_DATA_DIR = PROJECT_ROOT / "data" / "dvc" / "raw"
        ```

14. [ ] **Update Data Handler Path:**
    -   Open `src/trading_platform/cli.py`.
    -   Find the instantiation of the `DataHandler`.
    -   Change the `data_root` argument to use the new constant from the `paths` module:
        ```python
        # Before
        data_root=paths.PROJECT_ROOT / "data",

        # After
        data_root=paths.RAW_DATA_DIR,
        ```

15. [ ] **Update Data Sync Script:**
    -   Open the `scripts/sync-all.sh` file.
    -   Find the line that defines the `DATA_DIR` variable.
    -   Update the path to point to the new raw data directory:
        ```bash
        # Before
        DATA_DIR="$PROJECT_ROOT/data"

        # After
        DATA_DIR="$PROJECT_ROOT/data/dvc/raw"
        ```
    -   Additionally, update the `mkdir` command in the same script to ensure it only creates the base directory if it doesn't exist:
        ```bash
        # Before
        mkdir -p "$DATA_DIR/full"
        mkdir -p "$DATA_DIR/incremental"

        # After
        mkdir -p "$DATA_DIR"
        ```

### Phase 5: DVC Utility Scripts

16. [ ] **Create DVC script directory:**
    -   Execute the following command to create a dedicated directory for DVC-related scripts:
        ```bash
        mkdir -p scripts/dvc
        ```

17. [ ] **Create DVC sync script:**
    -   Create a new file named `scripts/dvc/sync.sh`.
    -   Add the following content to the file. This script will accept `push` or `pull` as an argument to synchronize data with the DVC remote.
        ```bash
        #!/bin/bash
        set -e

        ACTION=$1

        if [[ "$ACTION" != "push" && "$ACTION" != "pull" ]]; then
            echo "Error: Invalid action. Use 'push' or 'pull'."
            exit 1
        fi

        echo "Executing dvc $ACTION..."
        dvc "$ACTION"
        echo "DVC sync ($ACTION) complete."
        ```

18. [ ] **Make sync script executable:**
    -   Run the following command to make the script executable:
        ```bash
        chmod +x scripts/dvc/sync.sh
        ```

19. [ ] **Commit the new script:**
    -   Add the new script to Git version control.
        ```bash
        git add scripts/dvc/sync.sh
        git commit -m "feat: Add dvc sync utility script"
        ```
