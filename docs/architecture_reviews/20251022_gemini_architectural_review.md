# Architectural Review of project_requirements.md

**Date:** 2025-10-22
**Reviewer:** Gemini

This document provides an architectural review of the `project_requirements.md` specification for the trading platform. The review is conducted from the perspective of a systems architect, focusing on design clarity, scalability, maintainability, and risk.

## 1. Strengths

The requirements document is exceptionally well-structured and lays a strong foundation for a robust and maintainable system. Key strengths include:

- **Excellent Modularity:** The clear separation of concerns between the Data Handler (DH), Strategy Engine (SE), Risk & Exit Manager (REM), Portfolio Manager (PM), and Regime Market Manager (RMM) is a significant architectural strength. This modularity, enforced by requirements like `[SYS-1.1.1]` and `[SYS-1.2.2]`, will facilitate parallel development, independent testing, and future scalability.

- **Strategy vs. Risk Separation:** The explicit mandate that the Strategy Engine is for **signal generation only** (`[SE-3.3]`) while the REM handles all trade management logic (`[REM-6.1]`) is a critical and well-executed design choice. This promotes the reusability of strategies across different risk models and instruments.

- **Backtest/Live Parity:** Requirement `[SYS-1.1.3]` correctly identifies that the Backtester and Execution Layer must use the exact same core components (especially the `PortfolioManager`). This is fundamental to building trust in backtested results and is often a failure point in many trading systems.

- **Declarative-First Approach:** The use of YAML for defining Strategies (`[SE-3.5]`), Risk & Exit Models (`[REM-6.2]`), and Market Regimes (`[RMM-4.9]`) is a powerful feature. It makes the system more accessible to non-programmers, simplifies version control for strategies, and enables easier programmatic generation and analysis of configurations.

- **Emphasis on Testability:** The project's commitment to 100% test coverage, TDD/BDD (`[SYS-1.10]`), and traceability (`[TRACE-17.1]`) is a major strength that will lead to higher quality and fewer regressions.

- **Canonical-First Engine:** The principle of an instrument-agnostic core that operates on canonical values (`[SYS-1.3]`) is a forward-looking design that will make it much easier to expand the platform to other asset classes (e.g., futures, equities) in the future.

## 2. Weaknesses & Gaps

While the foundation is strong, several areas lack the necessary detail for implementation and present architectural risks.

- **Under-defined "Rule Translator" (RT):** The RT is mentioned as a key component for translating native terms (pips, points) into canonical values, which is central to the "Canonical-First" architecture. However, it lacks a dedicated requirements section. Key questions are unanswered:
  - What is its precise API?
  - How does it access instrument metadata (e.g., pip location, point value)?
  - Who invokes it? The Backtester/Execution Layer, or the REM itself?
  This ambiguity makes a core part of the system's cross-asset capability difficult to implement.

- **Vague Portfolio Manager State Persistence:** Requirement `[PM-5.8.5]` mandates that entry window state be serializable, but this is insufficient for a robust live trading environment. The entire state of the `PortfolioManager` (cash, open positions, equity history, daily PnL) must be persisted transactionally to ensure full recovery from a crash without loss of state or funds. The current requirements do not detail this critical mechanism.

- **Scalability of Data Synchronization:** The data sync service, as defined in `[DH-2.14]` through `[DH-2.19]`, requires the `DataHandler` to load a base file and then concatenate all incremental files at runtime (`[DH-2.18.1]`). As the system runs for years, this will lead to loading thousands of small CSV files, which is a significant performance bottleneck.

- **Unclear Real-Time AI Integration:** The AI Lab's "Real-Time Decision Making" use case (`[AI-10.1.1]`) is architecturally vague. Stating it will use a "message queue or low-latency REST API" (`[AI-10.5.6]`) is a starting point, but a formal API contract is missing. The data payload, latency requirements, and fallback behavior (what happens if the AI service is down?) are undefined.

## 3. Architectural Recommendations

To address the identified weaknesses, I recommend the following architectural refinements:

1.  **Elevate the Rule Translator (RT) to a First-Class Module:**
    - **Action:** Create a new section in the requirements document dedicated to the `RuleTranslator`.
    - **Recommendation:** Define the RT as a **stateless service/utility**. Its primary function should be `translate(rule: dict, instrument: InstrumentDefinition) -> CanonicalRule`. This pure-function approach makes it highly testable and decoupled. The Backtester and Execution Layer will be responsible for invoking it at runtime, passing the native rules from the REM and the appropriate instrument definition.

2.  **Formalize Portfolio Manager State Persistence with Journaling:**
    - **Action:** Expand the `PortfolioManager` requirements to include a formal state persistence strategy.
    - **Recommendation:** Implement an **event-sourced or journal-based persistence mechanism** for the `PortfolioManager`. After every state-changing event (e.g., `ORDER_FILL`, `BAR_CLOSE`), the PM should append a record to a journal file (e.g., a local SQLite database or a simple log file). On startup, the PM can reconstruct its exact state by replaying the journal. This is more robust than simple state serialization.

3.  **Introduce a Data Compaction Step for Scalability:**
    - **Action:** Update the "Automated Data Synchronization Service" requirements (`[DH-2.14]`+).
    - **Recommendation:** The sync service's responsibility should be expanded. After downloading a new incremental file, it should trigger a **compaction process**. This process would read the existing master Parquet file and the new incremental CSV, and write a *new, versioned master Parquet file*. The `DataHandler` would then only ever need to load a single file per instrument, drastically improving load times. This aligns with `[DH-2.10]` but makes the caching strategy more explicit and scalable.

4.  **Define a Clear API Contract for Real-Time AI:**
    - **Action:** Create a formal API specification for the real-time AI service, perhaps in a separate `docs/api/ai_inference.yml` file using the OpenAPI standard.
    - **Recommendation:** The contract should define a simple, low-latency endpoint (e.g., `POST /v1/filter_signal`). The request payload should be minimal (e.g., `{ "features": { "rsi": 65, "adx": 30 } }`), and the response should be a simple decision object (e.g., `{ "action": "proceed", "confidence": 0.85 }`). This decouples the AI model development from the core trading engine.

## 4. Risk Analysis

- **Backtester Orchestration Complexity:** The `Backtester` (`[BT-7.1]`) is the most complex component, managing the simulation loop and coordinating all other modules. Its stateful logic, especially around handling entry windows, pending exits for flips, and filter enforcement, is a high-risk area for subtle bugs. Rigorous, scenario-based integration testing will be critical here.

- **Counterfactual Simulation Performance:** The "exact" counterfactual simulation mode (`[BT-7.11]`) is a powerful feature but poses a performance risk. Re-running a simulation for every skipped trade could lead to extreme slowdowns in scenarios where filters are very active. The performance impact should be benchmarked, and this feature should be clearly marked as a non-default, intensive analysis tool.

- **Data Integrity and Error Handling:** The system's correctness is highly sensitive to data quality. A single erroneous price spike in the data could invalidate an entire backtest. While `[DH-2.6]` mentions validation, the system's response to such errors is not defined. The system should implement a clear policy: either halt on data quality failures or produce explicit warnings and continue, with the behavior being configurable.

- **Traceability Gaps:** The requirements check revealed a significant number of requirements without corresponding tests. This gap between specification and verification (`[TRACE-17.1]`) is a major risk that will lead to technical debt, regressions, and a lack of confidence in the system's adherence to its own rules.

## 5. Prioritized Next Steps

1.  **Define the Rule Translator (RT) Module:** This is the most significant architectural gap. A clear definition is required before the REM, Backtester, and Execution Layer can be properly implemented.
2.  **Address Traceability Gaps:** The team should immediately begin linking existing tests to requirement IDs and prioritize creating tests for critical uncovered requirements (e.g., Portfolio Manager state, RMM policies). This will build a solid foundation for future development.
3.  **Refine the Portfolio Manager State Persistence Strategy:** A robust solution for live trading recovery is essential and should be designed before the `ExecutionLayer` is built.
4.  **Update the Data Synchronization Requirements:** Modify the requirements to include a data compaction step to ensure long-term performance and scalability.
