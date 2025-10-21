# REM Configuration V2 Migration Guide

## Overview

The REM (Risk and Exit Manager) configuration format has been updated to Version 2 to provide:
- **Strict validation** using Pydantic models
- **Explicit type discriminators** for clarity
- **Indicator whitelisting** to prevent using unsupported indicators
- **Clear error messages** when configs contain typos or invalid values

**Breaking Change**: Old format configs will continue to work temporarily for backward compatibility, but will not be validated. Migrate to the new format to benefit from strict validation.

## Breaking Changes

### Type Field Required

All stop-loss and take-profit rules now require a `type` field to discriminate between different rule types:
- `"fixed_pips"` - Fixed pip-based distance
- `"indicator"` - Indicator-based dynamic distance

### Indicator Parameters Restructured

Indicator-based stops now use a nested `params` object instead of flat fields.

### Field Renames

| Old Field | New Field | Notes |
|-----------|-----------|-------|
| `atr_multiple` | `params.multiplier` | Under indicator type |
| `atr_length` | `params.length` | Under indicator type |
| `price_offset` | `pips` | Converted to pip units |

## Migration Examples

### Example 1: Fixed Pip Stop-Loss

**Old Format (DEPRECATED):**
```yaml
rem:
  stop_loss:
    price_offset: 0.0020  # 20 pips for EUR/USD
```

**New Format:**
```yaml
name: "Fixed_20pip_Stop"
version: "2.0"

stop_loss:
  type: "fixed_pips"
  pips: 20
```

**Changes:**
- ✅ Added `type: "fixed_pips"` discriminator
- ✅ Replaced `price_offset: 0.0020` with `pips: 20`
- ✅ Added optional `name` and `version` metadata
- ✅ Removed top-level `rem:` wrapper

### Example 2: Fixed Pip Stop + Take-Profit

**Old Format (DEPRECATED):**
```yaml
rem:
  stop_loss:
    price_offset: 0.0020  # 20 pips
  take_profit:
    price_offset: 0.0040  # 40 pips
```

**New Format:**
```yaml
name: "Fixed_20pip_Stop_40pip_TP"
version: "2.0"

stop_loss:
  type: "fixed_pips"
  pips: 20

take_profit:
  type: "fixed_pips"
  pips: 40
```

### Example 3: ATR-Based Stop-Loss

**Old Format (DEPRECATED):**
```yaml
rem:
  stop_loss:
    atr_multiple: 2.0
    atr_length: 14
```

**New Format:**
```yaml
name: "ATR_2x_Stop"
version: "2.0"

stop_loss:
  type: "indicator"
  indicator: "atr"
  params:
    length: 14
    multiplier: 2.0
```

**Changes:**
- ✅ Added `type: "indicator"` discriminator
- ✅ Added explicit `indicator: "atr"` field
- ✅ Moved parameters under nested `params` object
- ✅ Renamed `atr_multiple` → `multiplier`
- ✅ Renamed `atr_length` → `length`

### Example 4: Mixed Stop/TP Types

**New Format (not possible in old format):**
```yaml
name: "ATR_Stop_FixedTP"
version: "2.0"

stop_loss:
  type: "indicator"
  indicator: "atr"
  params:
    multiplier: 2.0
    length: 14

take_profit:
  type: "fixed_pips"
  pips: 40
```

This demonstrates mixing indicator-based stop with fixed pip take-profit.

## Whitelisted Indicators

Only the following indicators are permitted for REM stop-loss/take-profit calculations:

| Indicator | Type | Required Params | Optional Params | Default Values |
|-----------|------|-----------------|-----------------|----------------|
| `atr` | Volatility | `multiplier` (float > 0) | `length` (int ≥ 1) | `length: 14` |
| `bollinger` | Volatility | - | `length` (int ≥ 1), `num_std` (float > 0) | `length: 20`, `num_std: 2.0` |
| `keltner` | Volatility | - | `length`, `atr_length`, `multiplier` | `length: 20`, `atr_length: 10`, `multiplier: 2.0` |

**Note**: Bollinger and Keltner are in the schema but not yet implemented. Only ATR is currently available.

## Validation Errors

The new format provides clear validation errors:

### Error: Missing Type Field

```
ValidationError: 1 validation error for REMConfig
stop_loss
  Unable to extract tag using discriminator 'type'
```

**Fix**: Add `type: "fixed_pips"` or `type: "indicator"` field.

### Error: Unknown Indicator

```
ValidationError: 1 validation error for REMConfig
stop_loss.indicator
  Input should be 'atr', 'bollinger' or 'keltner'
```

**Fix**: Only use whitelisted indicators. RSI, MACD, etc. are not allowed for stops.

### Error: Extra Field

```
ValidationError: 1 validation error for REMConfig
stop_loss.unknown_field
  Extra inputs are not permitted
```

**Fix**: Remove the unknown field. Check spelling.

### Error: Missing Required Parameter

```
ValidationError: 1 validation error for REMConfig
stop_loss.params.multiplier
  Field required
```

**Fix**: Add the required `multiplier` parameter for ATR.

### Error: Invalid Value

```
ValidationError: 1 validation error for REMConfig
stop_loss.pips
  Input should be greater than 0
```

**Fix**: Ensure `pips` value is positive (> 0).

## Migration Steps

### Step 1: Identify Current Format

Check your `rem.yaml` file:
- If it has fields like `atr_multiple`, `price_offset` → Old format
- If it has `type: "fixed_pips"` or `type: "indicator"` → New format

### Step 2: Choose Target Type

Decide which type to use:
- **Fixed pips**: Use `type: "fixed_pips"` for constant pip distance
- **ATR indicator**: Use `type: "indicator", indicator: "atr"` for volatility-adjusted stops

### Step 3: Convert Fields

Use the mapping tables above to convert field names:
- `price_offset` → calculate pips, use `pips` field
- `atr_multiple` → `params.multiplier`
- `atr_length` → `params.length`

### Step 4: Add Required Fields

Ensure all required fields are present:
- `type` field (always required)
- `indicator` field (if using indicator type)
- `params` object (if using indicator type)
- Required params within `params` (e.g., `multiplier` for ATR)

### Step 5: Validate

Run your config through validation:
```python
from trading_platform.risk_manager import REMConfig
import yaml

with open('rem.yaml') as f:
    data = yaml.safe_load(f)

config = REMConfig(**data)  # Will raise ValidationError if invalid
```

## Advanced Features (Not Covered)

The following features use advanced REM configurations and are NOT part of the basic REM schema:
- `trailing_stop` - Use DynamicREM instead
- `reference_price` - Contextual exit rules (legacy, not in new schema)

These are now modeled separately via `DynamicREMConfig` and related Pydantic models.

## Backward Compatibility

The `RiskExitManager` class maintains backward compatibility:
- **Old format configs** (without `type` field) bypass validation
- **New format configs** (with `type` field) are validated via Pydantic
- **Advanced features** (trailing_stop, reference_price) bypass validation

This allows gradual migration without breaking existing configs.

## Testing Your Migration

After migrating, test your config:

```bash
# Run validation tests
poetry run pytest tests/risk_manager/test_rem_schema.py -v

# Run your strategy with the new config
poetry run python -m trading_platform.cli backtest \
  --config path/to/your/config.yaml
```

## Questions?

- Generate the JSON schema on demand with `REMConfig.model_json_schema()` if needed.
- See [models.py](../../src/trading_platform/risk_manager/models.py) for Pydantic model implementation
- See [golden strategy configs](../../configs/golden_strategies/ema_crossover/) for examples
