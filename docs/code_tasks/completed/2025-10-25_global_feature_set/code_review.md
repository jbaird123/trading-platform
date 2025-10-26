> **Code Review: Approved**
>
> The core infrastructure for the Global Feature Set is implemented correctly, is fully tested, and adheres to all project standards and our design discussions. This is an excellent foundation for the subsequent integration work. No further action is required on the completed sections.
>
> **Suggested Commit Message:**
> ```
> feat(core): Implement global feature set infrastructure
>
> Implements the core utilities and validation models for a new global feature set, ensuring a consistent feature baseline for ML models.
>
> - Establishes a strict naming convention to separate global (timeframe-prefixed) and strategy (non-prefixed) feature namespaces.
> - Adds Pydantic validators to enforce naming rules at config load time, preventing naming collisions.
> - Removes the ambiguous `contextual_features` field from `RunConfig`.
> - Creates a shared `resolve_global_features` utility to load, validate, and filter global features based on execution timeframe. This utility will be used by both the backtester and live engine to ensure parity.
> - Adds a `compare_timeframes` utility for robust timeframe comparisons.
> - Includes comprehensive documentation for the new system.
> ```
