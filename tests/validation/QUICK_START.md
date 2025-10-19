# Golden Validation Framework - Quick Start

## Current Status

**✅ COMPLETED:**
- Analyzer registry framework (`analyzers/__init__.py`)
- Generic IndicatorStopAnalyzer (`analyzers/indicator_stop.py`)
- Implementation tracking documents

**⏳ REMAINING (~4.5 hours one-time work):**
- Complete TrailingStopAnalyzer refactor (1 hour)
- Documentation & automation tools (3 hours)
- Testing & verification (30 min)

## What This Framework Does

Reduces adding a new strategy test from **30+ minutes** to **5 minutes**.

**Before:**
- Copy files manually
- Figure out what to change
- Debug PineScript exports
- Manually verify data quality
- Hope you didn't miss something

**After:**
```bash
# 1. Generate (30 sec)
python tests/validation/create_new_strategy_test.py \\
    --name "ema_crossover/2atr_stop" \\
    --exit-mechanisms "indicator_stop" \\
    --indicator-type "atr" \\
    --indicator-params '{"length": 14}' \\
    --stop-multiplier 2.0

# 2. Modify PineScript (2 min)
# - Follow PINESCRIPT_MODIFICATIONS.md
# - Copy snippet from templates/

# 3. Export from TradingView (2 min)
# - Checklist printed by generator

# 4. Validate (30 sec)
python tests/validation/validate_export.py ema_crossover/2atr_stop

# 5. Test (30 sec)
pytest -m validation tests/validation/test_strategy_validation.py

# 6. Commit (30 sec)
dvc add data/dvc/golden/strategies/ema_crossover/2atr_stop
git add ... && git commit
```

**Total: ~6 minutes**

## Next Steps to Complete

See **`IMPLEMENTATION_GUIDE.md`** for detailed step-by-step instructions.

**Summary:**
1. **Phase 1** (1 hr): Add `@register_analyzer` to TrailingStopAnalyzer
2. **Phase 2** (3 hr): Create README, templates, validators, scripts
3. **Phase 3** (30 min): Test with ATR example

## Key Files Created

| File | Purpose | Status |
|------|---------|--------|
| `analyzers/__init__.py` | Registry pattern | ✅ Done |
| `analyzers/indicator_stop.py` | ATR/BB/KC stops | ✅ Done |
| `analyzers/trailing_stop.py` | Moved from root | ⏳ Needs decorator |
| `IMPLEMENTATION_GUIDE.md` | Step-by-step instructions | ✅ Done |
| `IMPLEMENTATION_STATUS.md` | Progress tracker | ✅ Done |

## Design Highlights

### 1. Pluggable Analyzers
```python
@register_analyzer("indicator_stop")
class IndicatorStopAnalyzer(AmbiguityAnalyzer):
    @classmethod
    def from_metadata(cls, metadata: dict):
        # Auto-configured from metadata.json
        ...
```

### 2. Metadata-Driven Configuration
```json
{
  "exit_mechanisms": ["indicator_stop"],
  "indicator_stop_type": "atr",
  "indicator_stop_params": {"length": 14},
  "stop_distance_multiplier": 2.0
}
```

### 3. Automatic Discovery
No need to manually add strategies to test parametrization - they're auto-discovered from DVC data.

### 4. Early Validation
Catch export errors BEFORE running tests:
- Missing volume column
- Wrong timezone (Azores vs Reykjavik)
- Missing warmup data
- Invalid metadata

### 5. Reusable Templates
PineScript snippets with:
- Mandatory strategy settings
- Volume requirement
- Common patterns (ATR stop, fixed SL+TP, etc.)

## Benefits

**For You:**
- 5-minute workflow instead of 30+
- Fewer errors (automated validation)
- Consistent approach (templates)
- Easy to maintain (no duplication)

**For the Codebase:**
- Extensible (new indicators = zero code changes)
- Testable (each analyzer independent)
- Documented (README + guide)
- Future-proof (registry pattern)

## Questions?

1. Read `IMPLEMENTATION_GUIDE.md` for detailed instructions
2. Check `IMPLEMENTATION_STATUS.md` for current progress
3. Review `analyzers/indicator_stop.py` for example implementation
4. Run existing tests to verify nothing broke

## Ready to Continue?

Start with **Phase 1, Step 1.1** in `IMPLEMENTATION_GUIDE.md`!
