# Global Feature Set

## Purpose

The global feature set provides a centralized configuration for mandatory features that are **always** included in every backtest and live trading session. This ensures:

1. **Consistency**: ML models receive the same features across all strategies and runs
2. **Multi-timeframe Context**: Strategies get higher-timeframe market context automatically
3. **Simplification**: Strategies don't need to redefine common features

## Configuration Location

Global features are defined in:
```
config/features/global.yaml
```

## Namespace Separation

To prevent feature name collisions between global features and strategy-specific features, strict naming conventions are enforced via Pydantic validators:

### Global Features (config/features/global.yaml)

**MUST** have timeframe prefixes:
- **Valid**: `5min_rsi_14`, `15min_ema_9`, `1h_atr_14`, `4h_rsi`, `1d_volume_sma_20`
- **Invalid**: `rsi_14`, `ema_9`, `atr_14` (missing timeframe prefix)

**Timeframe prefix format**: `{timeframe}_{descriptor}`

Where `{timeframe}` must be one of:
- `1min_` - 1-minute
- `5min_` - 5-minute
- `15min_` - 15-minute
- `1h_` - 1-hour
- `4h_` - 4-hour
- `1d_` - 1-day

### Strategy Features (config/strategies/*.yaml)

**MUST NOT** have timeframe prefixes:
- **Valid**: `rsi`, `ema_fast`, `ema_slow`, `atr`, `bb_upper`
- **Invalid**: `1h_rsi`, `15min_ema_fast` (has timeframe prefix)

### Rationale

This naming convention ensures that features in `context_at_entry` and `context_at_exit` can never collide:
- Global features: `1h_rsi_14`, `15min_ema_9`, `1d_volume_sma_20`
- Strategy features: `rsi`, `ema_fast`, `ema_slow`

The naming convention is enforced via Pydantic validators, making it impossible to instantiate invalid configurations.

## Timeframe Filtering

Features are automatically filtered based on the strategy's `execution_timeframe`:

### Filter Rule

**Include features where**: `feature.timeframe >= execution_timeframe`

### Rationale

- **Higher timeframes provide context**: A 1-minute strategy benefits from knowing 1-hour and daily trends
- **Lower timeframes add noise**: A 1-hour strategy doesn't need 5-minute oscillations

### Examples

#### Example 1: 1-Minute Strategy
```yaml
# Execution timeframe: 1min
# Included features: ALL (m5, m15, h1, h4, d1)
# Excluded features: none
```

A 1-minute execution timeframe includes **all** higher timeframe features, providing maximum market context.

#### Example 2: 1-Hour Strategy
```yaml
# Execution timeframe: 1H
# Included features: h1, h4, d1
# Excluded features: m5, m15
```

A 1-hour execution timeframe excludes lower timeframes (5min, 15min) as they provide noisy, less-relevant signals.

#### Example 3: Features Without Timeframe
Features without an explicit `timeframe` field are always included, treated as belonging to the execution timeframe.

## Validation Rules

### Global Feature Validation (GlobalFeatureSetConfig)

Enforced in: `src/trading_platform/core/config.py`

```python
@model_validator(mode="after")
def validate_all_features_have_prefix(self):
    """Ensure all features have timeframe prefix."""
    for feature in self.features:
        FeatureConfig.model_validate(
            feature.model_dump(),
            context={"is_global": True}
        )
    return self
```

### Strategy Feature Validation (StrategyConfig)

Enforced in: `src/trading_platform/strategy/models.py`

```python
@model_validator(mode="after")
def validate_feature_names_no_timeframe_prefix(self):
    """Ensure strategy features do NOT have timeframe prefixes."""
    for feature in self.features:
        if re.match(r"^(m1|m5|m15|h1|h4|d1)_", feature.name):
            raise ValueError(
                f"Strategy features must NOT have timeframe prefix. "
                f"Found: {feature.name}"
            )
    return self
```

## Error Handling

### Missing global.yaml

If `config/features/global.yaml` does not exist, `resolve_global_features()` raises:
```python
FileNotFoundError: Global feature configuration not found at config/features/global.yaml
```

### Invalid Naming

If a global feature lacks a timeframe prefix:
```python
ValidationError: Global features must have timeframe prefix (1min_, 5min_, 15min_, 1h_, 4h_, 1d_). Got: rsi_14
```

If a strategy feature has a timeframe prefix:
```python
ValidationError: Strategy features must NOT have timeframe prefix. Found: 1h_rsi
```

### Unrecognized Timeframe

If a timeframe is not in the supported list:
```python
ValueError: Unrecognized timeframe: 30min
```

Supported timeframes: `1min`, `5min`, `15min`, `1H`, `4H`, `1D`

## Removal of contextual_features

The `contextual_features` field has been removed from `RunConfig`. All non-strategy features must now be defined in `global.yaml`.

**Before** (deprecated):
```yaml
# run_config.yaml
contextual_features:
  - name: ctx_atr
    type: ATR
    params: {length: 14}
```

**After** (required):
```yaml
# config/features/global.yaml
features:
  - name: 1h_atr_14  # Note: must have timeframe prefix
    type: ATR
    params: {length: 14}
    timeframe: "1H"
```

## Timeframe Comparison Utility

The `compare_timeframes()` utility (in `src/trading_platform/core/timeframes.py`) is used for filtering:

```python
from trading_platform.core.timeframes import compare_timeframes

compare_timeframes("1min", "1H")  # < 0 (1min is smaller)
compare_timeframes("1H", "1min")  # > 0 (1H is larger)
compare_timeframes("1H", "1H")    # == 0 (equal)
```

Timeframe ranks (in minutes):
- `1min`: 1
- `5min`: 5
- `15min`: 15
- `1H`: 60
- `4H`: 240
- `1D`: 1440

## Usage Example

### 1. Define Global Features

```yaml
# config/features/global.yaml
features:
  # Trend indicators
  - name: "1h_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "1H"

  - name: "1d_ema_50"
    type: "EMA"
    params: { "length": 50 }
    timeframe: "1D"

  # Momentum indicators
  - name: "15min_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "15min"

  - name: "1h_rsi_14"
    type: "RSI"
    params: { "length": 14 }
    timeframe: "1H"

  # Volatility indicators
  - name: "1h_atr_14"
    type: "ATR"
    params: { "length": 14 }
    timeframe: "1H"

  # Volume indicators
  - name: "1h_volume_sma_20"
    type: "SMA"
    params: { "length": 20 }
    source: "volume"
    timeframe: "1H"
```

### 2. Define Strategy (Without Timeframe Prefixes)

```yaml
# config/strategies/ema_crossover.yaml
strategy_name: "EMA Crossover"
features:
  - name: "ema_fast"  # No timeframe prefix
    type: "EMA"
    params: { "length": 9 }

  - name: "ema_slow"  # No timeframe prefix
    type: "EMA"
    params: { "length": 21 }

long_entry_rules:
  - any_of:
      - condition: "cross_above"
        left: { "ref": "ema_fast" }
        right: { "ref": "ema_slow" }
```

### 3. Features Available in Context

When this strategy runs on a **15-minute timeframe**, the following features are available in `context_at_entry`:

**From strategy** (computed on 15min data):
- `ema_fast`
- `ema_slow`

**From global** (filtered to >= 15min):
- `15min_rsi_14` (15min data, resampled)
- `1h_ema_50` (1H data, resampled)
- `1h_rsi_14` (1H data, resampled)
- `1h_atr_14` (1H data, resampled)
- `1h_volume_sma_20` (1H data, resampled)
- `1d_ema_50` (1D data, resampled)

**Excluded** (< 15min):
- None in this example

**Total features**: 8 (2 strategy + 6 global)

No name collisions because global features have `{timeframe}_` prefixes and strategy features don't.

## Integration Points

### Backtester Integration (TODO)

The backtester will use `resolve_global_features()` to load and filter features:

```python
from trading_platform.core.feature_resolver import resolve_global_features

# In backtester initialization
global_features = resolve_global_features(config.execution_timeframe)

# Compute global features on appropriate timeframes
# Merge into context_at_entry/context_at_exit
```

### Live Trading Integration (TODO)

The live trading engine will use the same `resolve_global_features()` utility to ensure backtest/live parity.

## References

- Implementation: `src/trading_platform/core/feature_resolver.py`
- Configuration model: `src/trading_platform/core/config.py` (GlobalFeatureSetConfig)
- Timeframe utilities: `src/trading_platform/core/timeframes.py`
- Tests: `tests/core/test_feature_resolver.py`, `tests/core/test_timeframes.py`
- Proposed features: `config/features/proposed_global_features.md`
