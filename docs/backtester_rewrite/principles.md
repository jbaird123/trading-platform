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

## Requirements To Revisit / Expand
- _[Add new requirements here as we uncover them.]_
