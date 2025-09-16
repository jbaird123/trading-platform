# Requirements Review & Architectural Feedback (2025-09-16)

This document captures conflicts, discrepancies, and architectural feedback from a review of `project_requirements.md` against the current codebase.

## 1. Conflicts & Discrepancies

This section highlights requirements that directly conflict with the implemented code.

### Data Handler (DH)
- **Conflict**: `[DH-2.1]` states the system loads data from "OANDA, Dukascopy."
- **Implementation**: The `load_and_normalize_data` function in `src/trading_platform/data/schema.py` only supports loading from local CSV files. There is no code for connecting to any external data provider.
- **Impact**: High. The requirement misrepresents a core capability of the system.

### Backtester (BT) & Strategy Engine (SE)
- **Conflict**: The architecture (SE-3.3, REM-6.1) specifies a strict separation between signal generation (SE) and risk management (REM). Strategies should *not* contain stop-loss or take-profit logic.
- **Implementation**: The `run_backtest` function in `src/trading_platform/backtester/core.py` directly implements stop-loss and take-profit logic by iterating through `strategy.long_exit_blocks` and `strategy.short_exit_blocks`. This hard-codes risk management inside the backtester loop and tightly couples it to the `CompiledStrategy` object.
- **Impact**: Critical. This violates the core architectural principle of separating strategy from risk. The backtester is interpreting risk rules from the strategy definition, not from a separate, pluggable Risk & Exit Manager (REM) component.

### Reporting & Visualization (RV)
- **Conflict**: The additions file (`[BRIEF-11.2]`) requires that for any trade closed by a risk rule, the JSON brief must record the original **native rule** (e.g., `{ "value": 50, "type": "pips" }`).
- **Implementation**: The `_serialize_trade` function in `src/trading_platform/reporting/brief.py` only records a simple `exit_reason` string (e.g., "stop-loss"). It does not capture or store the specific native rule configuration that triggered the exit.
- **Impact**: Medium. This breaks the required traceability between a trade's exit and the specific risk parameter that caused it, which is important for analysis and optimization.

## 2. Architectural Recommendations

This section highlights areas where the architecture is ambiguous, could be improved, or deviates from the conceptual model described in the requirements.

### The "Risk & Exit Manager (REM)" is a Ghost Module
- **Observation**: The requirements define the REM as a distinct, pluggable module responsible for all risk and exit logic. However, no such module exists in the codebase (i.e., there is no `src/trading_platform/risk_manager/` or similar).
- **Current Implementation**: Risk and exit rules are defined within a `risk` block in the strategy YAML/JSON schema and are directly interpreted by the `run_backtest` function.
- **Recommendation**: Re-evaluate the REM concept.
    1.  **Option A (Embrace Current Design)**: If the current design is preferred, the requirements should be rewritten to eliminate the concept of a separate REM module. Instead, document that risk/exit rules are a property of the **Strategy Definition** and are executed by the **Backtester/Execution Layer**. This is simpler but creates a tighter coupling.
    2.  **Option B (Implement the REM)**: To adhere to the principle of separation, a true `RiskExitManager` class/module should be created. The backtester would be given a `Strategy` object and a `RiskExitManager` object, and it would be the REM's job to tell the backtester when to close a position. This is more complex but architecturally cleaner.

### The "Runtime Translation" Principle is Not Explicit
- **Observation**: The `projec_requirements_additions.md` file introduces the critical concept of "Runtime Translation"—the idea that the Backtester (BT) and Execution Layer (EL) are responsible for converting native risk rules (e.g., "50 pips") into canonical price levels. The main requirements document is less clear.
- **Current Implementation**: The `run_backtest` function does *not* perform this translation. It only handles fixed price offsets (`sl_rule["type"] == "price"`). It does not have logic to convert pips, ATR, or percentages based on instrument metadata.
- **Recommendation**:
    1.  The "Runtime Translation" principle should be formally and clearly stated in the `Backtester (BT)` and `Execution Layer (EL)` sections of the main requirements document.
    2.  The backtester and execution layer must be implemented to actually perform this translation. This is a significant feature gap that also represents an architectural conflict.

### Aspirational vs. Implemented Requirements
- **Observation**: The Data Handler section, in particular, contains many requirements for features that are not implemented (live data connectors, DVC, Parquet caching, event data).
- **Recommendation**: To make the requirements document a reliable source of truth for the *current* system, move all unimplemented, aspirational features to a dedicated "Future Enhancements" or "Roadmap" section at the end of the document or within each module's section. This clarifies what the system *does* versus what it *will do*. (Note: The user cancelled the tool call to do this, but the recommendation stands).
