# ML Model Integration Plan

## Current State
- Profitability and diagnostic models train successfully via the ML pipeline.
- ModelRegistry handles loading, saving, and prediction for both model families.
- Diagnostic outputs (quintiles, probabilities) require manual interpretation.
- No automated path exists to convert diagnostic insights into RMM YAML configs.
- Prompt-driven workflows can explore configs but lack repeatability and CI hooks.

## Goals
- Blend deterministic automation (for reproducibility) with AI-driven exploration.
- Generate candidate RMM configurations directly from diagnostic model outputs.
- Validate candidates automatically with backtests and summarize results.
- Enable automated CI/cron usage while keeping flexible entry points for AI prompts.

## Architecture Overview
1. **Diagnostic Data Collector**
   - Inputs: enriched trades, trained diagnostic models.
   - Action: score trades, capture feature context, aggregate high-quintile slices.
   - Output: machine-readable summaries stored in `analysis/diagnostic_runs/...`.

2. **Candidate Rule Generator**
   - Inputs: diagnostic summaries.
   - Action: synthesize `RMMConfig` candidates using consistent heuristics
     (threshold discovery, feature grouping, rule complexity limits).
   - Output: candidate YAML files + metadata (support counts, scores).

3. **Validation Runner**
   - Inputs: strategy config, candidate RMM YAMLs.
   - Action: run backtests, collect metrics, compare to baselines, log failures.
   - Output: metrics table, updated briefs, classification of candidate quality.

4. **Reviewer Artifacts**
   - Optional report (Markdown/HTML) capturing rankings, diffs, and context references.

5. **CI/CD Integration**
   - CLI entry points for each stage (generate, validate, summarize).
   - Status JSON or exit codes so pipelines can fail if objectives are missed.
   - Version tags capturing diagnostic model hash and dataset provenance.

6. **AI Orchestration Layer**
   - Prompt templates or scripts that call the CLI commands.
   - Supports iterative experimentation by adjusting generator parameters.
   - Logs parameter sets tried by the AI for auditability.

## Future Enhancements
- Auto-select candidate configurations based on multi-objective scoring.
- Maintain an autogen RMM library with metadata (model version, dataset).
- Feedback loop to capture live/backtest performance of adopted configs.
- Multi timeframe/strategy support with batched candidate generation.
- Visualization dashboards for candidate comparison.

## Immediate Next Steps
1. Implement diagnostic data collector module and CLI command.
2. Build candidate rule generator with threshold heuristics and YAML emitter.
3. Create validation runner that executes backtests and compiles metrics.
4. Draft documentation and usage examples (including AI-friendly prompts).
5. Wire commands into CI to ensure regressions fail fast.

## Notes for Future AI Sessions
- Use generated diagnostic summaries as the starting point, not raw briefs.
- Invoke the CLI pipeline for reproducible runs; only tweak heuristics via
  documented parameters.
- Retain artifacts in `analysis/diagnostic_runs/<timestamp>/` to allow replay.
