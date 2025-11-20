# Backtester Rewrite Plan

This document tracks the objectives, scope, and progress for the backtester rewrite.

## Guiding Goals
- **Deterministic timing semantics.** Clearly separate decision, execution, and stop timestamps so every component shares the same contract.
- **Modular layers.** Strategy, execution engine, portfolio manager, and risk/exit manager should communicate via well-defined interfaces (e.g., intents, fills, risk events).
- **Traceable context.** Every trade/brief snapshot must carry the exact decision metadata (time, price, feature payload) without recomputation or re-alignment hacks.
- **Testability-first.** Unit and integration tests should cover each module independently before we wire them together. Golden validations remain the final gate, but not the only safety net.

## Milestones

### M1 – Requirements & Architecture (Current)
**Status:** 🟡 In Progress
**Exit Criteria:** Behavioral requirements documented; interfaces defined with type hints; architecture & sequence diagrams approved; rollout decisions resolved.

#### M1.1 Behavioral Requirements
- [ ] Document entry/exit timing semantics (same-bar vs. next-bar-open).
- [ ] Enumerate timestamp types (`decision_time`, `execution_time`, `stop_check_time`) and propagation rules.
- [ ] Specify context snapshot contract (structure, schema versioning, immutability).
- [ ] Define explicit portfolio/position state machine.
- [ ] Document gap handling and tie-break policies.
- [ ] Identify cost application points and supported cost models.

#### M1.2 Interface Definitions
- [ ] Draft `DecisionSnapshot` dataclass (fields + typing).
- [ ] Draft `ExecutionIntent` model (intent type, execution model, risk metadata).
- [ ] Draft `FillEvent` structure (timestamp, price, intent reference, costs).
- [ ] Draft `RiskExitEvent` structure for REM outputs.
- [ ] Define `ExecutionEngine` protocol (inputs, outputs, clock dependency).
- [ ] Define `PortfolioManager` command API for intents/fills.

#### M1.3 Architecture & Review
- [ ] Component diagram showing flow from DataHandler → Strategy → Execution Engine → Portfolio → REM → Reporting.
- [ ] Sequence diagrams for: next-bar-open entry, intrabar stop detection, gating rejection.
- [ ] Review diagrams/requirements with team; capture feedback.
- [ ] Finalize rollout strategy before M2 begins.

### M2 – Execution Engine Implementation
- Build the new event/intent loop with unit tests and contract tests.
- Integrate the authoritative system clock abstraction.
- Provide fixtures to compare legacy vs. new loop outputs.
**Status:** ⚪ Planned

### M3 – Risk & Portfolio Integration
- Adapt REM to emit structured `RiskExitEvent`s and consume clock signals.
- Wire the portfolio FSM to handle intents/fills and apply costs centrally.
- Ensure entry window serialization works with new interfaces.
**Status:** ⚪ Planned

### M4 – Context/Reporting & Validation Harness
- Reconnect brief generation, analytics, and validation exporters to the new data flow.
- Run smoke tests + targeted golden comparisons under feature flag.
**Status:** ⚪ Planned

### M5 – Full Validation & Cutover
- Execute entire validation suite with the new engine.
- Roll through parallel → canary → default-on → legacy removal according to rollout plan.
**Status:** ⚪ Planned

## Current Focus
- Draft requirements doc that enumerates all behavioral rules (entry timing, next-bar semantics, REM expectations, cache usage).
- Identify pain points in the legacy code that the new design must avoid (e.g., implicit index shifting, duplicated context snapshots).
- Decide on initial data structures (e.g., `DecisionSnapshot`, `ExecutionIntent`, `FillEvent`) so we can stub interfaces early.

## Notes / Open Questions

### Q1 – Rollout Strategy
- **Question:** Feature flag vs. full cutover?
- **Decision Deadline:** Before M2 begins.
- **Working Plan:** Feature flag → parallel comparison → default-on with escape hatch → remove legacy.
- **Owner:** Joe + architecture leads.

### Q2 – Strategy Config Compatibility
- **Question:** Maintain backward compatibility or allow breaking changes?
- **Decision Deadline:** Before M2 begins.
- **Working Plan:** Keep existing entry/exit rule syntax; allow documented changes for timing metadata with validation tooling to compare old/new outputs.
- **Owner:** Strategy/platform owners.

### Q3 – Telemetry & Debugging
- **Question:** What observability is mandatory?
- **Decision Deadline:** Before M2 implementation.
- **Must-Haves:** Structured logs for decision→intent→fill, performance metrics, debug dumps of decision snapshots, hooks for legacy vs. new comparisons.
- **Owner:** DevOps + lead developer.

## Takeaways
- Document everything: the existing system's behavior is complicated; capturing it now prevents re-learning later.
- Keep requirements, design artifacts, and decisions in-repo for easy reference across sessions.
- Plan incremental rollout steps (parallel run, canary, full cutover) early to avoid surprises.

_(Update this plan as we make decisions, complete milestones, or discover new work.)_
