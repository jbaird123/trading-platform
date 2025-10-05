# Exception Handling Policy

**Last Updated:** 2025-10-05
**Status:** Active

## ⚠️ CRITICAL PRINCIPLE: FAIL FAST BY DEFAULT ⚠️

### Golden Rule

**When in doubt, FAIL LOUDLY rather than log/warn.**

This is the foundational rule for all exception handling in this codebase. If you cannot prove with 100% certainty that catching an exception is safe, you MUST let it propagate.

---

## Core Principles

### 1. Default Action: Let Exceptions Propagate

The correct default behavior is to **not catch exceptions** and let them propagate to the caller. This ensures:
- Bugs are discovered immediately in development
- Users see clear error messages rather than silent corruption
- Stack traces provide complete debugging information
- No uncertainty about system state after an error

### 2. Burden of Proof

**The developer must PROVE it is safe to catch an exception.**

Before adding a `try/except` block, you must answer these three questions with 100% certainty:

1. **"Can the system produce correct results without this feature?"**
2. **"Is there any scenario where hiding this error causes incorrect behavior?"**
3. **"Would a user prefer a clear error over silent degradation?"**

If the answer to #1 is "uncertain" or "no" → **FAIL FAST**
If the answer to #2 is "yes" or "uncertain" → **FAIL FAST**
If the answer to #3 is "yes" or "uncertain" → **FAIL FAST**

### 3. When Exception Catching is Allowed

Exception catching with logging is ONLY allowed when you can prove ALL of the following:

✅ **Complete Certainty:** System produces correct results without this feature
✅ **No Side Effects:** Failure cannot cause incorrect behavior elsewhere
✅ **Graceful Degradation:** Clear fallback behavior exists
✅ **User Preference:** User would prefer continuation over error
✅ **Visibility:** Failure is logged appropriately

---

## Examples of Correct Exception Handling

### ✅ SAFE TO CATCH AND LOG

These are PROVED safe because the system works perfectly without them:

#### Example 1: Git Commit Hash (Metadata)
```python
def _get_git_commit() -> str | None:
    """Get git commit hash for provenance tracking.

    Returns None if git is unavailable - system works fine without it.
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode("ascii").strip()
    except Exception as e:
        logger.debug(f"Git commit hash unavailable: {e}")
        return None  # Metadata only, brief.json complete without it
```

**Why safe:** Git hash is metadata for provenance. Brief.json contains all analysis results. System is fully functional without it.

#### Example 2: Chart Generation (Fallback Exists)
```python
try:
    generate_interactive_chart(run_path, df, trades)
except Exception as e:
    logger.warning(f"Chart generation failed: {e}")
    # System continues - users have complete text reports and brief.json
```

**Why safe:** Charts are visualization convenience. All data exists in brief.json and CSV exports. User can analyze results without charts.

#### Example 3: Optional Export Files
```python
try:
    df.to_parquet(run_path / "processed_data.parquet")
except Exception as e:
    logger.warning(f"Failed to save processed_data.parquet: {e}")
    # File is for AI Lab post-analysis, not required for backtest
```

**Why safe:** Parquet file is convenience export. Source data exists, backtest results are complete.

---

### ❌ MUST FAIL FAST

These MUST propagate exceptions because we cannot prove safety:

#### Example 1: Strategy Compilation
```python
# WRONG - silently degrading
try:
    strat = compile_strategy(strat_cfg)
except Exception as e:
    logger.error(f"Strategy compilation failed: {e}")
    strat = None  # ❌ What happens downstream with None?

# CORRECT - fail fast
strat = compile_strategy(strat_cfg)
# Let exception propagate - invalid strategy cannot proceed
```

**Why must fail:** Cannot prove downstream code handles None safely. Strategy is core requirement.

#### Example 2: Data Loading
```python
# WRONG - potentially loading partial data
try:
    df = load_market_data(symbol, start, end)
except Exception as e:
    logger.error(f"Data load failed: {e}")
    df = pd.DataFrame()  # ❌ Empty DataFrame causes incorrect results

# CORRECT - fail fast
df = load_market_data(symbol, start, end)
# Let exception propagate - cannot backtest without data
```

**Why must fail:** Cannot prove empty DataFrame won't corrupt results. Data is fundamental requirement.

#### Example 3: User-Requested Analysis
```python
# WRONG - user explicitly requested Monte Carlo
try:
    mc_results = monte_carlo_resimulation(df, cfg, trials=1000)
except Exception as e:
    logger.error(f"Monte Carlo failed: {e}")
    mc_results = None  # ❌ User expects MC results, gets silent failure

# CORRECT - fail fast
mc_results = monte_carlo_resimulation(df, cfg, trials=1000)
# Let exception propagate - user requested this, failure should be visible
```

**Why must fail:** User explicitly requested this analysis. Incomplete results are misleading.

#### Example 4: Feature Calculation in Strategy
```python
# WRONG - NaN propagation uncertain
try:
    df['rsi'] = compute_rsi(df['close'], length=14)
except Exception as e:
    logger.warning(f"RSI calculation failed: {e}")
    df['rsi'] = np.nan  # ❌ Does NaN break downstream logic?

# CORRECT - fail fast
df['rsi'] = compute_rsi(df['close'], length=14)
# Let exception propagate - cannot prove NaN handling is safe
```

**Why must fail:** Cannot prove NaN won't cause incorrect signals or crashes downstream.

---

## Exception Handling Rules

### Rule 1: Bare `except:` is FORBIDDEN

```python
# ❌ NEVER DO THIS
try:
    do_something()
except:  # Catches KeyboardInterrupt, SystemExit, etc.
    pass

# ✅ At minimum, catch Exception
try:
    do_something()
except Exception as e:
    logger.error(f"Failed: {e}")
    raise  # Re-raise after logging
```

### Rule 2: `except Exception:` Requires Justification

Every `except Exception:` block MUST have:
- Logging at appropriate level (error/warning/debug)
- Comment explaining why catching is safe
- Or re-raise after logging

```python
# ✅ GOOD - logged and justified
try:
    save_chart(path)
except Exception as e:
    logger.warning(f"Chart save failed: {e}")
    # Safe: charts are optional, data exists in brief.json

# ✅ GOOD - logged and re-raised
try:
    result = critical_operation()
except Exception as e:
    logger.error(f"Critical operation failed: {e}", exc_info=True)
    raise  # Re-raise to fail fast

# ❌ BAD - no logging, no justification
try:
    do_something()
except Exception:
    pass
```

### Rule 3: Silent `pass` is FORBIDDEN

```python
# ❌ NEVER DO THIS
try:
    optional_feature()
except Exception:
    pass  # Silent failure

# ✅ DO THIS
try:
    optional_feature()
except Exception as e:
    logger.warning(f"Optional feature failed: {e}")
    # Continues - feature proved optional
```

### Rule 4: Specific Exceptions When Possible

Catch specific exceptions when you know what can go wrong:

```python
# ✅ BETTER - specific exceptions
try:
    with open(path) as f:
        data = json.load(f)
except FileNotFoundError:
    logger.error(f"Config file not found: {path}")
    raise  # User needs to provide config
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON in {path}: {e}")
    raise  # User needs to fix config

# ⚠️ ACCEPTABLE - when truly uncertain what can fail
try:
    complex_third_party_library_call()
except Exception as e:
    logger.error(f"Library call failed: {e}", exc_info=True)
    raise
```

---

## Logging Levels

Use appropriate logging levels:

### `logger.debug()` - Non-issues
- Missing optional metadata (git hash)
- Cache misses
- Fallback behavior that's expected

### `logger.warning()` - Degraded functionality
- Optional feature failures (charts, exports)
- Graceful degradation with fallback
- User should know but system continues

### `logger.error()` - Serious problems
- User-requested features failing
- Unexpected conditions
- Just before re-raising exception

### `logger.exception()` - Critical failures
- Unhandled exceptions in top-level handlers
- Includes full traceback automatically

```python
# Example usage
try:
    run_backtest(config)
except Exception as e:
    logger.exception("Backtest failed")  # Auto-includes traceback
    raise
```

---

## Common Patterns

### Pattern 1: Optional Feature with Logging

```python
def save_optional_file(path: Path, data: pd.DataFrame) -> None:
    """Save optional export file.

    Logs warning on failure but does not raise - file is convenience only.
    """
    try:
        data.to_parquet(path)
        logger.debug(f"Saved {path}")
    except Exception as e:
        logger.warning(f"Failed to save {path}: {e}")
        # Continue - file is optional, data exists elsewhere
```

### Pattern 2: Required Operation

```python
def load_strategy(path: Path) -> Strategy:
    """Load strategy from file.

    Raises exception on failure - strategy is required to proceed.
    """
    # No try/except - let FileNotFoundError/ValidationError propagate
    with open(path) as f:
        config = yaml.safe_load(f)

    return compile_strategy(config)  # Let compilation errors propagate
```

### Pattern 3: Log and Re-raise

```python
def critical_with_context(data: pd.DataFrame) -> Result:
    """Critical operation that must succeed.

    Logs context before re-raising to aid debugging.
    """
    try:
        return complex_operation(data)
    except Exception as e:
        logger.error(
            f"Operation failed on data with shape {data.shape}: {e}",
            exc_info=True
        )
        raise  # Re-raise to fail fast with added context
```

### Pattern 4: Cleanup Before Re-raise

```python
def operation_with_resources():
    """Operation with resource cleanup.

    Uses try/finally for cleanup, lets exceptions propagate.
    """
    resource = acquire_resource()
    try:
        return process(resource)
    finally:
        resource.cleanup()  # Always cleanup, even on exception
        # Exception still propagates after cleanup
```

---

## Testing Exception Handling

Every exception handler must have tests:

### Test 1: Verify Optional Failures are Logged
```python
def test_optional_feature_failure_logged(caplog):
    """Ensure optional feature failures log warnings."""
    with patch('module.save_file') as mock_save:
        mock_save.side_effect = IOError("Disk full")

        result = process_data()  # Should continue despite failure

        assert "Failed to save" in caplog.text
        assert result is not None  # Processing completed
```

### Test 2: Verify Required Operations Fail Fast
```python
def test_strategy_load_failure_propagates():
    """Ensure strategy load failures raise exceptions."""
    with pytest.raises(FileNotFoundError):
        load_strategy(Path("nonexistent.yaml"))

    # No silent None return, no degraded state
```

### Test 3: Verify Error Context is Logged
```python
def test_error_context_logged(caplog):
    """Ensure errors log helpful context."""
    with pytest.raises(ValueError):
        with caplog.at_level(logging.ERROR):
            process_invalid_data(bad_df)

    assert "shape" in caplog.text  # Context logged
    assert "ValueError" in caplog.text  # Exception type logged
```

---

## Code Review Checklist

When reviewing exception handling:

- [ ] Is there a `try/except` block? (If no, good - fail fast by default)
- [ ] If yes, is the exception logged? (Required)
- [ ] Is there a comment justifying why catching is safe? (Required)
- [ ] Can you prove the system works correctly without this feature? (Must prove)
- [ ] Is there a test for the exception path? (Required)
- [ ] Does the test verify logging occurs? (Required)
- [ ] Is the exception specific (e.g., FileNotFoundError) or generic (Exception)?
- [ ] If generic Exception, is there a comment explaining why?
- [ ] Does the error message include helpful context?
- [ ] Would a user prefer this behavior over a clear error?

---

## Rationale

### Why "Fail Fast" is Critical

Silent failures cause bugs that are **extremely difficult to diagnose**:

1. **Delayed Discovery:** Bug manifests far from root cause
2. **Data Corruption:** Silent failures can corrupt results
3. **False Confidence:** User trusts incomplete/incorrect results
4. **Debugging Hell:** No stack trace, no clear error, just wrong output
5. **Production Incidents:** Issues slip to production undetected

### Why Defensive Programming is Dangerous

Common anti-patterns to avoid:

```python
# ❌ "Just in case" exception handling
try:
    value = config.get("setting")
except:
    value = default  # What if config.get() never raises?
    # This hides typos, missing keys, actual bugs

# ❌ "Make it work" exception handling
try:
    return calculate_result(data)
except:
    return None  # Hides calculation errors, corrupts downstream

# ❌ "I'll handle it later" exception handling
try:
    important_operation()
except Exception as e:
    # TODO: handle this properly
    pass  # Famous last words
```

### The Cost of Silent Failures

Real example from this codebase audit:
- Monte Carlo analysis silently failing → users trust incomplete results
- Data loading returning empty DataFrame → backtest runs on no data
- Feature calculation failing → NaN propagates, breaks signals

Each of these would be **immediately obvious** with fail-fast approach.

---

## Enforcement

### Linting Rules

The following linting rules are enforced:

1. No bare `except:` clauses (E722)
2. Warning on `except Exception:` without subsequent logging
3. Warning on `pass` in exception handlers without explanatory comment

### Code Review

All PRs with exception handling changes require:
1. Explicit justification in PR description
2. Tests verifying exception behavior
3. Approval from two reviewers

### Strict Mode

For development, set `STRICT_MODE=1` environment variable to convert all optional feature failures into exceptions. This helps catch issues early.

---

## Summary

**Default:** Let exceptions propagate (fail fast)

**Catch only when:** You can PROVE with 100% certainty that:
1. System produces correct results without the feature
2. Failure cannot cause incorrect behavior elsewhere
3. Clear fallback/degradation path exists
4. User prefers continuation over clear error
5. Failure is logged appropriately

**When in doubt:** FAIL FAST

---

## References

- [Task List: Fix Defensive Programming Anti-Patterns](../code_tasks/fix_defensive_programming_antipatterns_RISK_ORDERED.md)
- [Testing Guide: Error Path Testing](../testing_guide.md)
- Martin Fowler: "Fail Fast" principle
- Eric Lippert: "Vexing Exceptions"

---

**This policy is mandatory for all code in this repository.**
