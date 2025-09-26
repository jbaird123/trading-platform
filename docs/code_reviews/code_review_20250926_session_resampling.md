> **Code Review: Changes Required**
>
> The implementation of the session-aware resampling is logically correct, but it has been built on top of a critical architectural flaw that it also exacerbates. The following changes are required before this can be approved.
>
> - **[Critical] Resolve Symbol Inconsistency:** The `_INSTRUMENT_DEFINITIONS` dictionary in `src/trading_platform/data/instrument.py` contains duplicate entries for the same instrument using different naming conventions (e.g., `EUR/USD` and `EUR_USD`). This must be resolved. As per our previous discussion, we must standardize on a single canonical format. Please proceed with the `symbol_normalization_tasks.md` plan, starting with the refactoring of `instrument.py`, before we can approve these session-related changes.
> - **[Minor] Remove Redundant Code:** In `src/trading_platform/data/schema.py`, the `resample_ohlc` function calculates `session_hour` twice. Please remove the redundant calculation.
