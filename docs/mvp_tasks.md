# MVP Implementation Task List

This document breaks down the `mvp_roadmap.md` into a granular, actionable checklist. Mark items as complete as you finish them.

## Phase 1: Foundations

- [x] **Task 0: Codebase Cleanup**
  - [x] Delete the outdated `tests/test_sanity.py` file. Its functionality is replaced by `tests/test_core.py`.

- [x] **Task 0.5: Verify Project Skeleton**
  - [x] Run `poetry run python -m trading_platform.core.run` to confirm the `initialize_run` function creates a run directory and `config.json`.
  - [x] Run `poetry run pytest` to confirm the `test_core.py` test for `initialize_run` passes.

- [x] **Task 1: Initialize Development Environment**
  - [x] Run `poetry install` to create the virtual environment and install all dependencies listed in `pyproject.toml`.

- [ ] **Task 2: Set Up Pre-commit Hooks**
  - [x] Add `pre-commit` to the development dependencies in `pyproject.toml`.
  - [x] Run `poetry lock` to update the `poetry.lock` file with the new dependency.
  - [x] Run `poetry install` to install the packages from the updated lock file.
  - [x] Run `poetry run pre-commit install` to activate the hooks for your local git repository.
  - [x] Make a test commit to verify the hooks (e.g., `ruff`, `mypy`) run automatically.

- [ ] **Task 3: Create Initial CI/CD Workflow**
  - [x] Create the `.github/workflows/ci.yml` file and define the `name` and `on` triggers.
  - [x] Add steps to install dependencies with caching.
  - [x] Add steps to run linter (Ruff), type checker (MyPy), and tests (Pytest).
  - [ ] Push a commit to a new branch and open a Pull Request to `main` to verify that the GitHub Actions workflow is triggered and passes.
  - [ ] (Future) Add SonarQube secrets to GitHub and add the SonarQube analysis step to `ci.yml`.

- [ ] **Task 4: Implement Data Schema Contract (BDD/TDD)**
  - [ ] Create the feature file: `tests/features/data_schema.feature`.
  - [ ] Create the test file: `tests/step_defs/test_data_schema_steps.py`.
  - [ ] Run `pytest` and see the BDD tests fail with "step definition not found" errors.
  - [ ] Implement the step definition skeletons in `test_data_schema_steps.py`.
  - [ ] Run `pytest` again and see the tests fail with `NotImplementedError` or assertion errors.
  - [ ] Create the implementation file: `src/trading_platform/data/schema.py`.
  - [ ] Write the code for loading and normalizing data to make the tests pass.

---

*This task list will be expanded as we complete each phase.*
