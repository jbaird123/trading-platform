# Analyzer Pattern Guide

## Overview

This guide documents the analyzer registry pattern used for exit mechanism validation. This is a reference for understanding how analyzers work and how to add new exit mechanisms (ATR stops, Bollinger stops, etc.).

**Note**: For adding a new strategy test, see [README.md](README.md) instead.

## What's Already Done ✅

1. **Analyzer Registry** (`tests/validation/analyzers/__init__.py`)
   - Registry pattern implemented
   - Factory function: `create_analyzer_for_strategy(metadata)`
   - Decorator: `@register_analyzer(name)`

2. **Generic Indicator Stop Analyzer** (`tests/validation/analyzers/indicator_stop.py`)
   - Works for ATR, Bollinger, Keltner, any future indicators
   - Registered as "indicator_stop"
   - Configurable via metadata.json

3. **File Organization**
   - Created `tests/validation/analyzers/` package
   - Moved `trailing_stop_discrepancy_analyzer.py` → `analyzers/trailing_stop.py`

## Remaining Work

### PHASE 1: Complete Analyzer Refactor (1 hour)

#### Step 1.1: Update TrailingStopAnalyzer (15 min)

**File**: `tests/validation/analyzers/trailing_stop.py`

**Add at top after imports:**
```python
from tests.validation.analyzers import register_analyzer
```

**Add decorator before class definition:**
```python
@register_analyzer("trailing_stop")
class TrailingStopDiscrepancyAnalyzer:
```

**Add classmethod after `__init__` (around line 77):**
```python
    @classmethod
    def from_metadata(cls, metadata: dict):
        """Create analyzer from strategy metadata.

        Expected metadata fields:
        - "trailing_stop_pips": 20  # Pips value
        - "take_profit_pips": 15    # Optional

        Args:
            metadata: Strategy metadata dictionary

        Returns:
            TrailingStopDiscrepancyAnalyzer instance

        Raises:
            ValueError: If trailing_stop_pips missing
        """
        trailing_stop_pips = metadata.get("trailing_stop_pips")
        if trailing_stop_pips is None:
            raise ValueError(
                "trailing_stop mechanism requires 'trailing_stop_pips' in metadata"
            )

        # Convert pips to price (for EURUSD: divide by 10,000)
        trailing_stop_price = trailing_stop_pips / 10000.0

        # Optional: take_profit_pips
        take_profit_pips = metadata.get("take_profit_pips")
        take_profit_price = take_profit_pips / 10000.0 if take_profit_pips else None

        return cls(
            trailing_stop_pips=trailing_stop_price,
            take_profit_pips=take_profit_price,
            tolerance=metadata.get("price_tolerance", 1e-5)
        )
```

**Keep existing `__init__` and all other methods unchanged.**

#### Step 1.2: Update Test Imports (15 min)

**File**: `tests/validation/test_export_exit_price_comparison.py`

**Change:**
```python
# OLD
from tests.validation.trailing_stop_discrepancy_analyzer import (
    create_analyzer_for_strategy,
)

# NEW
from tests.validation.analyzers import create_analyzer_for_strategy
```

**File**: Any other files importing `trailing_stop_discrepancy_analyzer`

Run this to find them:
```bash
grep -r "trailing_stop_discrepancy_analyzer" tests/validation/
```

Update all imports to use the new path.

#### Step 1.3: Add Backward Compatibility (10 min)

**File**: `tests/validation/trailing_stop_discrepancy_analyzer.py` (new file at old location)

```python
"""Backward compatibility shim for trailing_stop_discrepancy_analyzer.

DEPRECATED: Import from tests.validation.analyzers.trailing_stop instead.

This module exists only for backward compatibility. All new code should use:
    from tests.validation.analyzers.trailing_stop import TrailingStopDiscrepancyAnalyzer
    from tests.validation.analyzers import create_analyzer_for_strategy
"""

import warnings

from tests.validation.analyzers.trailing_stop import (
    TrailingStopDiscrepancyAnalyzer,
)


def create_analyzer_for_strategy(golden_metadata: dict, tolerance: float = 0.00001):
    """Backward compatibility wrapper.

    DEPRECATED: Use tests.validation.analyzers.create_analyzer_for_strategy() instead.
    """
    warnings.warn(
        "Importing from trailing_stop_discrepancy_analyzer is deprecated. "
        "Use 'from tests.validation.analyzers import create_analyzer_for_strategy' instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Use the new registry-based factory
    from tests.validation.analyzers import create_analyzer_for_strategy as new_factory
    return new_factory(golden_metadata)


__all__ = ["TrailingStopDiscrepancyAnalyzer", "create_analyzer_for_strategy"]
```

#### Step 1.4: Test Phase 1 (10 min)

```bash
# Run existing trailing stop tests
pytest -m validation tests/validation/test_export_exit_price_comparison.py -v

# Should pass with no changes to test behavior
```

---

### PHASE 2: Documentation & Automation (3 hours)

#### Step 2.1: Create Main README (60 min)

**File**: `tests/validation/README.md`

**Content** (see full template at end of this guide)

Key sections:
- Quick Start (10-minute workflow)
- PineScript Requirements (MANDATORY settings)
- Exit Mechanism Types (trailing_stop, indicator_stop, etc.)
- TradingView Export Checklist
- Troubleshooting Guide

#### Step 2.2: Create PineScript Templates (45 min)

**Directory**: `tests/validation/pinescript_templates/`

**Create these files:**

1. `README.md` - Explains template system
2. `base_ema_crossover.pine` - Full baseline strategy with mandatory settings
3. `add_atr_stop.pine` - Snippet to add ATR stop to baseline
4. `add_fixed_stop_tp.pine` - Snippet for fixed SL+TP
5. `export_checklist.md` - Step-by-step export instructions

**Key requirement**: All templates MUST include:
```pinescript
strategy("Name",
         overlay=true,
         initial_capital=100000,
         default_qty_value=10000,
         default_qty_type=strategy.cash,
         commission_type=strategy.commission.percent,
         commission_value=0.0,
         pyramiding=1,
         process_orders_on_close=false,
         calc_on_order_fills=false,
         calc_on_every_tick=false)

// MANDATORY: Include volume
plot(volume, title="Volume", display=display.none)
```

#### Step 2.3: Create Data Validator (60 min)

**File**: `tests/validation/validators/__init__.py`
```python
"""Data validation utilities for golden test exports."""

from tests.validation.validators.data_validator import GoldenDataValidator

__all__ = ["GoldenDataValidator"]
```

**File**: `tests/validation/validators/data_validator.py`

```python
"""Validation rules for TradingView export data quality."""

import pandas as pd
from pathlib import Path

class GoldenDataValidator:
    """Validates exported TradingView data meets requirements."""

    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.data_dir = Path(f"data/dvc/golden/strategies/{strategy_name}")
        self.errors = []
        self.warnings = []

    def validate_all(self) -> tuple[bool, list[str], list[str]]:
        """Run all validation checks.

        Returns:
            (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        self._check_required_files()
        self._validate_metadata()
        self._validate_ohlcv()
        self._validate_trades()

        return (len(self.errors) == 0, self.errors, self.warnings)

    def _check_required_files(self):
        """Check all required files exist."""
        required = ["metadata.json", "ohlcv.csv", "trades.csv"]

        for filename in required:
            if not (self.data_dir / filename).exists():
                self.errors.append(f"Missing required file: {filename}")

    def _validate_metadata(self):
        """Validate metadata.json structure."""
        if not (self.data_dir / "metadata.json").exists():
            return

        import json
        with open(self.data_dir / "metadata.json") as f:
            metadata = json.load(f)

        # Required fields
        required = ["strategy_name", "date_range", "exit_mechanisms"]
        for field in required:
            if field not in metadata:
                self.errors.append(f"metadata.json missing: {field}")

        # Validate exit mechanism params
        mechanisms = metadata.get("exit_mechanisms", [])

        if "trailing_stop" in mechanisms and "trailing_stop_pips" not in metadata:
            self.errors.append("trailing_stop requires 'trailing_stop_pips'")

        if "indicator_stop" in mechanisms:
            if "indicator_stop_type" not in metadata:
                self.errors.append("indicator_stop requires 'indicator_stop_type'")
            if "stop_distance_multiplier" not in metadata:
                self.warnings.append("indicator_stop should specify 'stop_distance_multiplier'")

    def _validate_ohlcv(self):
        """Validate OHLCV data quality."""
        if not (self.data_dir / "ohlcv.csv").exists():
            return

        df = pd.read_csv(self.data_dir / "ohlcv.csv")

        # CRITICAL: Volume column
        if "volume" not in df.columns:
            self.errors.append(
                "CRITICAL: ohlcv.csv MUST include 'volume' column!\\n"
                "Add to PineScript: plot(volume, title='Volume', display=display.none)"
            )

        # CRITICAL: UTC timezone
        if "time" in df.columns:
            sample = str(df["time"].iloc[0])

            if "-01:00" in sample:
                self.errors.append(
                    "CRITICAL: Using UTC (Azores) timezone with DST offsets!\\n"
                    "FIX: TradingView → Settings → Timezone → 'UTC (Reykjavik)'"
                )

            if not sample.endswith("Z"):
                self.errors.append(
                    f"Timestamps must end with 'Z'. Got: {sample}\\n"
                    "FIX: Set timezone to 'UTC (Reykjavik)'"
                )

        # Check warmup coverage
        df["time"] = pd.to_datetime(df["time"], utc=True)
        min_date = df["time"].min()
        warmup_required = pd.Timestamp("2022-12-01", tz="UTC")

        if min_date > warmup_required:
            self.warnings.append(
                f"Data starts {min_date.date()}, warmup needs {warmup_required.date()}"
            )

    def _validate_trades(self):
        """Validate trades.csv structure."""
        if not (self.data_dir / "trades.csv").exists():
            return

        df = pd.read_csv(self.data_dir / "trades.csv")

        required = ["Trade #", "Type", "Signal", "Date/Time", "Price USD"]
        for col in required:
            if col not in df.columns:
                self.errors.append(f"trades.csv missing: {col}")

    def print_report(self):
        """Print validation report."""
        print("\\n" + "="*80)
        print(f"VALIDATION: {self.strategy_name}")
        print("="*80)

        if self.errors:
            print(f"\\n❌ ERRORS ({len(self.errors)}):")
            for i, err in enumerate(self.errors, 1):
                print(f"  {i}. {err}")

        if self.warnings:
            print(f"\\n⚠️  WARNINGS ({len(self.warnings)}):")
            for i, warn in enumerate(self.warnings, 1):
                print(f"  {i}. {warn}")

        if not self.errors and not self.warnings:
            print("\\n✅ ALL CHECKS PASSED")

        print("="*80 + "\\n")
```

#### Step 2.4: Create Validation Script (15 min)

**File**: `tests/validation/validate_export.py`

```python
#!/usr/bin/env python3
"""Validate TradingView export before running tests.

Usage:
    python tests/validation/validate_export.py ema_crossover/2atr_stop
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.validation.validators import GoldenDataValidator

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_export.py <strategy_name>")
        print("Example: python validate_export.py ema_crossover/2atr_stop")
        sys.exit(1)

    validator = GoldenDataValidator(sys.argv[1])
    is_valid, errors, warnings = validator.validate_all()
    validator.print_report()

    sys.exit(0 if is_valid else 1)
```

Make executable:
```bash
chmod +x tests/validation/validate_export.py
```

#### Step 2.5: Create Strategy Generator Script (45 min)

**File**: `tests/validation/create_new_strategy_test.py`

```python
#!/usr/bin/env python3
"""Create new golden strategy test from baseline.

Usage:
    python tests/validation/create_new_strategy_test.py \\
        --name "ema_crossover/2atr_stop" \\
        --exit-mechanisms "indicator_stop" \\
        --indicator-type "atr" \\
        --indicator-params '{"length": 14}' \\
        --stop-multiplier 2.0
"""

import argparse
import json
import shutil
from pathlib import Path

def create_strategy_test(name: str, exit_mechanisms: list, **params):
    """Create new strategy test from baseline."""

    baseline = Path("configs/golden_strategies/ema_crossover/baseline")
    new_dir = Path(f"configs/golden_strategies/{name}")

    if new_dir.exists():
        raise ValueError(f"Strategy {name} already exists!")

    # Copy baseline
    shutil.copytree(baseline, new_dir)
    print(f"✓ Copied baseline to {new_dir}")

    # Update metadata.json
    metadata_path = new_dir / "metadata.json"
    with open(metadata_path) as f:
        metadata = json.load(f)

    metadata["strategy_name"] = name
    metadata["exit_mechanisms"] = exit_mechanisms
    metadata.update(params)

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"✓ Updated metadata.json")

    # Create PineScript guide
    guide = new_dir / "PINESCRIPT_MODIFICATIONS.md"
    with open(guide, "w") as f:
        f.write(f"# PineScript Modifications for {name}\\n\\n")
        f.write("## ⚠️  MANDATORY REQUIREMENTS\\n\\n")
        f.write("1. **Include Volume:**\\n")
        f.write("   ```pinescript\\n")
        f.write("   plot(volume, title=\\"Volume\\", display=display.none)\\n")
        f.write("   ```\\n\\n")
        f.write("2. **Use Standard Settings:**\\n")
        f.write("   Copy from: `pinescript_templates/base_ema_crossover.pine`\\n\\n")

        if "indicator_stop" in exit_mechanisms:
            ind_type = params.get("indicator_stop_type", "indicator")
            f.write(f"## Adding {ind_type.upper()}-Based Stop\\n\\n")
            f.write(f"See: `pinescript_templates/add_{ind_type}_stop.pine`\\n")

    print(f"✓ Created {guide.name}")

    # Print checklist
    print("\\n" + "="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Modify PineScript (see PINESCRIPT_MODIFICATIONS.md)")
    print("2. Export from TradingView:")
    print("   ☐ Timezone: UTC (Reykjavik)")
    print("   ☐ Date range: 2022-12-01 to 2024-12-31")
    print("   ☐ Volume included in indicators")
    print("3. Validate: python tests/validation/validate_export.py " + name)
    print("4. Test: pytest -m validation tests/validation/test_strategy_validation.py")
    print("5. Commit: dvc add + git add + dvc push")
    print("="*80)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--exit-mechanisms", nargs="+", required=True)
    parser.add_argument("--indicator-type")
    parser.add_argument("--indicator-params", type=json.loads)
    parser.add_argument("--stop-multiplier", type=float)

    args = parser.parse_args()

    params = {}
    if args.indicator_type:
        params["indicator_stop_type"] = args.indicator_type
    if args.indicator_params:
        params["indicator_stop_params"] = args.indicator_params
    if args.stop_multiplier:
        params["stop_distance_multiplier"] = args.stop_multiplier

    create_strategy_test(args.name, args.exit_mechanisms, **params)
```

Make executable:
```bash
chmod +x tests/validation/create_new_strategy_test.py
```

---

### PHASE 3: Test & Document (30 min)

#### Step 3.1: Create ATR Stop Example (10 min)

```bash
# Generate scaffold
python tests/validation/create_new_strategy_test.py \\
    --name "ema_crossover/2atr_stop" \\
    --exit-mechanisms "indicator_stop" \\
    --indicator-type "atr" \\
    --indicator-params '{"length": 14}' \\
    --stop-multiplier 2.0

# Follow printed checklist
```

#### Step 3.2: Verify Workflow (10 min)

Time yourself through the complete workflow:
1. Generate strategy
2. Modify PineScript
3. Export from TradingView
4. Validate export
5. Run tests

**Target: < 10 minutes total**

#### Step 3.3: Update Documentation (10 min)

Add any learnings/issues to:
- README.md
- IMPLEMENTATION_STATUS.md
- This guide

---

## Quick Reference

### File Structure After Completion

```
tests/validation/
├── README.md                          # Main documentation
├── IMPLEMENTATION_GUIDE.md            # This file
├── IMPLEMENTATION_STATUS.md           # Progress tracker
├── analyzers/
│   ├── __init__.py                   # Registry + factory
│   ├── indicator_stop.py             # Generic indicator analyzer
│   └── trailing_stop.py              # Trailing stop analyzer
├── validators/
│   ├── __init__.py
│   └── data_validator.py             # Export validation
├── pinescript_templates/
│   ├── README.md
│   ├── base_ema_crossover.pine
│   ├── add_atr_stop.pine
│   └── export_checklist.md
├── create_new_strategy_test.py       # Generator script
├── validate_export.py                # Validation script
└── [existing test files...]
```

### Metadata.json Examples

**Trailing Stop:**
```json
{
  "strategy_name": "ema_crossover/20pip_trailing_stop",
  "exit_mechanisms": ["trailing_stop"],
  "trailing_stop_pips": 20,
  "date_range": {"start": "2023-01-01", "end": "2024-12-31"},
  "warmup_start": "2022-12-01"
}
```

**ATR Stop:**
```json
{
  "strategy_name": "ema_crossover/2atr_stop",
  "exit_mechanisms": ["indicator_stop"],
  "indicator_stop_type": "atr",
  "indicator_stop_params": {"length": 14},
  "stop_distance_multiplier": 2.0,
  "date_range": {"start": "2023-01-01", "end": "2024-12-31"},
  "warmup_start": "2022-12-01"
}
```

**Trailing Stop + TP:**
```json
{
  "strategy_name": "ema_crossover/20pip_trailing_stop_15pip_tp",
  "exit_mechanisms": ["trailing_stop"],
  "trailing_stop_pips": 20,
  "take_profit_pips": 15,
  "date_range": {"start": "2023-01-01", "end": "2024-12-31"},
  "warmup_start": "2022-12-01"
}
```

## Testing Checklist

After completing implementation, verify:

- [ ] Existing trailing stop tests pass
- [ ] Analyzer registry works
- [ ] Can create analyzer from metadata
- [ ] IndicatorStopAnalyzer categorizes ATR stops
- [ ] Data validator catches volume/timezone errors
- [ ] Generator creates correct file structure
- [ ] Validation script reports errors clearly
- [ ] Full workflow < 10 minutes
- [ ] README is clear and complete
- [ ] PineScript templates have mandatory settings

## Common Issues & Solutions

### Issue: "No analyzer registered for 'trailing_stop'"
**Solution**: Add `@register_analyzer("trailing_stop")` decorator

### Issue: "OHLCV missing volume column"
**Solution**: Add `plot(volume, ...)` to PineScript

### Issue: "Timestamps have -01:00 offset"
**Solution**: Change TradingView timezone to UTC (Reykjavik)

### Issue: "Test parametrization doesn't find new strategy"
**Solution**: Ensure metadata.json exists and is valid JSON

## Time Estimates

- Phase 1 (Analyzer Refactor): 1 hour
- Phase 2 (Documentation & Tools): 3 hours
- Phase 3 (Testing): 30 minutes

**Total: ~4.5 hours one-time investment**

**Payoff: Every new strategy test goes from 30+ min → 5 min**

---

## Need Help?

- Check `IMPLEMENTATION_STATUS.md` for current progress
- Review existing trailing stop analyzer for patterns
- Test each phase before moving to next
- Ask questions if anything is unclear!
