> **Code Review: Approved**
>
> All changes are implemented correctly, fully tested, and adhere to all project standards. No further action is required.
>
> **Suggested Commit Message:**
> ```
> feat(data): implement session-aware daily resampling
>
> This commit introduces session-aware daily resampling and the underlying data models required to support it.
>
> - Adds a `SessionDefinition` model to define trading session boundaries.
> - Updates `InstrumentDefinition` to include a list of `SessionDefinition` objects.
> - Refactors the `resample_ohlc` function to use the session close time as the `origin` for daily resampling, ensuring that daily bars align with trading sessions (e.g., 17:00 NY time for Forex).
> - Modifies the `load_from_catalog` data loader to return the `InstrumentDefinition`, making this information available to the resampling logic.
> - Adds comprehensive, test-first unit tests for all new models and logic.
> ```
