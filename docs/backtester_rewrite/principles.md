# Backtester Rewrite Principles & Requirements

Use this document to capture architectural principles, coding rules, and behavioral requirements that must hold throughout the rewrite. Add new items as they surface so the entire effort stays aligned.

## Core Principles
- **Fail fast.** Prefer explicit errors over defensive catch-alls; unexpected data or states should abort immediately so problems are visible.
- **Strict module boundaries.** Design each component (data prep, strategy, execution engine, portfolio, REM, reporting) to communicate only through defined interfaces. Future separation into standalone services should require minimal refactoring.
- **Simplicity over optionality.** Avoid sprawling optional parameters or mode flags. If a use case is necessary, model it via distinct interfaces/types rather than boolean switches.
- **Deterministic contracts.** Every interface must specify what timestamps, prices, and payloads it expects/produces so there is zero implicit shifting or re-alignment.
- **Unambiguous bar metadata.** Every time series handed to downstream modules must expose explicit `open_time` and `close_time` columns in addition to the label (always set to the bar’s open). No component should ever have to “guess” whether a value represents open or close, nor should we rely on shifting/ffill tricks to align feature caches—timestamps make alignment canonical.
- **Testability by construction.** Each module should be unit-testable in isolation with clear seams for mocks/fakes; large integration tests then stitch the pieces together.
- **Authoritative system clock.** All modules must derive “current time” from a single clock abstraction injected by the orchestrator. In live trading the clock maps to wall time; in simulation the backtester advances it per bar. No component should infer time by reading `datetime.utcnow()` or deriving it from labels on its own. This ensures deterministic sequencing and catches any attempt to operate on T‑1/T‑2 accidentally.

## Behavioral Requirements (Living List)

> **Note:** Requirement IDs use the `BT-10.x` namespace so they can be copied directly into `docs/project_requirements.md` later without renumbering.

### Timing & Execution Semantics
- **[BT-10.1]** Every component operates on explicit timestamps: `decision_time`, `execution_time`, `stop_check_time`. These values must be carried in all intents/events.
- **[BT-10.2]** No implicit index shifting or inferred alignment. Any transformation of a DataFrame must declare whether it is aligned to bar open or bar close.
- **[BT-10.3]** Next-bar-open execution semantics are canonical: decision at bar *N* close → fill intent scheduled for bar *N+1* open → REM still evaluates intrabar events starting on bar *N+1*.
- **[BT-10.4]** Stop/TP checks must specify whether they rely on intrabar zoom data or bar-level OHLC only; ambiguity resolutions must be deterministic.

### Context & Metadata Contracts
- **[BT-10.5]** `context_at_entry` / `context_at_exit` payloads are part of the external API. Structural changes require schema versioning.
- **[BT-10.6]** Decision snapshots must capture strategy features, global features, regime metadata, risk levels, and `decision_time` (ISO-8601). No partial snapshots are allowed.
- **[BT-10.7]** Once captured, context snapshots are immutable. Late enrichment is prohibited; any additional data should be stored separately with explicit provenance.

### State & Portfolio Management
- **[BT-10.8]** Entry window state must be serializable/deserializable so live trading can restart mid-window without loss.
- **[BT-10.9]** Portfolio and position transitions must follow an explicit finite-state machine (idle → pending → open → closing), avoiding ad hoc booleans.
- **[BT-10.10]** The single-position constraint must either be guaranteed by design or the new system must intentionally support multi-position workflows. There is no “implicit” assumption.

### Data & Feature Handling
- **[BT-10.11]** DataHandler’s `open_time`/`close_time` columns remain the source of truth for bar timing; all downstream consumers must reference them instead of recomputing.
- **[BT-10.12]** Global-feature caches must declare their alignment (e.g., “values valid at bar close”). Joining logic may not silently shift indexes to guess alignment.
- **[BT-10.13]** Any DataFrame handed to a strategy or gateway must specify whether its label is the bar open, close, or other reference. Strategies must never discover this via heuristics.

### Risk & Exit Management
- **[BT-10.14]** REM returns structured exit events `{price, reason, timestamp, method, metadata}` rather than raw floats; execution engine decides how to apply them.
- **[BT-10.15]** Gap handling and tie-break policies (e.g., `stop_then_tp`) must be explicitly configured and enforced consistently.
- **[BT-10.16]** Ambiguity resolution via 1-minute zoom must be deterministic, logged, and testable with golden fixtures. If zoom data is unavailable, REM must raise rather than guess.

### Cost & Execution Model
- **[BT-10.17]** PortfolioManager (or a dedicated cost service) is the only place where spreads, commissions, and slippage are applied. No other module may adjust fills for costs.
- **[BT-10.18]** Execution engines pass intents/fills but never duplicate cost logic; they simply forward cost configuration to the portfolio layer.

### Validation & Testing
- **[BT-10.19]** Golden validations remain authoritative. Any intentional deviations must be documented with rationale and migration tooling.
- **[BT-10.20]** Each module requires unit tests covering valid/invalid inputs before it participates in integration suites.
- **[BT-10.21]** Public interfaces must have contract tests or fixtures that assert required fields and failure modes.

### Extensibility & Future-Proofing
- **[BT-10.22]** Design workflows so multi-position support can be added without a wholesale rewrite (e.g., treat “position” as a collection).
- **[BT-10.23]** Execution model plug-ins (current bar close, next bar open, limit orders) should be swappable via interfaces, not conditionals.
- **[BT-10.24]** Components must be deployable as separate services in the future; avoid tight coupling to in-process assumptions.

_(Continue appending to this list as new requirements emerge. Reference IDs can align with the broader project requirements doc for traceability.)_
