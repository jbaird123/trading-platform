# RMM Analysis Artifacts

This directory stores lightweight, version-controlled summaries that accompany
heavier artefacts generated in the `workspace/` tree. For example:

- `feature_audit.md` – concise report from `scripts/rmm_analysis/feature_audit.py`
  explaining expected missing values (e.g., `r_multiple` absent on no-REM runs,
  lower-timeframe features omitted for higher execution timeframes).

Large CSV/PNG outputs from the audit remain in `workspace/analysis/...` so they
do not clutter the repository, while the markdown report provides the context
needed to interpret them later.
