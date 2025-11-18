# Campaign Runner Implementation Plan

This document implements the missing Campaign Runner infrastructure described in `docs/ai/05_ml_data_curation_guide.md` Section 6. The Campaign Runner automates the execution of reproducible backtest batches, enabling systematic ML training data generation.

**Context:** During the multi-timeframe features implementation (2025-10-23), we discovered that while the feature computation engine was built, the automated campaign orchestration system described in the ML data curation guide was never implemented. Users currently must manually create RunConfig files and execute backtests one-by-one. This implementation adds the missing automation layer.

**What Already Exists (and will be leveraged):**
- ✅ `tp run-backtest` - Backtest execution engine
- ✅ `extract_trades_from_brief()` - Trade data extraction with rich context
- ✅ `tp ai-curate-data` - Data aggregation into parquet
- ✅ Multi-timeframe contextual features - Auto-captured during backtests
- ✅ DVC + S3 - Data versioning infrastructure
- ✅ Pydantic validation - RunConfig schema validation

**What This Implements:**
- Campaign YAML configuration system with full provenance tracking (git commit, dependencies, DVC versions, **data snapshot ID**)
- Automated execution plan generation from campaign matrix
- Batch backtest execution with progress tracking and failure artifact generation
- Artifact collection using prescribed `data/candidates/<campaign_id>/` structure
- Automated validation with quality gates (schema, data quality, dedupe, **drift monitoring via KS-statistic**, indicator registry)
- Manual review workflow with three decision states stored in **campaign-level decision.yaml**
- Enrichment stage that creates `data/enriched/<campaign_id>/rich_trades.parquet`
- Publishing approved results to master trade log with **automated DVC tracking** and full audit trail

**Alignment with Guide Requirements:**
- ✅ Section 5.2: Candidate submission workflow with **campaign-level decision.yaml** (lines 114-118)
- ✅ Section 5.3: Complete quality gates (schema, dedupe, **drift KS-stat check**, audit logging) (lines 133-143)
- ⚠️ Section 5.4: Manual overrides (**NOT IMPLEMENTED** - future work, requires `data/overrides/<campaign_id>.yaml`)
- ✅ Section 6.1: Campaign runner with **full provenance including data version** (line 164), execution, artifact packaging
- ✅ Section 6.4: Failure handling with `failure_report.json` and `campaign_complete.yaml`

**Branch Name:** `feature/campaign-runner`

Before starting, create and switch to the specified branch:
```bash
git checkout -b feature/campaign-runner
```

---

## Phase 1: Campaign Configuration Schema & Provenance

### 1. [ ] Create test module for campaign models
- Create the new file: `tests/ai/campaigns/test_campaign_models.py`
- Import `pytest`, `pydantic`, and `Path` from `pathlib`
- This file will house all tests for campaign configuration validation

### 2. [ ] Write test for basic CampaignConfig validation
- In `tests/ai/campaigns/test_campaign_models.py`, add function `test_campaign_config_validates_required_fields`
- Create a minimal valid campaign dictionary with:
  - `campaign_id: "test_campaign"`
  - `strategy_path: "config/strategy/example.yaml"`
  - `execution_timeframe: "15m"`
  - `run_matrix: []` (empty list for now)
  - `strategy_archetype: "trend_following"`
- Import the not-yet-created `CampaignConfig` from `trading_platform.ai.campaigns.models`
- Assert that `CampaignConfig.model_validate(campaign_dict)` succeeds without raising

### 3. [ ] Write test for CampaignConfig missing required fields
- In `tests/ai/campaigns/test_campaign_models.py`, add function `test_campaign_config_rejects_missing_fields`
- Create a dictionary missing the `strategy_archetype` field
- Use `pytest.raises(ValidationError)` to assert that validation fails
- Assert the error message contains "strategy_archetype" and "required"

### 4. [ ] Write test for RunMatrixEntry validation
- In `tests/ai/campaigns/test_campaign_models.py`, add function `test_run_matrix_entry_validates_dates`
- Create a valid `RunMatrixEntry` dictionary with:
  - `instrument: "EURUSD"`
  - `start_date: "2023-01-01"`
  - `end_date: "2023-12-31"`
- Import the not-yet-created `RunMatrixEntry` from `trading_platform.ai.campaigns.models`
- Assert that `RunMatrixEntry.model_validate(entry_dict)` succeeds

### 5. [ ] Write test for RunMatrixEntry with parameter overrides
- In `tests/ai/campaigns/test_campaign_models.py`, add function `test_run_matrix_entry_accepts_param_overrides`
- Create a `RunMatrixEntry` dictionary with `param_overrides: {"fast_length": 10, "slow_length": 20}`
- Assert validation succeeds
- Assert `entry.param_overrides == {"fast_length": 10, "slow_length": 20}`

### 6. [ ] Write test for CampaignConfig with contextual features
- In `tests/ai/campaigns/test_campaign_models.py`, add function `test_campaign_config_accepts_contextual_features`
- Create a campaign dictionary with `contextual_features` list containing one feature:
  - `name: "1h_rsi"`
  - `type: "RSI"`
  - `params: {"length": 14}`
  - `timeframe: "1h"`
- Assert validation succeeds
- Assert the feature can be accessed via `config.contextual_features[0]`

### 7. [ ] Write test for Provenance model with full metadata
- In `tests/ai/campaigns/test_campaign_models.py`, add function `test_provenance_captures_all_metadata`
- Create a `Provenance` dictionary with:
  - `git_commit: "abc1234"`
  - `poetry_lock_sha256: "deadbeef..."`
  - `python_version: "3.12.0"`
  - `platform: "darwin"`
  - `dvc_version: "3.63.0"`
  - `data_snapshot_id: "a1b2c3d4e5f6"` (DVC data version hash)
- Import not-yet-created `Provenance` from `trading_platform.ai.campaigns.models`
- Assert validation succeeds
- Assert all fields are accessible including `data_snapshot_id`

### 8. [ ] Implement CampaignConfig Pydantic model
- Create the new file: `src/trading_platform/ai/campaigns/models.py`
- Add module docstring: "Campaign configuration models for automated backtest orchestration."
- Import `BaseModel`, `Field` from `pydantic`, `Path`, `List`, `Optional`, `Dict`, `Any`
- Import `FeatureConfig` from `trading_platform.core.config`
- Create class `RunMatrixEntry(BaseModel)` with fields:
  - `instrument: str = Field(..., description="Trading instrument symbol")`
  - `start_date: str = Field(..., description="Backtest start date (YYYY-MM-DD)")`
  - `end_date: str = Field(..., description="Backtest end date (YYYY-MM-DD)")`
  - `param_overrides: Optional[Dict[str, Any]] = Field(default=None, description="Strategy parameter overrides")`
- Create class `Provenance(BaseModel)` with fields:
  - `git_commit: str = Field(..., description="Git commit hash")`
  - `poetry_lock_sha256: str = Field(..., description="SHA256 of poetry.lock")`
  - `python_version: str = Field(..., description="Python interpreter version")`
  - `platform: str = Field(..., description="OS platform")`
  - `dvc_version: str = Field(..., description="DVC version")`
  - `data_snapshot_id: str = Field(..., description="DVC data version/snapshot hash")`
  - `captured_at: str = Field(..., description="ISO timestamp of provenance capture")`
- Create class `CampaignConfig(BaseModel)` with fields:
  - `campaign_id: str = Field(..., description="Unique campaign identifier")`
  - `strategy_path: Path = Field(..., description="Path to strategy YAML file")`
  - `execution_timeframe: str = Field(..., description="Base execution timeframe (e.g., 15m, 1h)")`
  - `strategy_archetype: str = Field(..., description="Strategy type (e.g., trend_following, mean_reversion) - REQUIRED for model selection")`
  - `run_matrix: List[RunMatrixEntry] = Field(..., description="Matrix of runs to execute")`
  - `contextual_features: List[FeatureConfig] = Field(default_factory=list, description="Multi-timeframe features")`
  - `rem_path: Optional[Path] = Field(default=None, description="Path to REM config")`
  - `rmm_path: Optional[Path] = Field(default=None, description="Path to RMM config")`
  - `description: Optional[str] = Field(default=None, description="Campaign description")`
- Set `model_config = {"extra": "forbid"}` on all models

### 9. [ ] Create __init__.py for campaigns module
- Create the new file: `src/trading_platform/ai/campaigns/__init__.py`
- Add exports: `from .models import CampaignConfig, RunMatrixEntry, Provenance`

### 10. [ ] Run tests for Phase 1
- Execute: `poetry run pytest tests/ai/campaigns/test_campaign_models.py -v`
- Assert all 7 tests pass
- Execute: `poetry run pytest tests/ai/campaigns/test_campaign_models.py --cov=src/trading_platform/ai/campaigns/models --cov-report=term-missing`
- Assert 100% coverage for `models.py`

---

## Phase 2: Campaign Plan Generation with Full Provenance

### 11. [ ] Create test module for campaign planner
- Create the new file: `tests/ai/campaigns/test_planner.py`
- Import `pytest`, `json`, `Path`, `tmp_path` fixture, `hashlib`, `sys`, `platform`
- This file tests the logic for expanding campaign YAML into execution plans

### 12. [ ] Write test for capturing provenance metadata
- In `tests/ai/campaigns/test_planner.py`, add function `test_capture_provenance_includes_all_fields(tmp_path, monkeypatch)`
- Create fake `poetry.lock` file in `tmp_path`
- Mock `subprocess.check_output` to return fake git hash and DVC version
- Import not-yet-created `capture_provenance` from `trading_platform.ai.campaigns.planner`
- Call `prov = capture_provenance()`
- Assert `prov.git_commit == "abc1234"`
- Assert `prov.poetry_lock_sha256` is a valid 64-char hex string
- Assert `prov.python_version == sys.version`
- Assert `prov.platform` is not empty
- Assert `prov.dvc_version` contains "dvc"

### 13. [ ] Write test for generating plan from single run matrix entry
- In `tests/ai/campaigns/test_planner.py`, add function `test_generate_plan_single_entry(tmp_path)`
- Create a minimal campaign config with one run matrix entry (EURUSD, 2023-01-01 to 2023-12-31)
- Create a minimal strategy YAML file in `tmp_path / "strategy.yaml"` with:
  ```yaml
  name: "test_strategy"
  type: "EMA_CROSSOVER"
  parameters:
    fast_length: 10
    slow_length: 20
  ```
- Import not-yet-created function `generate_campaign_plan` from `trading_platform.ai.campaigns.planner`
- Call `plan = generate_campaign_plan(campaign_config, output_dir=tmp_path)`
- Assert `plan.campaign_id == "test_campaign"`
- Assert `len(plan.run_configs) == 1`
- Assert `plan.run_configs[0]["run_id"]` contains "test_campaign"
- Assert `plan.provenance` is a Provenance object

### 14. [ ] Write test for generating plan with multiple matrix entries
- In `tests/ai/campaigns/test_planner.py`, add function `test_generate_plan_multiple_entries(tmp_path)`
- Create campaign with 2 instruments (EURUSD, GBPUSD)
- Expected: 2 run configs
- Assert `len(plan.run_configs) == 2`
- Assert run IDs are unique
- Assert both configs have `strategy_archetype` and `execution_timeframe` metadata

### 15. [ ] Write test for plan generation with parameter overrides
- In `tests/ai/campaigns/test_planner.py`, add function `test_generate_plan_applies_param_overrides(tmp_path)`
- Create campaign with one matrix entry having `param_overrides: {"fast_length": 15}`
- Assert the generated RunConfig contains the overridden parameter value
- Load the strategy from the plan's config and check `strategy_params["fast_length"] == 15`

### 16. [ ] Write test for plan generation with contextual features
- In `tests/ai/campaigns/test_planner.py`, add function `test_generate_plan_includes_contextual_features(tmp_path)`
- Create campaign with `contextual_features` containing one multi-timeframe feature
- Assert the generated RunConfig includes the feature in its configuration
- Verify the feature has the correct `timeframe` field set

### 17. [ ] Write test for plan manifest file creation with provenance
- In `tests/ai/campaigns/test_planner.py`, add function `test_generate_plan_saves_manifest_with_provenance(tmp_path)`
- Call `generate_campaign_plan()` with `output_dir=tmp_path`
- Assert file exists: `tmp_path / "plan.json"`
- Load the JSON and verify it contains:
  - `campaign_id`
  - `created_at` timestamp
  - `run_configs` array
  - `provenance` object with all fields (git_commit, poetry_lock_sha256, python_version, platform, dvc_version)

### 18. [ ] Implement CampaignPlan model
- In `src/trading_platform/ai/campaigns/models.py`, create class `CampaignPlan(BaseModel)` with fields:
  - `campaign_id: str`
  - `strategy_archetype: str`
  - `execution_timeframe: str`
  - `created_at: str` (ISO timestamp)
  - `provenance: Provenance`
  - `run_configs: List[Dict[str, Any]]` (serialized RunConfig dictionaries)
  - `total_runs: int`
  - `strategy_path: Path`

### 19. [ ] Implement capture_provenance function
- In `src/trading_platform/ai/campaigns/planner.py` (new file), add module docstring: "Campaign plan generation from YAML configuration."
- Import required modules: `hashlib`, `subprocess`, `sys`, `platform`, `datetime`, `Path`, `json`
- Import `Provenance` from `.models`
- Create function `capture_provenance() -> Provenance`
- Logic:
  1. Get git commit: `subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()`
  2. Calculate poetry.lock hash: `hashlib.sha256(Path("poetry.lock").read_bytes()).hexdigest()`
  3. Get Python version: `sys.version`
  4. Get platform: `platform.platform()`
  5. Get DVC version: `subprocess.check_output(["dvc", "version"]).decode().strip()`
  6. Get data snapshot ID:
     - Run: `dvc_status = subprocess.check_output(["dvc", "status", "data/dvc/raw/", "--json"]).decode()`
     - Parse JSON and create hash: `data_snapshot_id = hashlib.sha256(dvc_status.encode()).hexdigest()[:12]`
     - This captures current state of tracked data directories
  7. Capture timestamp: `datetime.now(datetime.UTC).isoformat()`
  8. Return `Provenance` object with all fields including `data_snapshot_id`

### 20. [ ] Implement generate_campaign_plan function
- In `src/trading_platform/ai/campaigns/planner.py`
- Import required modules: `Path`, `json`, `copy`, `yaml`
- Import `CampaignConfig`, `CampaignPlan` from `.models`
- Import `RunConfig` from `trading_platform.core.config`
- Create function `generate_campaign_plan(campaign: CampaignConfig, output_dir: Path) -> CampaignPlan`
- Logic:
  1. Capture provenance metadata using `capture_provenance()`
  2. Load base strategy from `campaign.strategy_path` using YAML
  3. Initialize empty list `run_configs = []`
  4. For each entry in `campaign.run_matrix`:
     - Generate unique `run_id` as: `f"{campaign.campaign_id}_{entry.instrument}_{index}"`
     - Create `data_request` dict with symbol, timeframe, start, end from entry
     - Deep copy base strategy
     - Apply `entry.param_overrides` to strategy parameters if present
     - Create RunConfig dict with:
       - `run_id`
       - `user_id: f"campaigns/{campaign.campaign_id}"`
       - `data_request`
       - `strategy` (embedded)
       - Add metadata: `instrument_definitions` with `strategy_archetype` and `execution_timeframe`
     - Add contextual features from campaign to strategy
     - Serialize RunConfig to dict
     - Append to `run_configs` list
  5. Create `CampaignPlan` object with provenance
  6. Save plan to `output_dir / "plan.json"` using `plan.model_dump_json(indent=2)`
  7. Return plan

### 21. [ ] Update campaigns __init__.py with planner exports
- In `src/trading_platform/ai/campaigns/__init__.py`, add:
  - `from .planner import generate_campaign_plan, capture_provenance`

### 22. [ ] Run tests for Phase 2
- Execute: `poetry run pytest tests/ai/campaigns/test_planner.py -v`
- Assert all 7 tests pass
- Execute: `poetry run pytest tests/ai/campaigns/test_planner.py --cov=src/trading_platform/ai/campaigns/planner --cov-report=term-missing`
- Assert 100% coverage for `planner.py`

---

## Phase 3: Batch Execution Engine with Failure Artifacts

### 23. [ ] Create test module for campaign runner
- Create the new file: `tests/ai/campaigns/test_runner.py`
- Import `pytest`, `subprocess`, `unittest.mock`, `Path`, `json`
- This file tests batch backtest execution

### 24. [ ] Write test for executing single run from plan
- In `tests/ai/campaigns/test_runner.py`, add function `test_execute_campaign_single_run(tmp_path, monkeypatch)`
- Create a minimal plan with 1 run config
- Mock `subprocess.run` to simulate successful backtest execution
- Import not-yet-created `execute_campaign_runs` from `trading_platform.ai.campaigns.runner`
- Call `results = execute_campaign_runs(plan, runs_dir=tmp_path / "runs", campaign_dir=tmp_path / "campaign")`
- Assert `results.total_runs == 1`
- Assert `results.successful == 1`
- Assert `results.failed == 0`

### 25. [ ] Write test for executing multiple runs sequentially
- In `tests/ai/campaigns/test_runner.py`, add function `test_execute_campaign_multiple_runs(tmp_path, monkeypatch)`
- Create plan with 3 run configs
- Mock subprocess to succeed for all runs
- Assert `results.successful == 3`
- Assert subprocess was called 3 times with correct arguments

### 26. [ ] Write test for handling failed run with fail_fast=True
- In `tests/ai/campaigns/test_runner.py`, add function `test_execute_campaign_fails_fast_on_error(tmp_path, monkeypatch)`
- Create plan with 3 run configs
- Mock subprocess to fail on the 2nd run (returncode != 0)
- Call `execute_campaign_runs(plan, fail_fast=True)`
- Assert execution stops after 2 runs
- Assert `results.successful == 1`, `results.failed == 1`
- Assert 3rd run was never executed

### 27. [ ] Write test for handling failed run with continue_on_error=True
- In `tests/ai/campaigns/test_runner.py`, add function `test_execute_campaign_continues_on_error(tmp_path, monkeypatch)`
- Create plan with 3 run configs
- Mock subprocess to fail on 2nd run but succeed on 1st and 3rd
- Call `execute_campaign_runs(plan, continue_on_error=True)`
- Assert all 3 runs were attempted
- Assert `results.successful == 2`, `results.failed == 1`

### 28. [ ] Write test for execution log creation
- In `tests/ai/campaigns/test_runner.py`, add function `test_execute_campaign_writes_execution_log(tmp_path, monkeypatch)`
- Mock subprocess to succeed
- Execute campaign
- Assert file exists: `campaign_dir / "execution.log"`
- Read log and verify it contains timestamps and run IDs

### 29. [ ] Write test for failure_report.json generation
- In `tests/ai/campaigns/test_runner.py`, add function `test_execute_campaign_creates_failure_reports(tmp_path, monkeypatch)`
- Mock subprocess to fail with fake stderr
- Execute campaign
- Assert file exists: `campaign_dir / "failures" / "{run_id}_failure_report.json"`
- Load JSON and verify it contains:
  - `run_id`
  - `failed_at` timestamp
  - `exit_code`
  - `stderr` (stack trace)
  - `config_snapshot`
  - `environment` info

### 30. [ ] Write test for campaign_complete.yaml generation
- In `tests/ai/campaigns/test_runner.py`, add function `test_execute_campaign_creates_completion_summary(tmp_path, monkeypatch)`
- Mock subprocess with mixed success/failure
- Execute campaign
- Assert file exists: `campaign_dir / "campaign_complete.yaml"`
- Load YAML and verify it contains:
  - `campaign_id`
  - `total_runs`
  - `successful`
  - `failed`
  - `total_runtime_seconds`
  - `completed_at` timestamp

### 31. [ ] Implement ExecutionResults model
- In `src/trading_platform/ai/campaigns/models.py`, create class `ExecutionResults(BaseModel)` with fields:
  - `campaign_id: str`
  - `total_runs: int`
  - `successful: int`
  - `failed: int`
  - `execution_log_path: Path`
  - `started_at: str` (ISO timestamp)
  - `completed_at: str` (ISO timestamp)
  - `run_results: List[RunResult]`
- Create class `RunResult(BaseModel)` with fields:
  - `run_id: str`
  - `status: str` (success/failed)
  - `exit_code: int`
  - `stdout: str`
  - `stderr: str`
  - `execution_time_seconds: float`

### 32. [ ] Implement execute_campaign_runs function
- Create the new file: `src/trading_platform/ai/campaigns/runner.py`
- Add module docstring: "Campaign batch execution engine with failure artifact generation."
- Import required modules: `subprocess`, `Path`, `datetime`, `json`, `yaml`, `time`, `sys`, `platform`
- Import `CampaignPlan`, `ExecutionResults`, `RunResult` from `.models`
- Create function `execute_campaign_runs(plan: CampaignPlan, runs_dir: Path, campaign_dir: Path, fail_fast: bool = True, continue_on_error: bool = False) -> ExecutionResults`
- Logic:
  1. Create campaign directory: `campaign_dir.mkdir(parents=True, exist_ok=True)`
  2. Create failures directory: `(campaign_dir / "failures").mkdir(exist_ok=True)`
  3. Create execution log file at `campaign_dir / "execution.log"`
  4. Initialize counters: `successful = 0`, `failed = 0`
  5. Record `started_at` timestamp
  6. Initialize `run_results = []`
  7. For each run_config in `plan.run_configs`:
     - Write temporary RunConfig YAML to `campaign_dir / "temp_run_config.yaml"`
     - Build command: `["poetry", "run", "tp", "run-backtest", "--config", str(temp_config_path), "--user", f"campaigns/{plan.campaign_id}"]`
     - Record start time
     - Execute via `subprocess.run(cmd, capture_output=True, text=True)`
     - Record end time, calculate duration
     - Check return code:
       - If 0: increment `successful`, status = "success"
       - If != 0:
         - Increment `failed`, status = "failed"
         - Create failure report: `{run_id}_failure_report.json` with:
           - `run_id`
           - `failed_at`: current timestamp
           - `exit_code`: returncode
           - `stderr`: process stderr
           - `stdout`: process stdout
           - `config_snapshot`: run_config dict
           - `environment`: dict with python_version, platform, git_commit
         - Save to `failures/` directory
     - Create `RunResult` with status, exit_code, stdout, stderr, duration
     - Append to `run_results`
     - Write log entry to execution.log with timestamp, run_id, status
     - If failed and `fail_fast=True`: break loop
     - If failed and `continue_on_error=False` and not `fail_fast`: raise RuntimeError
  8. Record `completed_at` timestamp
  9. Calculate total runtime
  10. Create `campaign_complete.yaml` with summary
  11. Save to `campaign_dir / "campaign_complete.yaml"`
  12. Create and return `ExecutionResults`

### 33. [ ] Update campaigns __init__.py with runner exports
- In `src/trading_platform/ai/campaigns/__init__.py`, add:
  - `from .runner import execute_campaign_runs`

### 34. [ ] Run tests for Phase 3
- Execute: `poetry run pytest tests/ai/campaigns/test_runner.py -v`
- Assert all 9 tests pass
- Execute: `poetry run pytest tests/ai/campaigns/test_runner.py --cov=src/trading_platform/ai/campaigns/runner --cov-report=term-missing`
- Assert 100% coverage for `runner.py`

---

## Phase 4: Artifact Collection with Prescribed Folder Structure

### 35. [ ] Create test module for artifact collector
- Create the new file: `tests/ai/campaigns/test_collector.py`
- Import `pytest`, `json`, `Path`, `tmp_path`
- This file tests campaign artifact organization using `data/candidates/<campaign_id>/` structure

### 36. [ ] Write test for collecting artifacts to candidates folder
- In `tests/ai/campaigns/test_collector.py`, add function `test_collect_artifacts_uses_prescribed_structure(tmp_path)`
- Create fake run directory: `tmp_path / "runs" / "campaigns" / "test_campaign" / "run_001" / "brief.json"`
- Create minimal brief.json with mock data including `strategy_archetype` and `execution_timeframe` in meta
- Import not-yet-created `collect_campaign_artifacts` from `trading_platform.ai.campaigns.collector`
- Call `summary = collect_campaign_artifacts("test_campaign", runs_dir=tmp_path / "runs")`
- Assert candidates directory created at: `data/candidates/test_campaign/run_001/`
- Assert brief.json copied to candidates folder
- Assert `summary.total_candidates == 1`
- Assert `summary.candidates_dir == Path("data/candidates/test_campaign")`

### 37. [ ] Write test for collecting artifacts from multiple runs
- In `tests/ai/campaigns/test_collector.py`, add function `test_collect_artifacts_multiple_runs(tmp_path)`
- Create 3 fake run directories with brief.json files
- Collect artifacts
- Assert all 3 briefs copied to `data/candidates/test_campaign/` with separate subdirectories
- Assert `summary.total_candidates == 3`

### 38. [ ] Write test for extracting metadata from brief
- In `tests/ai/campaigns/test_collector.py`, add function `test_collect_artifacts_extracts_metadata(tmp_path)`
- Create brief.json with specific metrics: `total_pnl: 1000`, `sharpe_ratio: 1.5`, `win_rate: 0.6`
- Include `strategy_archetype: "trend_following"` and `execution_timeframe: "15m"` in brief meta
- Collect artifacts
- Assert metadata.json created in candidate folder: `data/candidates/test_campaign/run_001/metadata.json`
- Load metadata.json and verify metrics match
- Verify `strategy_archetype` and `execution_timeframe` are captured

### 39. [ ] Write test for creating candidates index
- In `tests/ai/campaigns/test_collector.py`, add function `test_collect_artifacts_creates_index(tmp_path)`
- Create 2 runs with different metrics
- Collect artifacts
- Assert file exists: `data/candidates/test_campaign/index.json`
- Load index and verify it contains array of 2 candidates with metadata

### 40. [ ] Write test for handling missing brief.json
- In `tests/ai/campaigns/test_collector.py`, add function `test_collect_artifacts_skips_missing_brief(tmp_path)`
- Create run directory without brief.json
- Collect artifacts
- Assert no candidate created for that run
- Assert warning logged (use `caplog` fixture)

### 41. [ ] Implement ArtifactSummary model
- In `src/trading_platform/ai/campaigns/models.py`, create class `CandidateMetadata(BaseModel)` with fields:
  - `run_id: str`
  - `strategy_archetype: str`
  - `execution_timeframe: str`
  - `total_pnl: float`
  - `sharpe_ratio: Optional[float]`
  - `win_rate: float`
  - `total_trades: int`
  - `max_drawdown: float`
- Create class `ArtifactSummary(BaseModel)` with fields:
  - `campaign_id: str`
  - `total_candidates: int`
  - `candidates_dir: Path` (always `data/candidates/<campaign_id>`)
  - `collected_at: str` (ISO timestamp)
  - `candidates: List[CandidateMetadata]`

### 42. [ ] Implement collect_campaign_artifacts function
- Create the new file: `src/trading_platform/ai/campaigns/collector.py`
- Add module docstring: "Campaign artifact collection using prescribed data/candidates/ structure."
- Import required modules: `Path`, `json`, `shutil`, `datetime`, `logging`
- Import `ArtifactSummary`, `CandidateMetadata` from `.models`
- Import `paths` from `trading_platform.core`
- Create function `collect_campaign_artifacts(campaign_id: str, runs_dir: Path) -> ArtifactSummary`
- Logic:
  1. Define candidates directory: `candidates_dir = paths.PROJECT_ROOT / "data" / "candidates" / campaign_id`
  2. Create candidates directory: `candidates_dir.mkdir(parents=True, exist_ok=True)`
  3. Find all run directories: `runs_dir / "campaigns" / campaign_id / *`
  4. Initialize `candidates = []`
  5. For each run directory:
     - Check if `brief.json` exists, skip if not (log warning)
     - Load brief.json
     - Extract run_id from directory name
     - Extract metadata from brief:
       - `strategy_archetype` from `meta.strategy_archetype` (or `instrument_definitions`)
       - `execution_timeframe` from `meta.execution_timeframe` (or infer from data)
       - `total_pnl` from `backtest_metrics.total_pnl`
       - `sharpe_ratio` from `backtest_metrics.sharpe_ratio`
       - `win_rate` from `backtest_metrics.win_rate`
       - `total_trades` from `len(trades)`
       - `max_drawdown` from `backtest_metrics.max_drawdown`
     - Create candidate directory: `candidates_dir / run_id`
     - Copy `brief.json` to candidate directory
     - Create `CandidateMetadata` object
     - Save metadata.json in candidate directory
     - Append to `candidates` list
  6. Create index.json: save candidates list to `candidates_dir / "index.json"`
  7. Create and return `ArtifactSummary`

### 43. [ ] Update campaigns __init__.py with collector exports
- In `src/trading_platform/ai/campaigns/__init__.py`, add:
  - `from .collector import collect_campaign_artifacts`

### 44. [ ] Run tests for Phase 4
- Execute: `poetry run pytest tests/ai/campaigns/test_collector.py -v`
- Assert all 6 tests pass
- Execute: `poetry run pytest tests/ai/campaigns/test_collector.py --cov=src/trading_platform/ai/campaigns/collector --cov-report=term-missing`
- Assert 100% coverage for `collector.py`

---

## Phase 5: Validation with Complete Quality Gates

### 45. [ ] Create test module for campaign validator
- Create the new file: `tests/ai/campaigns/test_validator.py`
- Import `pytest`, `json`, `Path`, `pandas`
- This file tests automated validation with all quality gates

### 46. [ ] Write test for validating brief schema
- In `tests/ai/campaigns/test_validator.py`, add function `test_validate_candidates_checks_schema(tmp_path)`
- Create candidates directory at `data/candidates/test_campaign/run_001/` with valid brief.json
- Import not-yet-created `validate_campaign_candidates` from `trading_platform.ai.campaigns.validator`
- Call `report = validate_campaign_candidates("test_campaign")`
- Assert `report.total_candidates == 1`
- Assert `report.passed == 1`
- Assert first candidate has check result for "schema_validation" with status "passed"

### 47. [ ] Write test for detecting invalid brief schema
- In `tests/ai/campaigns/test_validator.py`, add function `test_validate_candidates_detects_invalid_schema(tmp_path)`
- Create brief.json missing required field (e.g., no "trades" array)
- Validate candidates
- Assert `report.failed == 1`
- Assert validation report contains issue description

### 48. [ ] Write test for data quality checks
- In `tests/ai/campaigns/test_validator.py`, add function `test_validate_candidates_checks_data_quality(tmp_path)`
- Create brief.json with data quality flags: `has_nans: true`
- Validate candidates
- Assert check result for "data_quality" has status "warning"
- Assert issue message mentions NaN values

### 49. [ ] Write test for minimum trades check
- In `tests/ai/campaigns/test_validator.py`, add function `test_validate_candidates_checks_min_trades(tmp_path)`
- Create brief.json with only 2 trades (below threshold of 5)
- Validate candidates
- Assert check result for "min_trades" has status "failed"
- Assert issue mentions insufficient trades

### 50. [ ] Write test for duplicate trade_id detection
- In `tests/ai/campaigns/test_validator.py`, add function `test_validate_candidates_detects_duplicate_trade_ids(tmp_path)`
- Create brief.json with duplicate trade IDs in trades array
- Validate candidates
- Assert check result for "duplicate_detection" has status "failed"
- Assert issue mentions duplicate trade IDs

### 51. [ ] Write test for indicator registry validation
- In `tests/ai/campaigns/test_validator.py`, add function `test_validate_candidates_checks_indicator_registry(tmp_path, monkeypatch)`
- Create brief.json with contextual features
- Mock indicator registry to return list of valid indicators
- Add an invalid indicator to features
- Validate candidates
- Assert check result for "indicator_registry" has status "failed"
- Assert issue mentions unregistered indicator

### 52. [ ] Write test for drift monitoring check
- In `tests/ai/campaigns/test_validator.py`, add function `test_validate_candidates_computes_drift_stats(tmp_path)`
- Create baseline master_trade_log.parquet at `data/dvc/processed/training_sets/master_trade_log.parquet` with 100 trades
- Create candidate brief.json with 20 trades having significantly different `r_multiple` distribution (mean shifted by 2 std devs)
- Validate candidates
- Assert check result for "drift_monitoring" exists
- Assert KS-statistic computed and included in message
- If KS > 0.15, assert status "warning" with drift alert message

### 53. [ ] Write test for validation report file creation
- In `tests/ai/campaigns/test_validator.py`, add function `test_validate_candidates_saves_report(tmp_path)`
- Validate candidates
- Assert file exists: `data/candidates/test_campaign/validation_report.json`
- Load JSON and verify structure matches ValidationReport schema

### 54. [ ] Write test for audit log update
- In `tests/ai/campaigns/test_validator.py`, add function `test_validate_candidates_updates_audit_log(tmp_path, monkeypatch)`
- Mock file append operations
- Validate candidates
- Assert audit log entry created in `docs/ai/logs/campaign_audit.md`
- Verify entry contains: timestamp, campaign_id, validation status

### 55. [ ] Implement ValidationReport model
- In `src/trading_platform/ai/campaigns/models.py`, create class `CheckResult(BaseModel)` with fields:
  - `check_name: str`
  - `status: str` (passed/failed/warning)
  - `message: Optional[str]`
- Create class `CandidateValidation(BaseModel)` with fields:
  - `run_id: str`
  - `overall_status: str` (passed/failed/warning)
  - `checks: Dict[str, CheckResult]`
  - `issues: List[str]`
- Create class `ValidationReport(BaseModel)` with fields:
  - `campaign_id: str`
  - `validated_at: str` (ISO timestamp)
  - `total_candidates: int`
  - `passed: int`
  - `failed: int`
  - `warnings: int`
  - `results: List[CandidateValidation]`

### 56. [ ] Implement validate_campaign_candidates function
- Create the new file: `src/trading_platform/ai/campaigns/validator.py`
- Add module docstring: "Campaign candidate validation with complete quality gates."
- Import required modules: `Path`, `json`, `datetime`, `logging`, `pandas`
- Import `scipy.stats.ks_2samp` for drift monitoring
- Import `ValidationReport`, `CandidateValidation`, `CheckResult` from `.models`
- Import `paths` from `trading_platform.core`
- Import `extract_trades_from_brief` from `trading_platform.ai.feature_engineering.trade_extractor`
- Import `get_all_indicators` from `trading_platform.strategy.indicators_registry` (or similar)
- Create function `validate_campaign_candidates(campaign_id: str) -> ValidationReport`
- Logic:
  1. Define candidates_dir: `paths.PROJECT_ROOT / "data" / "candidates" / campaign_id`
  2. Find all candidate directories
  3. Load baseline for drift monitoring (if exists): `master_log_path = paths.PROJECT_ROOT / "data" / "dvc" / "processed" / "training_sets" / "master_trade_log.parquet"`
  4. Initialize counters: `passed = 0`, `failed = 0`, `warnings = 0`
  5. Initialize `results = []`
  6. For each candidate directory:
     - Load brief.json
     - Initialize `checks = {}`
     - Run validation checks:
       - **Schema check**: verify required fields exist (meta, trades, backtest_metrics)
       - **Data quality check**: check `data_quality.has_nans`, `duplicate_bars_count`
       - **Min trades check**: verify `len(trades) >= 5`
       - **Max drawdown check**: verify `max_drawdown < 0.5` (50%)
       - **Duplicate detection**: check for duplicate trade IDs within brief
       - **Indicator registry check**: verify all features in contextual_features are registered
       - **Feature completeness**: check if trades have `context_at_entry` and `context_at_exit`
       - **Drift monitoring** (NEW): if master log exists:
         - Extract candidate trades using `extract_trades_from_brief(brief_data)`
         - Compute KS-statistic for `r_multiple` field vs baseline
         - `ks_stat = ks_2samp(baseline["r_multiple"], candidate["r_multiple"]).statistic`
         - If `ks_stat > 0.15`: status "warning", message "DRIFT DETECTED: KS={ks_stat:.3f}"
         - Else: status "passed", message "KS={ks_stat:.3f}"
     - For each check, create `CheckResult` with status and message
     - Determine overall status (failed if any check failed, warning if any warnings, else passed)
     - Collect issues list from failed checks
     - Create `CandidateValidation` object
     - Append to `results`
     - Update counters
  7. Create `ValidationReport`
  8. Save report to `candidates_dir / "validation_report.json"`
  9. Update audit log: append entry to `docs/ai/logs/campaign_audit.md` with:
     - Timestamp
     - Campaign ID
     - Action: "validation"
     - Summary: passed/failed/warnings counts
  10. Return report

### 57. [ ] Update campaigns __init__.py with validator exports
- In `src/trading_platform/ai/campaigns/__init__.py`, add:
  - `from .validator import validate_campaign_candidates`

### 58. [ ] Run tests for Phase 5
- Execute: `poetry run pytest tests/ai/campaigns/test_validator.py -v`
- Assert all 10 tests pass (added drift monitoring test)
- Execute: `poetry run pytest tests/ai/campaigns/test_validator.py --cov=src/trading_platform/ai/campaigns/validator --cov-report=term-missing`
- Assert 100% coverage for `validator.py`

---

## Phase 6: Manual Review Workflow with Three Decision States

### 58. [ ] Create test module for review workflow
- Create the new file: `tests/ai/campaigns/test_review.py`
- Import `pytest`, `yaml`, `Path`
- This file tests the manual review and approval workflow with all three decision states

### 59. [ ] Write test for generating review report
- In `tests/ai/campaigns/test_review.py`, add function `test_generate_review_report_creates_markdown(tmp_path)`
- Create candidates index at `data/candidates/test_campaign/index.json` with 5 candidates having different metrics
- Import not-yet-created `generate_review_report` from `trading_platform.ai.campaigns.review`
- Call `report_path = generate_review_report("test_campaign")`
- Assert file exists at `data/candidates/test_campaign/review_report.md`
- Read markdown and verify it contains "Top Performers" section

### 60. [ ] Write test for approving candidate
- In `tests/ai/campaigns/test_review.py`, add function `test_approve_candidate_updates_campaign_decision_yaml(tmp_path)`
- Import not-yet-created `approve_candidate` from `trading_platform.ai.campaigns.review`
- Call `approve_candidate(campaign_id="test", run_id="run_001", notes="Good metrics")`
- Assert decision.yaml created at `data/candidates/test/decision.yaml` (CAMPAIGN-LEVEL, not per-run)
- Load YAML and verify structure:
  - `campaign_id: "test"`
  - `reviewed_by` present
  - `reviewed_at` timestamp present
  - `decisions` list contains one entry:
    - `run_id: "run_001"`
    - `status: "approved"`
    - `notes: "Good metrics"`

### 61. [ ] Write test for rejecting candidate
- In `tests/ai/campaigns/test_review.py`, add function `test_reject_candidate_appends_to_campaign_decision_yaml(tmp_path)`
- Import `reject_candidate`
- Call `reject_candidate(campaign_id="test", run_id="run_002", reason="High drawdown")`
- Load decision.yaml from `data/candidates/test/decision.yaml` (CAMPAIGN-LEVEL)
- Verify `decisions` list contains entry for run_002:
  - `run_id: "run_002"`
  - `status: "rejected"`
  - `reason: "High drawdown"`

### 62. [ ] Write test for needs-rework decision
- In `tests/ai/campaigns/test_review.py`, add function `test_needs_rework_candidate_appends_to_campaign_decision_yaml(tmp_path)`
- Import not-yet-created `mark_needs_rework`
- Call `mark_needs_rework(campaign_id="test", run_id="run_003", reason="Adjust parameters", suggestions="Increase stop loss")`
- Load decision.yaml from `data/candidates/test/decision.yaml` (CAMPAIGN-LEVEL)
- Verify `decisions` list contains entry for run_003:
  - `run_id: "run_003"`
  - `status: "needs-rework"`
  - `reason: "Adjust parameters"`
  - `suggestions: "Increase stop loss"`

### 63. [ ] Write test for listing approved candidates
- In `tests/ai/campaigns/test_review.py`, add function `test_get_approved_candidates_filters_correctly(tmp_path)`
- Create campaign-level decision.yaml at `data/candidates/test/decision.yaml` with 3 decisions: 2 approved, 1 rejected
- Import not-yet-created `get_approved_candidates`
- Call `approved = get_approved_candidates("test")`
- Assert `len(approved) == 2`
- Assert only approved run_ids in list

### 64. [ ] Write test for listing needs-rework candidates
- In `tests/ai/campaigns/test_review.py`, add function `test_get_needs_rework_candidates_filters_correctly(tmp_path)`
- Create candidates with mixed statuses including "needs-rework"
- Import `get_needs_rework_candidates`
- Call `needs_rework = get_needs_rework_candidates("test")`
- Assert only needs-rework run_ids returned

### 65. [ ] Implement generate_review_report function
- Create the new file: `src/trading_platform/ai/campaigns/review.py`
- Add module docstring: "Campaign review and approval workflow with three decision states."
- Import required modules: `Path`, `yaml`, `json`, `datetime`
- Import `paths` from `trading_platform.core`
- Create function `generate_review_report(campaign_id: str) -> Path`
- Logic:
  1. Define candidates_dir: `paths.PROJECT_ROOT / "data" / "candidates" / campaign_id`
  2. Load candidates from `candidates_dir / "index.json"`
  3. Sort by Sharpe ratio descending
  4. Select top 10 performers
  5. Sort by Sharpe ratio ascending
  6. Select bottom 5 performers
  7. Build markdown report with sections:
     - Campaign summary
     - Top 10 performers table (run_id, PnL, Sharpe, Win Rate, Trades)
     - Bottom 5 performers table
     - Review instructions (explain three decision states)
  8. Save to `candidates_dir / "review_report.md"`
  9. Return path

### 66. [ ] Implement approve_candidate function
- In `src/trading_platform/ai/campaigns/review.py`, create function `approve_candidate(campaign_id: str, run_id: str, notes: str, reviewer: str = "user") -> None`
- Logic:
  1. Define decision_path: `paths.PROJECT_ROOT / "data" / "candidates" / campaign_id / "decision.yaml"` (CAMPAIGN-LEVEL)
  2. Load existing decision.yaml if exists, else create new dict with:
     - `campaign_id`
     - `reviewed_by: reviewer`
     - `reviewed_at: datetime.now(datetime.UTC).isoformat()`
     - `decisions: []` (empty list)
  3. Append new decision to `decisions` list:
     - `run_id`
     - `status: "approved"`
     - `notes`
  4. Save to decision.yaml

### 67. [ ] Implement reject_candidate function
- In `src/trading_platform/ai/campaigns/review.py`, create function `reject_candidate(campaign_id: str, run_id: str, reason: str, reviewer: str = "user") -> None`
- Same logic as approve but append decision with `status: "rejected"` and `reason` instead of `notes` to campaign-level decision.yaml

### 68. [ ] Implement mark_needs_rework function
- In `src/trading_platform/ai/campaigns/review.py`, create function `mark_needs_rework(campaign_id: str, run_id: str, reason: str, suggestions: str, reviewer: str = "user") -> None`
- Same logic as approve but append decision with `status: "needs-rework"`, `reason`, `suggestions` to campaign-level decision.yaml

### 69. [ ] Implement get_approved_candidates function
- In `src/trading_platform/ai/campaigns/review.py`, create function `get_approved_candidates(campaign_id: str) -> List[str]`
- Logic:
  1. Load campaign-level decision.yaml from `data/candidates/<campaign_id>/decision.yaml`
  2. Parse `decisions` list
  3. Filter where `status == "approved"`
  4. Return list of run_ids

### 70. [ ] Implement get_needs_rework_candidates function
- In `src/trading_platform/ai/campaigns/review.py`, create function `get_needs_rework_candidates(campaign_id: str) -> List[str]`
- Same logic as get_approved but filter for `status == "needs-rework"` from campaign-level decision.yaml

### 71. [ ] Update campaigns __init__.py with review exports
- In `src/trading_platform/ai/campaigns/__init__.py`, add:
  - `from .review import generate_review_report, approve_candidate, reject_candidate, mark_needs_rework, get_approved_candidates, get_needs_rework_candidates`

### 72. [ ] Run tests for Phase 6
- Execute: `poetry run pytest tests/ai/campaigns/test_review.py -v`
- Assert all 7 tests pass
- Execute: `poetry run pytest tests/ai/campaigns/test_review.py --cov=src/trading_platform/ai/campaigns/review --cov-report=term-missing`
- Assert 100% coverage for `review.py`

---

## Phase 7: Enrichment Stage (NEW - Missing from Original Plan)

### 73. [ ] Create test module for enrichment
- Create the new file: `tests/ai/campaigns/test_enrichment.py`
- Import `pytest`, `pandas`, `Path`, `json`
- This file tests the enrichment stage that creates intermediate dataset

### 74. [ ] Write test for enriching approved candidates
- In `tests/ai/campaigns/test_enrichment.py`, add function `test_enrich_approved_candidates_only(tmp_path)`
- Create 3 candidate directories: 2 approved, 1 rejected
- Each has brief.json with trades
- Import not-yet-created `enrich_campaign_dataset` from `trading_platform.ai.campaigns.enrichment`
- Call `result = enrich_campaign_dataset("test")`
- Assert output file created: `data/enriched/test/rich_trades.parquet`
- Load parquet and verify only 2 approved candidates' trades present

### 75. [ ] Write test for enrichment using ai-curate-data
- In `tests/ai/campaigns/test_enrichment.py`, add function `test_enrich_uses_ai_curate_data(tmp_path, monkeypatch)`
- Mock `subprocess.run` to capture ai-curate-data invocation
- Enrich campaign
- Assert subprocess called with correct args:
  - `["poetry", "run", "tp", "ai-curate-data", "--source-dir", "...", "--output-file", "..."]`

### 76. [ ] Write test for enrichment with campaign metadata
- In `tests/ai/campaigns/test_enrichment.py`, add function `test_enrichment_adds_campaign_metadata(tmp_path)`
- Enrich campaign
- Load output parquet
- Assert columns exist: `campaign_id`, `strategy_archetype`, `execution_timeframe`, `run_id`

### 77. [ ] Write test for enrichment summary
- In `tests/ai/campaigns/test_enrichment.py`, add function `test_enrichment_returns_summary(tmp_path)`
- Enrich campaign
- Assert result contains:
  - `campaign_id`
  - `approved_candidates` count
  - `total_trades_enriched`
  - `output_path`

### 78. [ ] Implement EnrichmentResult model
- In `src/trading_platform/ai/campaigns/models.py`, create class `EnrichmentResult(BaseModel)` with fields:
  - `campaign_id: str`
  - `approved_candidates: int`
  - `total_trades_enriched: int`
  - `output_path: Path`
  - `enriched_at: str` (ISO timestamp)

### 79. [ ] Implement enrich_campaign_dataset function
- Create the new file: `src/trading_platform/ai/campaigns/enrichment.py`
- Add module docstring: "Campaign enrichment stage - creates intermediate rich trades dataset."
- Import required modules: `subprocess`, `Path`, `json`, `datetime`, `pandas`
- Import `get_approved_candidates` from `.review`
- Import `EnrichmentResult` from `.models`
- Import `paths` from `trading_platform.core`
- Create function `enrich_campaign_dataset(campaign_id: str) -> EnrichmentResult`
- Logic:
  1. Get approved candidates using `get_approved_candidates(campaign_id)`
  2. Define candidates_dir: `paths.PROJECT_ROOT / "data" / "candidates" / campaign_id`
  3. Define output_dir: `paths.PROJECT_ROOT / "data" / "enriched" / campaign_id`
  4. Create output directory: `output_dir.mkdir(parents=True, exist_ok=True)`
  5. Define output_path: `output_dir / "rich_trades.parquet"`
  6. Create temporary directory for approved briefs only
  7. Copy only approved candidate briefs to temp directory
  8. Build command: `["poetry", "run", "tp", "ai-curate-data", "--source-dir", str(temp_dir), "--output-file", str(output_path)]`
  9. Execute via subprocess
  10. Load enriched parquet
  11. Add campaign metadata columns:
      - For each candidate, read brief to get `strategy_archetype`, `execution_timeframe`
      - Add `campaign_id`, `run_id` to all rows
  12. Save updated parquet
  13. Create and return `EnrichmentResult`

### 80. [ ] Update campaigns __init__.py with enrichment exports
- In `src/trading_platform/ai/campaigns/__init__.py`, add:
  - `from .enrichment import enrich_campaign_dataset`

### 81. [ ] Run tests for Phase 7
- Execute: `poetry run pytest tests/ai/campaigns/test_enrichment.py -v`
- Assert all 5 tests pass
- Execute: `poetry run pytest tests/ai/campaigns/test_enrichment.py --cov=src/trading_platform/ai/campaigns/enrichment --cov-report=term-missing`
- Assert 100% coverage for `enrichment.py`

---

## Phase 8: Publishing with Full Audit Trail

### 82. [ ] Create test module for campaign publisher
- Create the new file: `tests/ai/campaigns/test_publisher.py`
- Import `pytest`, `pandas`, `Path`, `hashlib`
- This file tests publishing from enriched dataset to master trade log

### 83. [ ] Write test for publishing from enriched dataset
- In `tests/ai/campaigns/test_publisher.py`, add function `test_publish_reads_from_enriched(tmp_path)`
- Create enriched dataset at `data/enriched/test/rich_trades.parquet`
- Import not-yet-created `publish_campaign_dataset` from `trading_platform.ai.campaigns.publisher`
- Call `result = publish_campaign_dataset("test")`
- Assert publisher read from enriched folder, not candidates folder

### 84. [ ] Write test for appending to master trade log
- In `tests/ai/campaigns/test_publisher.py`, add function `test_publish_appends_to_master_log(tmp_path)`
- Create existing master_trade_log.parquet with 10 trades
- Create enriched dataset with 5 trades
- Publish
- Load master log
- Assert total rows = 15

### 85. [ ] Write test for generating checksum
- In `tests/ai/campaigns/test_publisher.py`, add function `test_publish_generates_checksum(tmp_path)`
- Publish dataset
- Assert result contains `sha256_checksum` field
- Verify checksum is valid hex string of length 64
- Recalculate checksum manually and verify it matches

### 86. [ ] Write test for updating curation history
- In `tests/ai/campaigns/test_publisher.py`, add function `test_publish_updates_curation_history(tmp_path, monkeypatch)`
- Mock file operations to capture history update
- Publish dataset
- Assert `docs/ai/data_curation_history.md` updated with entry containing:
  - Timestamp
  - Campaign ID
  - Number of trades
  - Checksum
  - Actor

### 87. [ ] Write test for updating audit log
- In `tests/ai/campaigns/test_publisher.py`, add function `test_publish_updates_audit_log(tmp_path, monkeypatch)`
- Publish dataset
- Assert `docs/ai/logs/campaign_audit.md` updated with publish action

### 88. [ ] Write test for automated DVC tracking
- In `tests/ai/campaigns/test_publisher.py`, add function `test_publish_executes_dvc_tracking(tmp_path, monkeypatch)`
- Mock subprocess to capture DVC commands
- Publish dataset
- Assert subprocess called with `["dvc", "add", str(master_log_path)]`
- Assert subprocess called with `["dvc", "push"]`
- Assert result contains `dvc_tracking_updated=True`

### 89. [ ] Implement PublishResult model
- In `src/trading_platform/ai/campaigns/models.py`, create class `PublishResult(BaseModel)` with fields:
  - `campaign_id: str`
  - `total_trades_published: int`
  - `output_path: Path`
  - `sha256_checksum: str`
  - `published_at: str` (ISO timestamp)
  - `master_log_updated: bool`
  - `dvc_tracking_updated: bool` (changed from "required" - now actually executes DVC commands)

### 90. [ ] Implement publish_campaign_dataset function
- Create the new file: `src/trading_platform/ai/campaigns/publisher.py`
- Add module docstring: "Campaign dataset publishing from enriched stage to master trade log with automated DVC tracking."
- Import required modules: `Path`, `pandas`, `hashlib`, `datetime`, `subprocess`
- Import `PublishResult` from `.models`
- Import `paths` from `trading_platform.core`
- Create function `publish_campaign_dataset(campaign_id: str) -> PublishResult`
- Logic:
  1. Define enriched_path: `paths.PROJECT_ROOT / "data" / "enriched" / campaign_id / "rich_trades.parquet"`
  2. Verify enriched dataset exists
  3. Load enriched parquet
  4. Define output_dir: `paths.PROJECT_ROOT / "data" / "dvc" / "processed" / "training_sets"`
  5. Define master_log_path: `output_dir / "master_trade_log.parquet"`
  6. Check if master log exists:
     - If exists: load, append enriched data, save
     - If not: save enriched data as master log
  7. Calculate SHA256 checksum of master log file
  8. **AUTOMATED DVC TRACKING** (was manual, now automated per guide Section 5.2 lines 128-129):
     - Execute: `subprocess.run(["dvc", "add", str(master_log_path)], check=True)`
     - Execute: `subprocess.run(["dvc", "push"], check=True)`
     - Set `dvc_tracking_updated = True`
  9. Update curation history:
     - Append entry to `docs/ai/data_curation_history.md` with:
       - Timestamp
       - Campaign ID
       - Total trades added
       - Checksum
       - Actor (e.g., "campaign-runner")
  10. Update audit log:
     - Append entry to `docs/ai/logs/campaign_audit.md` with publish action
  11. Create and return `PublishResult` with `dvc_tracking_updated=True`

### 91. [ ] Update campaigns __init__.py with publisher exports
- In `src/trading_platform/ai/campaigns/__init__.py`, add:
  - `from .publisher import publish_campaign_dataset`

### 92. [ ] Run tests for Phase 8
- Execute: `poetry run pytest tests/ai/campaigns/test_publisher.py -v`
- Assert all 7 tests pass
- Execute: `poetry run pytest tests/ai/campaigns/test_publisher.py --cov=src/trading_platform/ai/campaigns/publisher --cov-report=term-missing`
- Assert 100% coverage for `publisher.py`

---

## Phase 9: CLI Commands

### 93. [ ] Write test for campaign-plan CLI command
- In `tests/cli/test_cli.py`, add function `test_cmd_campaign_plan(tmp_path, monkeypatch)`
- Mock `generate_campaign_plan` to return fake plan
- Create minimal campaign YAML file
- Build args: `["campaign-plan", "--config", str(yaml_path)]`
- Call CLI main function
- Assert mocked function was called with correct arguments
- Assert exit code 0

### 94. [ ] Write test for campaign-run CLI command
- In `tests/cli/test_cli.py`, add function `test_cmd_campaign_run(tmp_path, monkeypatch)`
- Mock `execute_campaign_runs`
- Create plan.json file
- Build args: `["campaign-run", "--campaign-id", "test"]`
- Call CLI main
- Assert mocked function called
- Assert exit code 0

### 95. [ ] Write test for campaign-validate CLI command
- In `tests/cli/test_cli.py`, add function `test_cmd_campaign_validate(monkeypatch)`
- Mock `validate_campaign_candidates`
- Build args: `["campaign-validate", "--campaign-id", "test"]`
- Assert validation called

### 96. [ ] Write test for campaign-review CLI command
- In `tests/cli/test_cli.py`, add function `test_cmd_campaign_review(monkeypatch)`
- Mock `generate_review_report`
- Build args: `["campaign-review", "--campaign-id", "test"]`
- Assert review report generated

### 97. [ ] Write test for campaign-approve CLI command
- In `tests/cli/test_cli.py`, add function `test_cmd_campaign_approve(monkeypatch)`
- Mock `approve_candidate`
- Build args: `["campaign-approve", "--campaign-id", "test", "--run-id", "run_001", "--notes", "Good"]`
- Assert approve called with correct args

### 98. [ ] Write test for campaign-needs-rework CLI command
- In `tests/cli/test_cli.py`, add function `test_cmd_campaign_needs_rework(monkeypatch)`
- Mock `mark_needs_rework`
- Build args: `["campaign-needs-rework", "--campaign-id", "test", "--run-id", "run_002", "--reason", "Tweak params", "--suggestions", "Lower stop"]`
- Assert needs-rework called

### 99. [ ] Write test for campaign-enrich CLI command
- In `tests/cli/test_cli.py`, add function `test_cmd_campaign_enrich(monkeypatch)`
- Mock `enrich_campaign_dataset`
- Build args: `["campaign-enrich", "--campaign-id", "test"]`
- Assert enrich called

### 100. [ ] Write test for campaign-publish CLI command
- In `tests/cli/test_cli.py`, add function `test_cmd_campaign_publish(monkeypatch)`
- Mock `publish_campaign_dataset`
- Build args: `["campaign-publish", "--campaign-id", "test"]`
- Assert publish called

### 101. [ ] Implement cmd_campaign_plan function
- In `src/trading_platform/cli.py`, import:
  - `from trading_platform.ai.campaigns import generate_campaign_plan, CampaignConfig`
- Add function `cmd_campaign_plan(args: argparse.Namespace) -> int`
- Logic:
  1. Load campaign YAML from `args.config`
  2. Validate as `CampaignConfig`
  3. Determine output_dir: `paths.PROJECT_ROOT / "data" / "campaigns" / {campaign_id}`
  4. Call `generate_campaign_plan(campaign, output_dir)`
  5. Print: "Campaign plan created: {plan_path}"
  6. Print provenance summary
  7. Return 0

### 102. [ ] Implement cmd_campaign_run function
- In `src/trading_platform/cli.py`, import `execute_campaign_runs`, `CampaignPlan`
- Add function `cmd_campaign_run(args: argparse.Namespace) -> int`
- Logic:
  1. Load plan from `data/campaigns/{campaign_id}/plan.json`
  2. Parse as `CampaignPlan`
  3. Define runs_dir and campaign_dir
  4. Call `execute_campaign_runs(plan, runs_dir, campaign_dir, fail_fast=args.fail_fast, continue_on_error=args.continue_on_error)`
  5. Print execution summary
  6. Return 0 if all successful, else 1

### 103. [ ] Implement cmd_campaign_validate function
- In `src/trading_platform/cli.py`, import `validate_campaign_candidates`
- Add function `cmd_campaign_validate(args: argparse.Namespace) -> int`
- Logic:
  1. Call `validate_campaign_candidates(args.campaign_id)`
  2. Print validation summary
  3. Return 0

### 104. [ ] Implement cmd_campaign_review function
- In `src/trading_platform/cli.py`, import `generate_review_report`
- Add function `cmd_campaign_review(args: argparse.Namespace) -> int`
- Call review report generator and print path

### 105. [ ] Implement cmd_campaign_approve function
- In `src/trading_platform/cli.py`, import `approve_candidate`
- Add function `cmd_campaign_approve(args: argparse.Namespace) -> int`
- Call approve with args from command line

### 106. [ ] Implement cmd_campaign_reject function
- In `src/trading_platform/cli.py`, import `reject_candidate`
- Add function `cmd_campaign_reject(args: argparse.Namespace) -> int`
- Call reject with args from command line

### 107. [ ] Implement cmd_campaign_needs_rework function
- In `src/trading_platform/cli.py`, import `mark_needs_rework`
- Add function `cmd_campaign_needs_rework(args: argparse.Namespace) -> int`
- Call mark_needs_rework with args from command line

### 108. [ ] Implement cmd_campaign_enrich function
- In `src/trading_platform/cli.py`, import `enrich_campaign_dataset`
- Add function `cmd_campaign_enrich(args: argparse.Namespace) -> int`
- Call enrich and print result summary

### 109. [ ] Implement cmd_campaign_publish function
- In `src/trading_platform/cli.py`, import `publish_campaign_dataset`
- Add function `cmd_campaign_publish(args: argparse.Namespace) -> int`
- Call publish and print result summary
- Print DVC tracking status: "DVC tracking updated automatically: {result.dvc_tracking_updated}" (no manual reminder needed)

### 110. [ ] Add CLI subparsers for campaign commands
- In `src/trading_platform/cli.py`, in `main()` function, add subparsers:
  - `campaign-plan`: requires `--config`
  - `campaign-run`: requires `--campaign-id`, optional `--fail-fast`, `--continue-on-error`
  - `campaign-validate`: requires `--campaign-id`
  - `campaign-review`: requires `--campaign-id`
  - `campaign-approve`: requires `--campaign-id`, `--run-id`, `--notes`
  - `campaign-reject`: requires `--campaign-id`, `--run-id`, `--reason`
  - `campaign-needs-rework`: requires `--campaign-id`, `--run-id`, `--reason`, `--suggestions`
  - `campaign-enrich`: requires `--campaign-id`
  - `campaign-publish`: requires `--campaign-id`
- Set `func` attribute for each to corresponding cmd function

### 111. [ ] Run CLI tests for campaign commands
- Execute: `poetry run pytest tests/cli/test_cli.py::test_cmd_campaign_plan -v`
- Execute: `poetry run pytest tests/cli/test_cli.py::test_cmd_campaign_run -v`
- Execute: `poetry run pytest tests/cli/test_cli.py::test_cmd_campaign_validate -v`
- Execute: `poetry run pytest tests/cli/test_cli.py::test_cmd_campaign_review -v`
- Execute: `poetry run pytest tests/cli/test_cli.py::test_cmd_campaign_approve -v`
- Execute: `poetry run pytest tests/cli/test_cli.py::test_cmd_campaign_needs_rework -v`
- Execute: `poetry run pytest tests/cli/test_cli.py::test_cmd_campaign_enrich -v`
- Execute: `poetry run pytest tests/cli/test_cli.py::test_cmd_campaign_publish -v`
- Assert all 9 CLI tests pass

---

## Phase 10: Documentation & Examples

### 112. [ ] Create audit log directory and placeholder
- Create directory: `docs/ai/logs/`
- Create file: `docs/ai/logs/campaign_audit.md`
- Add header: `# Campaign Audit Log`
- Add description of log format

### 113. [ ] Create data curation history file
- Create file: `docs/ai/data_curation_history.md` (if doesn't exist)
- Add header: `# Data Curation History`
- Add description and table headers for tracking published datasets

### 114. [ ] Create example campaign YAML for trend following
- Create new file: `config/campaigns/example_trend_following_15m.yaml`
- Content:
  ```yaml
  campaign_id: trend_following_15m_v1
  strategy_path: config/strategy/ema_crossover.yaml
  execution_timeframe: 15m
  strategy_archetype: trend_following
  description: "EMA crossover trend following on 15m timeframe with multi-timeframe context"

  run_matrix:
    - instrument: EURUSD
      start_date: "2023-01-01"
      end_date: "2023-06-30"
      param_overrides:
        fast_length: 10
        slow_length: 20

    - instrument: EURUSD
      start_date: "2023-01-01"
      end_date: "2023-06-30"
      param_overrides:
        fast_length: 12
        slow_length: 25

    - instrument: GBPUSD
      start_date: "2023-01-01"
      end_date: "2023-06-30"
      param_overrides:
        fast_length: 10
        slow_length: 20

  contextual_features:
    - name: 1h_rsi
      type: RSI
      params:
        length: 14
      timeframe: 1h

    - name: 4h_ema_50
      type: EMA
      params:
        length: 50
      timeframe: 4h

    - name: 1d_atr
      type: ATR
      params:
        length: 14
      timeframe: 1D
  ```

### 115. [ ] Create campaign runner user guide
- Create new file: `docs/ai/06_campaign_runner_guide.md`
- Sections:
  1. **Overview** - What is the campaign runner, alignment with Section 6 of data curation guide
  2. **Quick Start** - 5-minute example showing full workflow
  3. **Campaign YAML Anatomy** - Detailed field reference with provenance requirements
  4. **Workflow** - Step-by-step execution flow with all stages
  5. **Quality Gates** - Complete list of validation checks (schema, dedupe, drift, registry)
  6. **Review & Approval** - Three decision states (approved, rejected, needs-rework)
  7. **Enrichment Stage** - How enriched dataset is created
  8. **Publishing** - How data flows to master trade log with audit trail
  9. **Folder Structure** - Prescribed data/candidates/ layout
  10. **CLI Reference** - All campaign commands with examples
  11. **Provenance & Reproducibility** - What metadata is captured
  12. **Troubleshooting** - Common issues and solutions

### 116. [ ] Update main curation guide with implementation reference
- Open `docs/ai/05_ml_data_curation_guide.md`
- Update Section 6 header to: "## 6. Automating Data Generation: The Campaign Runner ✅ IMPLEMENTED"
- Add note at top of section: "**Implementation:** See `docs/ai/06_campaign_runner_guide.md` for complete usage guide and CLI reference."
- Add quick example showing campaign execution workflow
- Link to example YAML files

### 117. [ ] Create campaign runner README in campaigns module
- Create new file: `src/trading_platform/ai/campaigns/README.md`
- Content:
  - Brief module overview
  - List of key components with one-line descriptions
  - Links to main documentation
  - Notes on quality gates and provenance tracking

### 118. [ ] Update CHANGELOG.md
- Add entry under "Unreleased" section:
  ```markdown
  ### Added
  - **Campaign Runner**: Automated backtest orchestration system for ML data generation
    - Campaign YAML configuration with full provenance tracking (`config/campaigns/`)
    - Batch execution engine with progress tracking and failure artifact generation
    - Artifact collection using prescribed `data/candidates/<campaign_id>/` structure
    - Complete validation with quality gates (schema, data quality, dedupe, drift monitoring, indicator registry, audit logging)
    - Manual review workflow with three decision states (approved, rejected, needs-rework)
    - Enrichment stage creating `data/enriched/<campaign_id>/rich_trades.parquet`
    - Publishing to master trade log with full audit trail and DVC tracking
    - CLI commands: `campaign-plan`, `campaign-run`, `campaign-validate`, `campaign-review`, `campaign-approve`, `campaign-reject`, `campaign-needs-rework`, `campaign-enrich`, `campaign-publish`
    - Implements complete Section 6 workflow from `docs/ai/05_ml_data_curation_guide.md`
    - Addresses all governance requirements: provenance metadata, candidate workflow, quality gates, enrichment/publish flow, failure handling
    - Example campaigns: `config/campaigns/example_trend_following_15m.yaml`
    - Full documentation: `docs/ai/06_campaign_runner_guide.md`
  ```

### 119. [ ] Run full test suite
- Execute: `poetry run pytest tests/ai/campaigns/ -v`
- Assert all campaign tests pass (approximately 55+ tests across 8 modules)
- Execute: `poetry run pytest tests/cli/test_cli.py -k campaign -v`
- Assert all campaign CLI tests pass
- Execute: `poetry run pytest --cov=src/trading_platform/ai/campaigns --cov-report=term-missing`
- Assert 100% coverage for entire campaigns module

### 120. [ ] Run integration smoke test
- Create a minimal campaign YAML in `workspace/test_campaign.yaml`
- Execute: `poetry run tp campaign-plan --config workspace/test_campaign.yaml`
- Verify plan.json created with provenance
- Execute: `poetry run tp campaign-run --campaign-id test_campaign --fail-fast` (with mock/minimal data)
- Verify execution log and campaign_complete.yaml created
- Execute: `poetry run tp campaign-validate --campaign-id test_campaign`
- Verify validation report created
- Clean up test artifacts

---

## Final Verification

### 121. [ ] Verify prescribed folder structure created
- Check that `data/candidates/<campaign_id>/` structure is used throughout
- Check that `data/enriched/<campaign_id>/` is created by enrichment
- Check that `docs/ai/logs/campaign_audit.md` exists and is updated

### 122. [ ] Verify provenance tracking completeness
- Review generated plan.json files
- Confirm all provenance fields present: git_commit, poetry_lock_sha256, python_version, platform, dvc_version
- Verify timestamps in ISO format

### 123. [ ] Verify all quality gates implemented
- Review validator.py
- Confirm all checks present: schema, data quality, min trades, dedupe, indicator registry, feature completeness, max drawdown
- Verify audit log updates

### 124. [ ] Verify three decision states working
- Test workflow with approved, rejected, and needs-rework decisions
- Confirm decision.yaml files created in correct locations
- Verify filtering works correctly

### 125. [ ] Verify enrichment stage integration
- Confirm enriched dataset created before publishing
- Verify ai-curate-data is invoked
- Check metadata columns added

### 126. [ ] Verify failure artifacts generated
- Test failed run scenario
- Confirm failure_report.json created with all required fields
- Verify campaign_complete.yaml includes failure summary

### 127. [ ] Run full test suite with coverage
- Execute: `poetry run pytest --cov --cov-report=term-missing`
- Verify all tests pass
- Verify overall coverage remains >= 93%
- Verify new campaigns module has 100% coverage

### 128. [ ] Run type checking
- Execute: `poetry run mypy src/trading_platform/ai/campaigns/`
- Assert no type errors

### 129. [ ] Run linting
- Execute: `poetry run ruff check src/trading_platform/ai/campaigns/`
- Assert no linting errors

### 130. [ ] Create pull request
- Commit all changes with message: "feat: Implement Campaign Runner with complete governance workflow"
- Push feature branch
- Create pull request with description:
  - References this task list
  - Links to `docs/ai/05_ml_data_curation_guide.md` as context
  - Lists all 5 review findings addressed
  - Includes before/after comparison showing manual vs automated workflow
- Request review

---

## Summary

This implementation creates a complete Campaign Runner system that fully implements Section 6 of `docs/ai/05_ml_data_curation_guide.md` and addresses all 5 review findings:

**Finding 1 - Provenance Metadata:** ✅ Captures git commit, poetry.lock hash, Python version, platform, DVC version, **and data snapshot ID** in every plan (Section 6.1 line 164)

**Finding 2 - Candidate Workflow:** ✅ Uses prescribed `data/candidates/<campaign_id>/` structure, supports three decision states (approved, rejected, needs-rework), stores **campaign-level decision.yaml** (Section 5.2 lines 114-118)

**Finding 3 - Validation Coverage:** ✅ Implements all quality gates (schema, data quality, min trades, dedupe, **drift monitoring via KS-statistic**, indicator registry, audit logging) (Section 5.3 lines 133-143)

**Finding 4 - Enrichment/Publish Flow:** ✅ Adds explicit enrichment stage that creates `data/enriched/<campaign_id>/rich_trades.parquet` using `tp ai-curate-data`, publishing reads from enriched stage **with automated DVC tracking** (Section 5.2 lines 125-129)

**Finding 5 - Failure Handling:** ✅ Generates `failure_report.json` per failed run and `campaign_complete.yaml` summary with full environment snapshots (Section 6.4)

**Note on Section 5.4 (Manual Overrides):** ⚠️ Manual overrides system (`data/overrides/<campaign_id>.yaml`) is **NOT IMPLEMENTED** in this task list. This is marked as future work as it requires additional governance infrastructure (reason codes, JIRA integration, override replay on rebuild).

The system enables users to:
1. Define campaigns declaratively via YAML with full provenance metadata
2. Auto-generate execution plans with complete provenance including data version
3. Execute backtests in batch with comprehensive failure handling
4. Collect and organize results in prescribed folder structure
5. Validate with complete quality gates including drift monitoring
6. Review and make decisions with three states stored in campaign-level YAML
7. Enrich approved candidates into intermediate dataset
8. Publish to master trade log with automated DVC tracking and full audit trail

All functionality is test-driven with 100% coverage, follows existing architectural patterns, and integrates seamlessly with the current codebase while maintaining strict alignment with the ML data curation guide's governance requirements.
