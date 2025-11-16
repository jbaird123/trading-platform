# Global Feature Parity Implementation Plan

### **Developer Mandates**

-   **No Bypassing Checks:** You must **never** bypass `mypy` or `ruff` checks. Using `--no-verify` or similar flags to circumvent pre--commit hooks is strictly forbidden. All code must pass all static analysis and linting checks.
-   **No Deferrals:** You must **never** mark any task as "deferred" or flag it for "future work." If a task is in the plan, it must be implemented.
-   **Full Implementation:** All tasks must be **completely implemented** as described. Do not leave placeholders or incomplete logic.
-   In addition, every task you define must explicitly enforce the **fail-fast exception handling policy** documented in `docs/coding_standards/exception_handling_policy.md`. Any plan that allows silent failures, defensive exception swallowing, or retries that contradict that policy is automatically invalid. Make the policy a first-class acceptance criterion for each implementation item.

1. [ ] **Create branch `feature/global-feature-parity`.** From the latest `canonical-timeframes` tip, run `git checkout -b feature/global-feature-parity`. All subsequent work must happen on this branch so we can trace the changes back to the global feature parity effort noted in [SYS-1.1.3].
2. [ ] **Add parity tests for the shared global-feature pipeline.**
    - File: `tests/core/test_global_feature_pipeline.py`.
    - Import `trading_platform.strategy.features.compute_features` and (future) `trading_platform.core.global_feature_pipeline.build_global_feature_frame`.
    - Create fixtures generating deterministic 5-minute OHLCV data (use `pd.date_range` and seeded numpy). Build a feature manifest covering: (a) same-timeframe EMA, (b) higher-timeframe ATR, (c) multi-timeframe dependency (15min SMA requiring resample).
    - Write tests that:
     1. Call `compute_features` with the manifest and capture both the returned DataFrame and `guard_info` equivalent (mock as needed).
     2. Call `build_global_feature_frame` (once implemented) with the same inputs.
     3. Assert via `pd.testing.assert_frame_equal` that columns, dtypes, and first/last timestamps match exactly (tolerance ≤ 1e-12).
     4. Assert that the helper’s metadata dict reports identical warmup start timestamps and NaN guard positions as the compute version.
     5. Verify that when an unsupported timeframe is requested (e.g., “37min”), the helper raises `ValueError` with a message containing the invalid timeframe token.
    - These tests will fail until the shared helper is implemented, giving a red-green path.
3. [ ] **Implement the shared global-feature pipeline and integrate `compute_features`.**
    - Add `src/trading_platform/core/global_feature_pipeline.py` exporting:
     ```python
     def build_global_feature_frame(
         market_data: pd.DataFrame,
         feature_defs: list[dict[str, Any]],
         *,
         execution_timeframe: str,
         data_handler: DataHandler | None = None,
         warmup_start: pd.Timestamp | None = None,
         resample_strategy: str = "forward_fill",
     ) -> tuple[pd.DataFrame, dict[str, pd.Timestamp]]:
     ```
    - The function must implement the following algorithm so failures surface immediately:
        1. Validate and canonicalize `execution_timeframe` via `timeframe_aliases.canonicalize_timeframe()`. If the value is falsy or unknown, raise `ValueError(f"Unsupported timeframe: {execution_timeframe}")`.
        2. Initialize `feature_columns: list[pd.Series] = []` and `valid_starts: dict[str, pd.Timestamp] = {}`.
        3. Group `feature_defs` by the declared `timeframe` (default to the canonical execution timeframe). Store these groups in an ordered dict so higher timeframes are processed after same-timeframe features.
        4. For each group:
            - If the group timeframe equals the execution timeframe, use `market_data`.
            - Otherwise, resample using `data.resample(rule, label="right", closed="right").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})`, then align to bar-close by shifting the resulting index to the bar close timestamp.
            - If resampling cannot be performed because the rule is invalid, raise `ValueError` immediately.
        5. For each feature definition inside the group:
            - Resolve the indicator via `_FEATURE_FUNCTIONS[name]`; raise `KeyError` if it does not exist.
            - Clone the params dict, substitute any `${param}` references using `strategy_parameters`, and invoke the indicator function with the resampled DataFrame.
            - Append the resulting `pd.Series` (renamed to the canonical column name) to `feature_columns`.
            - Determine the first non-NaN timestamp via `series.first_valid_index()`; store it in `valid_starts[column_name]`.
        6. Concatenate `feature_columns` along axis=1, reindexing to `market_data.index` via `.reindex(market_data.index)` so downstream consumers always align to execution bars.
        7. Return `(concatenated_frame, {"valid_start": valid_starts})`.
    - Refactor `trading_platform.strategy.features.compute_features` to call this helper instead of duplicating resample logic. Preserve the public signature and ensure `strategy_parameters` continue to flow into feature param substitution.
    - Ensure all new helper parameters are configurable (no magic numbers) and propagate exceptions from the helper without suppression.
    - Update imports and `__all__` where necessary to expose the helper.
4. [ ] **Add manifest-digest enforcement tests for the cache loader/builder.**
    - File: `tests/core/test_global_features_cache.py`.
    - Create tests that:
     1. Build a minimal cache directory via `tmp_path` with a fake metadata file containing `manifest_digest: "abc"`.
     2. Mock `global_feature_pipeline.build_global_feature_frame` to return a simple frame and metadata.
     3. Assert `build_global_feature_cache` writes the digest to metadata and `load_cached_global_features` raises `ValueError` when the manifest hash differs from the current config contents.
     4. Add a regression test ensuring a matching digest allows loading and that the returned `DataFrame` matches the builder output.
    - Tests must confirm error messages mention both the expected and actual digest strings for debuggability per [15. Development Process & Governance].
5. [ ] **Implement manifest hashing and cache integration.**
    - Update `src/trading_platform/core/global_features_cache.py` to:
     1. Compute a SHA256 digest from the serialized manifest + helper version string via a new utility `compute_manifest_digest(manifest: dict[str, Any]) -> str`.
        - Define “transient objects” as any non-JSON-serializable types (e.g., `pd.Timestamp`, `np.int64`). When preparing the manifest for hashing, convert timestamps to ISO8601 strings, convert numpy/pandas scalars to native Python (`int`, `float`, `str`), and sort all dict keys recursively so the serialized structure is deterministic. Provide an example schema in the docstring showing the exact sorted JSON fragment used in hashing.
     2. Store `manifest_digest` inside each timeframe’s metadata alongside existing columns/rows counts.
     3. During `load_cached_global_features`, compare the stored digest to the digest derived from the caller’s feature config; raise `ValueError` on mismatch with guidance to rebuild the cache.
     4. Replace direct indicator computation with a call to `build_global_feature_frame`, passing through `data_handler`, `execution_timeframe`, and `warmup_start`.
    - Update `trading_platform/strategy/features.py` where manifests are parsed so they expose a deterministic dict for hashing (sorted keys, no transient objects).
    - Ensure any new helper is imported via public modules (respecting [SYS-1.2.1]).
6. [ ] **Add CLI validation script tests.**
    - File: `tests/scripts/test_validate_feature_cache.py`.
    - Write tests using `tmp_path` to create a miniature cache (two timestamps, one feature).
    - Mock `build_global_feature_frame` to emit controlled data, then import `scripts.validate_feature_cache.main` directly and invoke it with a patched `sys.argv` to avoid brittle subprocess calls.
    - Assert the script exits `0` (by catching `SystemExit`) when cache rows equal recomputed rows and exits `1` when deliberate corruption (e.g., mutate a parquet cell) is introduced.
    - Verify the textual summary lists the timeframe, number of mismatched columns, and the digest being verified.
7. [ ] **Implement `scripts/validate_feature_cache.py`.**
    - Create a CLI (argparse) accepting: `--cache-dir`, `--symbol`, `--timeframe`, `--feature-config` (optional if the cache metadata already embeds the manifest digest), `--sample-size`, and `--max-drift` (float tolerance default `1e-9`).
    - Workflow:
     1. Load the manifest YAML specified by `--feature-config`.
     2. Compute the manifest digest and print it.
     3. Load the cache parquet for the timeframe via `load_cached_global_features`.
     4. Recompute the same rows using `build_global_feature_frame` restricted to either `sample_size` random timestamps or the full index.
     5. Compare values with `np.isclose(tol=max_drift)`; report mismatched cells and exit `1` if any are found.
    - Ensure logging is concise and structured (per [13.2 Logging Requirements]) and reuse existing console utilities if available.
8. [ ] **Document the unified pipeline workflow.**
    - Update `docs/engineering/runbooks/global_features.md` (create parent directories if missing) with a section titled “Canonical Global Feature Pipeline”.
    - Document:
        1. The new helper’s responsibilities.
        2. The manifest digest contract and how to rebuild caches when it changes.
        3. How to run `scripts/validate_feature_cache.py` as part of release validation.
    - Reference the relevant requirements `[SYS-1.1.3]` and `[7. Backtester]` to show compliance.

9. [ ] **Add an integration test covering the full pipeline.**
    - File: `tests/integration/test_global_feature_pipeline_end_to_end.py`.
    - Steps:
        1. Use `tmp_path` to build a synthetic cache with two timeframes and a manifest digest.
        2. Call `build_global_feature_frame`, write the resulting parquet, then load it via `load_cached_global_features`.
        3. Invoke the CLI validation script’s main entry point with the same manifest and assert it reports zero mismatches.
    - The test must prove that cache building, loading, hashing, and CLI validation interoperate without silent fallbacks.

10. [ ] **Verify 100% test coverage.**
    - Run `poetry run pytest --cov=trading_platform.core.global_feature_pipeline --cov=trading_platform.core.global_features_cache --cov=trading_platform.strategy.features --cov-report=term-missing` to satisfy [SYS-1.10.2].
    - Ensure coverage is 100% for all modified modules. If any lines are uncovered, add targeted tests to close the gaps.
    - Commit the final test suite with a message confirming coverage compliance.
