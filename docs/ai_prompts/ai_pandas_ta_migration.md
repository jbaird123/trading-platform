# Migration Plan: `ta` → `pandas-ta` (Small‑Steps Mode)

This plan helps you migrate a Python codebase from [`ta`](https://github.com/bukosabino/ta) to [`pandas-ta`](https://github.com/twopirllc/pandas-ta) **without overwhelming your AI assistant or your test suite**. It emphasizes tiny, reviewable diffs, an adapter layer, and module‑by‑module rollouts.

---

## Guiding Principles
- **Small‑Steps Mode:** ≤50 changed lines per step, always include tests, provide a short rationale.
- **Adapter First:** Hide `pandas-ta` behind a thin adapter to keep call sites stable.
- **One Module at a Time:** Convert and stabilize a single module before moving on.
- **Test Parity over Exactness:** Normalize names/NaNs; allow small numeric tolerances.
- **Stop Points:** After each patch, stop and await approval before proceeding.

---

## Phases & Copy‑Paste Prompts

### Phase 0 — Migration Game Plan
**Prompt:**  
> You are my refactor copilot. Goal: migrate from the **ta** library to **pandas-ta** across this repo with minimal breakage.  
> Constraints:  
> - Use **Small‑Steps Mode**: ≤50 lines per step; include tests; show a `git diff` style patch and a brief why/how.  
> - Prefer an **adapter layer** to minimize call‑site churn.  
> - Never change more than one module per step.  
> - After each step, conceptually “run tests” and list likely failures with reasons; propose the next smallest step.  
> Deliverables now:  
> 1) A phased plan (inventory → mapping → adapter → pilot → test fixes → rollout → enforce → parity → optional decommission).  
> 2) A risk list (params/naming/output‑shape/warmup NaNs/perf).  
> 3) A commit plan (tiny PRs). Keep it concise and actionable.

---

### Phase 1 — Build the Mapping Guide
Inventory every indicator you use and map it from `ta` → `pandas_ta`.

**Prompt:**  
> Build a **`ta` → `pandas_ta` mapping table** for every indicator used in this repo. For each:  
> - Old import/call (from `ta`), new import/call (from `pandas_ta`)  
> - Param name/default differences  
> - Return shape & column naming conventions  
> - Warmup/NaN behavior  
> - Known pitfalls (e.g., `window`→`length`, EMA `adjust`)  
> Output as a **Markdown table** + short notes. Flag any uncertainties.

**Starter table (fill in based on your usage):**

| Indicator | `ta` (old) | `pandas-ta` (new) | Param diffs | Returns | Notes |
|---|---|---|---|---|---|
| SMA | `SMAIndicator(close, window=14).sma_indicator()` | `pandas_ta.sma(close, length=14)` or `df.ta.sma(length=14)` | `window`→`length` | Series | Name often `SMA_14`; standardize |
| EMA | `EMAIndicator(close, window=14).ema_indicator()` | `pandas_ta.ema(close, length=14)` | `window`→`length`; `adjust` semantics | Series | Warmup NaNs |
| RSI | `RSIIndicator(close, window=14).rsi()` | `pandas_ta.rsi(close, length=14)` | `window`→`length` | Series | Range `[0,100]` |
| ATR | `AverageTrueRange(h,l,c, window=14).average_true_range()` | `pandas_ta.atr(h,l,c, length=14)` | `window`→`length` | Series | Needs H/L/C |

---

### Phase 2 — Introduce an Adapter
Create `trading_platform/indicators_adapter.py` (or similar). The adapter:
- Mirrors your **existing** function names/signatures where feasible (e.g., `sma(close, window=14)`).
- Calls `pandas_ta` inside.
- Normalizes outputs to **Series with deterministic names** (e.g., `SMA_14`, `EMA_50`).
- Centralizes quirks: `window`→`length`, warmup NaNs trimming, dtype, column naming.

**Prompt:**  
> Propose a minimal `indicators_adapter.py` that preserves current function names/signatures but uses `pandas_ta` internally. Include docstrings and 2–3 tiny tests (SMA/EMA/RSI) that prove consistent shape & naming. Keep the patch ≤50 lines if possible.

---

### Phase 3 — Pilot Swap (One Low‑Risk Module)
Convert exactly one small module to use the adapter. Update only its tests.

**Prompt:**  
> Replace direct `ta` imports in one small module with the adapter. Show a single diff (≤50 lines) and minimal test changes. List any expected failures and propose the smallest follow‑up patch to fix them.

---

### Phase 4 — Fix Tests (Naming/Warmup)
Common causes of failures:
- Column name changes (`EMA_14` vs old names)
- Initial NaNs (warmup) count differences
- Minor numeric drift

**Tactics:**
- Normalize names in the adapter to match old expectations.
- Use `pytest.approx(abs=1e-9, rel=1e-7)` for floats.
- Add a helper to align indexes and drop initial NaNs before assertions.

**Prompt:**  
> Provide a focused diff that adjusts only the pilot module’s tests for naming/warmup/tolerance. Keep changes minimal.

---

### Phase 5 — Rollout Loop (Repeat per Module)
Repeat Phase 3–4 for one additional module at a time.

**Prompt (re‑usable):**  
> Repeat the swap for **one additional module**: use the adapter; keep the diff ≤50 lines; update targeted tests; record new edge cases and update the mapping doc; propose the next module and list its risks.

---

### Phase 6 — Enforce “No Direct `ta` Imports”
Add a small pre‑commit hook or CI grep to block `from ta ...` and `import ta` outside the adapter.

**Prompt:**  
> Add a tiny pre‑commit hook (or CI check) that fails if direct `ta` imports appear outside the adapter. Provide the smallest snippet and a short README note.

---

### Phase 7 — Performance & Parity Spot‑Checks
Add a mini script/notebook to compare SMA/RSI/ATR parity and timing on a large DataFrame. Trim warmup before comparing max/mean absolute differences.

**Prompt:**  
> Provide a small script (or notebook outline) to benchmark `ta` vs adapter‑backed `pandas_ta` on 1M rows for SMA/RSI/ATR, reporting timing and max/mean abs diffs after warmup.

---

### Phase 8 — Optional Decommission of Adapter
Once all modules use the adapter and tests are stable, optionally inline `pandas_ta` calls and remove the adapter.

**Prompt:**  
> Propose a tiny example diff showing how to safely inline one adapter function with direct `pandas_ta` calls, and a checklist to delete the adapter when everything is green.

---

## Add‑On Snippets for Token Control

**Context diet (prepend as needed):**  
> Only open or quote files required for this step. Summarize long files. If a file exceeds 400 lines, show diffs for the **smallest slice** necessary.

**Diff‑only mode:**  
> Respond with **diff only** plus a 3–5 line rationale. No large code dumps.

**Checkpoint:**  
> Stop after the patch and ask “Ready for next step?” Do not proceed further.

---

## Common Pitfalls & Notes
- Parameter names (`window`→`length`) and EMA `adjust` default differences.
- `pandas_ta` auto‑names columns (e.g., `EMA_14`); standardize names in the adapter.
- Warmup NaNs: account for them in tests (drop/align or tolerant asserts).
- Choose one style (`df.ta.*` chaining **or** functional API) and hide it behind the adapter.
- Keep PRs small; resist converting multiple modules at once.

---

## Quick Checklist
- [ ] Mapping table drafted & reviewed  
- [ ] Adapter scaffold merged with tiny tests  
- [ ] Pilot module migrated & tests adjusted  
- [ ] Pre‑commit/CI rule forbidding direct `ta` imports  
- [ ] Rollout completed module‑by‑module  
- [ ] Optional: parity benchmarks run & documented  
- [ ] Optional: adapter decommissioned

---

**Good luck—small steps win big migrations.**
