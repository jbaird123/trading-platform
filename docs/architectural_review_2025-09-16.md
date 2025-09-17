# Architectural Review and Recommendations (2025-09-16)

This document provides a critical review of the unified `project_requirements.md`. The recent merge has resolved the major architectural conflicts. The focus of this review is to refine the design by improving consistency, clarifying component responsibilities, and ensuring the document is a practical guide for implementation.

## Overall Assessment

The architecture, centered on the separation of the Strategy Engine (SE) and the Risk & Exit Manager (REM), is sound. The principles of modularity and a canonical core are well-defined. The following recommendations are intended to build on this strong foundation.

---

## 1. Key Architectural Recommendations

### Recommendation 1: Formalize the `Run Configuration`

- **Observation**: The architecture hinges on a `Run Configuration` that binds components like the SE, REM, and Instrument together (`[Architecture-1.1]`). However, the structure of this configuration is not formally defined.
- **Problem**: Without a clear schema, we risk creating ambiguity in how runs are launched and reproduced. The CLI and backtester would have to rely on ad-hoc dictionaries, making the system brittle.
- **Recommendation**: Introduce a new requirement to define a formal schema for the `Run Configuration`. This schema would act as the top-level entry point for any backtest or live run. A draft requirement could be:

  > **Run Configuration Schema**: A formal JSON Schema shall be created for the `Run Configuration`. This configuration will define, at a minimum:
  > - A reference to the `Strategy` to be used (e.g., a path to a strategy YAML file).
  > - A reference to the `Risk & Exit Manager (REM)` configuration to be used (e.g., a path to an REM YAML file).
  > - A reference to the `Instrument` or list of instruments.
  > - The data source and time range.
  > - References to any other required components, like the `Regime Market Manager (RMM)`.

  This makes the entire run process explicit and contract-driven.

### Recommendation 2: Decouple Run Parameters in the JSON Brief

- **Observation**: The `JSON Brief Schema` (`[JSON-11.x]`) contains a flat `params` object that mixes strategy-specific parameters (e.g., `fast`, `slow` for moving averages) with risk parameters (e.g., `stop_type`, `stop_value`).
- **Problem**: This violates the architectural separation of SE and REM. The official record of the run (the brief) should not blur the lines between these components. It makes analysis difficult—was a run different because of a strategy change or a risk change?
- **Recommendation**: Modify the `JSON Brief Schema` to separate these concerns. Replace the single `params` object with two distinct objects:

  > - `strategy_params`: A snapshot of the parameters used by the Strategy Engine.
  > - `rem_config`: A complete snapshot of the Risk & Exit Manager configuration used for the run.

  This provides perfect traceability and aligns the brief's structure with the system's architecture.

### Recommendation 3: Define Exit Precedence Policy

- **Observation**: The system has two ways to close a trade: a **strategic exit** (the SE generates a `flat` signal) and a **risk-based exit** (the REM's stop-loss or take-profit is triggered).
- **Problem**: What happens if both occur on the same bar? The current requirements do not specify which takes precedence. The backtester could implement one rule, and the live engine another, leading to critical divergence.
- **Recommendation**: Add a new requirement to the Backtester (`[BT-7.x]`) and Execution Layer (`[EL-8.x]`) sections to define a clear and consistent **Exit Precedence Policy**. A sensible default would be:

  > **Exit Precedence Policy**: On any given bar, exit conditions shall be evaluated in the following order:
  > 1.  Risk-based exits from the REM (stop-loss and take-profit).
  > 2.  Strategic exits from the SE (a `flat` signal).
  > The first valid exit condition encountered is the one that is executed and recorded. This policy must be applied identically by both the Backtester and the Execution Layer.

### Recommendation 4: Improve Documentation Hygiene (Aspirational vs. Implemented)

- **Observation**: This point was raised in the previous review and is still highly relevant. The `Data Handler` section, for example, lists requirements for live data connectors, DVC, and event data handling (`[DH-2.1]`, `[DH-2.7]`, `[DH-2.12]`), none of which are implemented for the MVP.
- **Problem**: This makes the requirements document an unreliable source of truth for the *current* state of the system. A new developer might assume these features exist.
- **Recommendation**: Systematically move all unimplemented, aspirational requirements into a dedicated "Future Enhancements" subsection within each module's chapter. This makes the core, numbered requirements a true and testable reflection of the implemented system, while still keeping track of future goals.

---

## 2. Summary

By implementing these four recommendations, we will make the system architecture more explicit, robust, and easier to test, ensuring that the requirements document is a practical and accurate blueprint for development.
