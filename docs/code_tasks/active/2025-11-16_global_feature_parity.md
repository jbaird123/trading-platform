# Global Feature Parity Implementation Plan

### **Developer Mandates**

-   **No Bypassing Checks:** You must **never** bypass `mypy` or `ruff` checks. Using `--no-verify` or similar flags to circumvent pre--commit hooks is strictly forbidden. All code must pass all static analysis and linting checks.
-   **No Deferrals:** You must **never** mark any task as "deferred" or flag it for "future work." If a task is in the plan, it must be implemented.
-   **Full Implementation:** All tasks must be **completely implemented** as described. Do not leave placeholders or incomplete logic.

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
     The function must:
     1. Canonicalize `execution_timeframe` via `trading_platform.data.timeframe_aliases`.
     2. Iterate feature defs, grouping by source timeframe.
     3. For higher timeframes, resample `market_data` using the same logic currently embedded in `compute_features` (respect `resample_strategy`, align to `bar_close`).
     4. Run the appropriate indicator function from `trading_platform.strategy.features._FEATURE_FUNCTIONS`.
     5. Track the earliest non-NaN timestamp per column for downstream guard checks.
     6. Return the concatenated frame (indexed on `market_data.index`) plus metadata dictionary `{"valid_start": {column: timestamp}}`.
   - Refactor `trading_platform.strategy.features.compute_features` to call this helper instead of duplicating resample logic. Preserve the public signature and ensure `strategy_parameters` continue to flow into feature param substitution.
   - Ensure all new helper parameters are configurable (no magic numbers).
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
     2. Store `manifest_digest` inside each timeframe’s metadata alongside existing columns/rows counts.
     3. During `load_cached_global_features`, compare the stored digest to the digest derived from the caller’s feature config; raise `ValueError` on mismatch with guidance to rebuild the cache.
     4. Replace direct indicator computation with a call to `build_global_feature_frame`, passing through `data_handler`, `execution_timeframe`, and `warmup_start`.
   - Update `trading_platform/strategy/features.py` where manifests are parsed so they expose a deterministic dict for hashing (sorted keys, no transient objects).
   - Ensure any new helper is imported via public modules (respecting [SYS-1.2.1]).
6. [ ] **Add CLI validation script tests.**
   - File: `tests/scripts/test_validate_feature_cache.py`.
   - Write tests using `tmp_path` to create a miniature cache (two timestamps, one feature).
   - Mock `build_global_feature_frame` to emit controlled data, then run the script’s `main()` (to be added) via `subprocess.run([sys.executable, "scripts/validate_feature_cache.py", ...])` capturing stdout.
   - Assert the script exits `0` when cache rows equal recomputed rows and exits `1` when deliberate corruption (e.g., mutate a parquet cell) is introduced.
   - Verify the textual summary lists the timeframe, number of mismatched columns, and the digest being verified.
7. [ ] **Implement `scripts/validate_feature_cache.py`.**
   - Create a CLI (argparse) accepting: `--cache-dir`, `--symbol`, `--timeframe`, `--feature-config`, `--sample-size`, and `--max-drift` (float tolerance default `1e-9`).
   - Workflow:
     1. Load the manifest YAML specified by `--feature-config`.
     2. Compute the manifest digest and print it.
     3. Load the cache parquet for the timeframe via `load_cached_global_features`.
     4. Recompute the same rows using `build_global_feature_frame` restricted to either `sample_size` random timestamps or the full index.
     5. Compare values with `np.isclose(tol=max_drift)`; report mismatched cells and exit `1` if any are found.
   - Ensure logging is concise and structured (per [13.2 Logging Requirements]) and reuse existing console utilities if available.
8. [ ] **Document the unified pipeline workflow.**
   - Update `docs/engineering/runbooks/global_features.md` (create if missing) with a section titled “Canonical Global Feature Pipeline”.
   - Document:
     1. The new helper’s responsibilities.
     2. The manifest digest contract and how to rebuild caches when it changes.
     3. How to run `scripts/validate_feature_cache.py` as part of release validation.
   - Reference the relevant requirements `[SYS-1.1.3]` and `[7. Backtester]` to show compliance.
