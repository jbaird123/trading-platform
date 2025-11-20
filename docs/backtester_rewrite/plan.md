# Backtester Rewrite Plan

This document tracks the objectives, scope, and progress for the backtester rewrite.

## Guiding Goals
- **Deterministic timing semantics.** Clearly separate decision, execution, and stop timestamps so every component shares the same contract.
- **Modular layers.** Strategy, execution engine, portfolio manager, and risk/exit manager should communicate via well-defined interfaces (e.g., intents, fills, risk events).
- **Traceable context.** Every trade/brief snapshot must carry the exact decision metadata (time, price, feature payload) without recomputation or re-alignment hacks.
- **Testability-first.** Unit and integration tests should cover each module independently before we wire them together. Golden validations remain the final gate, but not the only safety net.

## Milestones
| Milestone | Description | Owner | Status |
|-----------|-------------|-------|--------|
| M1 | Capture detailed requirements & finalize target architecture diagram | Codex + Joe | ⚪ Planned |
| M2 | Implement new execution engine (signal → intent → fill) with tests | Codex | ⚪ Planned |
| M3 | Rebuild REM integration & gap handling on top of the new engine | Codex | ⚪ Planned |
| M4 | Reconnect context/brief generation; prove parity on smoke tests | Codex | ⚪ Planned |
| M5 | Re-enable full validation suite and retire legacy backtester code | Codex + Joe | ⚪ Planned |

## Current Focus
- Draft requirements doc that enumerates all behavioral rules (entry timing, next-bar semantics, REM expectations, cache usage).
- Identify pain points in the legacy code that the new design must avoid (e.g., implicit index shifting, duplicated context snapshots).
- Decide on initial data structures (e.g., `DecisionSnapshot`, `ExecutionIntent`, `FillEvent`) so we can stub interfaces early.

## Notes / Open Questions
- How should we version the new backtester during rollout (feature flag vs. full cut over)?
- Do we maintain compatibility with existing strategy configs, or is a migration acceptable?
- What telemetry or debugging hooks do we want baked in from day one?

_(Update this plan as we make decisions, complete milestones, or discover new work.)_
