# Flexible Run Output Directory Implementation Plan

This document outlines the steps to allow for custom output directories for backtest runs, enabling better organization for AI research campaigns.

**Branch Name:** `feature/flexible-run-output`

Before starting, create and switch to the specified branch:
`git checkout -b feature/flexible-run-output`

---

### Phase 1: Core Logic and Configuration

1.  [ ] **Write Test for Relaxed Path Validator:**
    -   In `tests/core/test_config.py`, create a new test function `test_run_config_allows_custom_workspace_runs_dir`.
    -   **Test Case 1 (Allow custom workspace path):**
        -   Define a custom path: `custom_dir = paths.WORKSPACE_DIR / "custom_runs"`.
        -   Create a `RunConfig` instance, passing `runs_dir=custom_dir`.
        -   Assert that the `runs_dir` attribute of the resulting config object resolves to the same path as `custom_dir`.
    -   **Test Case 2 (Reject path outside workspace):**
        -   Define a path outside the workspace: `outside_dir = "/tmp/some_dir"`.
        -   Create a `RunConfig` instance, passing `runs_dir=outside_dir`.
        -   Assert that the `runs_dir` attribute of the resulting config object resolves to the default `paths.RUNS_DIR`.

2.  [ ] **Implement Relaxed Path Validator:**
    -   In `src/trading_platform/core/config.py`, modify the `enforce_workspace_runs_dir` function inside the `RunConfig` model.
    -   The new logic should be:
        ```python
        try:
            # Check if the provided path is within the workspace directory
            self.runs_dir.resolve().relative_to(paths.WORKSPACE_DIR.resolve())
        except ValueError:
            # If it's not, log a warning and reset to the default
            logger.warning(
                "Ignoring configured `runs_dir` (%s) because it is outside the project workspace. "
                "Defaulting to: %s",
                self.runs_dir,
                paths.RUNS_DIR,
            )
            self.runs_dir = paths.RUNS_DIR
        return self
        ```

3.  [ ] **Write Test for CLI Output Directory Argument:**
    -   In `tests/cli/test_cli.py`, create a new test function `test_cmd_run_backtest_uses_output_dir`.
    -   Use `unittest.mock.patch` to mock `trading_platform.core.run.initialize_run`.
    -   Define a custom output directory path, e.g., `"workspace/test_cli_runs"`.
    -   Invoke the main CLI entrypoint with arguments that include `--output-dir`, for example: `["run-backtest", "--config", "/fake/config.yaml", "--output-dir", "workspace/test_cli_runs"]`.
    -   In the test, capture the `RunConfig` object passed to the mocked `initialize_run`.
    -   Assert that the `runs_dir` attribute of this captured `RunConfig` object is a `Path` object equivalent to `"workspace/test_cli_runs"`.

4.  [ ] **Implement CLI Output Directory Argument:**
    -   In `src/trading_platform/cli.py`, locate the `main` function.
    -   Find the subparser for `run-backtest` (variable `pb`).
    -   Add the new argument:
        ```python
        pb.add_argument(
            "--output-dir",
            help="Custom root directory for run artifacts (must be within workspace)",
        )
        ```
    -   In the `cmd_run_backtest` function, after loading the raw config (`cfg_raw = _load_config(cfg_path)`), add the following logic:
        ```python
        if args.output_dir:
            cfg_raw["runs_dir"] = args.output_dir
        ```

### Phase 2: AI Prompt Integration

5.  [ ] **Update AI Methodology Prompt:**
    -   Open the file `docs/ai_prompts/methodology/04_ai_regime_and_signal_discovery.md`.
    -   In section `2. Core Mandates & Guardrails`, add a new bullet point:
        ```markdown
        - **Organized Outputs:** When executing a backtest, you **MUST** use the `--output-dir` argument and set it to the current iteration's directory (e.g., `.../001_ema_crossover_iteration/`) to ensure run artifacts are co-located with the research configuration.
        ```
