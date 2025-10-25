# ModelRegistry - Central Model Management

## Overview

`ModelRegistry` is the **central manager** for all ML models in the trading platform. It handles:

- Model registration and organization by context
- Routing predictions to the appropriate model
- Batch training from enriched data
- Model persistence (save/load)
- Lazy loading for efficiency

## Purpose

Instead of manually managing individual model files, the registry provides a unified interface for:

1. **Context-based routing**: Automatically select the right model for a given timeframe/archetype
2. **Batch operations**: Train all models at once from enriched campaign data
3. **Storage management**: Handle file system layout and naming conventions
4. **Model families**: Manage both profitability and diagnostic model families

## Architecture

### Two Model Families

The registry manages two distinct model families:

```
models/
├── profitability/          # Real-time signal filtering
│   ├── 5min_trend_following.pkl
│   ├── 15min_trend_following.pkl
│   └── ...
└── diagnostic/             # Offline regime analysis
    ├── 5min_trend_following.pkl
    ├── 15min_trend_following.pkl
    └── ...
```

Each family serves a different purpose:
- **Profitability**: Production-safe, entry-features only, binary classification
- **Diagnostic**: Offline analysis, all features including lookahead, quintile classification

### File System Layout

```
<model_dir>/
├── profitability/
│   └── <timeframe>_<archetype>.pkl
├── diagnostic/
│   └── <timeframe>_<archetype>.pkl
└── registry.json          # Metadata (future use)
```

Model keys use the format: `{timeframe}_{archetype}`

Examples:
- `5min_trend_following`
- `15min_mean_reversion`
- `1h_breakout`

## Basic Usage

### Initialization

```python
from trading_platform.ai.models import ModelRegistry

# Create registry pointing to model directory
registry = ModelRegistry(model_dir="models")
```

### Training All Models

```python
import pandas as pd

# Load enriched trades
enriched_df = pd.read_parquet("data/enriched/campaign/rich_trades.parquet")

# Train all profitability models (auto-discovers contexts)
prof_models = registry.train_all_profitability_models(
    enriched_df,
    n_estimators=100,
    random_state=42
)

print(f"Trained {len(prof_models)} profitability models")

# Save all models to disk
registry.save()
```

### Loading Models

```python
# Load all saved models
registry = ModelRegistry(model_dir="models")
registry.load()

# Check what models are available
prof_models = registry.list_models("profitability")
diag_models = registry.list_models("diagnostic")

print(f"Loaded {len(prof_models)} profitability models")
print(f"Loaded {len(diag_models)} diagnostic models")
```

### Making Predictions

```python
# Predict profitability (routes to correct model automatically)
predictions = registry.predict_profitability(
    X=new_trades_df,
    timeframe="5min",
    archetype="trend_following"
)

# Get probabilities
probabilities = registry.predict_proba_profitability(
    X=new_trades_df,
    timeframe="5min",
    archetype="trend_following"
)
```

## Batch Training from Enriched Data

The registry automatically discovers all unique timeframe/archetype combinations in your data:

```python
# Example: enriched_df contains trades from multiple contexts
# - 5min_trend_following: 150 trades
# - 15min_trend_following: 200 trades
# - 5min_mean_reversion: 80 trades

prof_models = registry.train_all_profitability_models(enriched_df)

# Result: 3 models trained (one per context)
# - models/profitability/5min_trend_following.pkl
# - models/profitability/15min_trend_following.pkl
# - models/profitability/5min_mean_reversion.pkl
```

The process:
1. Scans `enriched_df` for unique (`execution_timeframe`, `strategy_archetype`) pairs
2. For each pair, filters data and trains a specialized model
3. Raises `ValueError` if any context has < 50 trades (fail-fast)
4. Returns dict of trained models keyed by `{timeframe}_{archetype}`

## Model Registration

### Manual Registration

```python
from trading_platform.ai.models import ProfitabilityModel

# Create and train a single model
model = ProfitabilityModel(timeframe="5min", archetype="trend_following")
model.fit(enriched_df)

# Register it
registry.register_model(
    family="profitability",
    key="5min_trend_following",
    model=model
)
```

### Retrieving Models

```python
# Get a specific model
model = registry.get_model("profitability", "5min_trend_following")

if model is None:
    print("Model not found")
else:
    predictions = model.predict(X)
```

### Listing Models

```python
# List all profitability models
prof_keys = registry.list_models("profitability")
# Returns: ["5min_trend_following", "15min_trend_following", ...]

# List all diagnostic models
diag_keys = registry.list_models("diagnostic")
```

## Lazy Loading

The registry supports lazy model creation:

```python
# Get or create a model (creates if doesn't exist)
model = registry.get_or_create_profitability_model(
    timeframe="5min",
    archetype="trend_following",
    n_estimators=100
)

# Model is created but not trained yet
# Call model.fit(df) to train it
```

## Persistence

### Saving Models

```python
# Save all registered models to disk
registry.save()

# This creates:
# - models/profitability/<key>.pkl for each profitability model
# - models/diagnostic/<key>.pkl for each diagnostic model
```

### Loading Models

```python
# Load all models from disk
registry = ModelRegistry(model_dir="models")
registry.load()

# Models are now available via get_model() or predict_*() methods
```

### Model Paths

```python
# Get the file path for a specific model
path = registry.get_model_path("profitability", "5min_trend_following")
# Returns: Path("models/profitability/5min_trend_following.pkl")
```

## CLI Integration

### Training

```bash
# Train all profitability models from enriched data
poetry run tp train-profitability-models \
  --enriched-path data/enriched/campaign/rich_trades.parquet \
  --model-dir models

# Train all diagnostic models
poetry run tp train-diagnostic-models \
  --enriched-path data/enriched/campaign/rich_trades.parquet \
  --model-dir models
```

### Prediction

```bash
# Predict using registered models
poetry run tp predict-profitability \
  --model-dir models \
  --timeframe 5min \
  --archetype trend_following \
  --features features.json
```

## Error Handling

### Insufficient Data

```python
try:
    prof_models = registry.train_all_profitability_models(enriched_df)
except ValueError as e:
    # Raised if any context has < 50 trades
    print(f"Training failed: {e}")
    # Example: "Insufficient data: need 50+ trades for 5min_trend_following, got 25"
```

### Missing Models

```python
# Predict with missing model
try:
    predictions = registry.predict_profitability(
        X=df,
        timeframe="1h",
        archetype="unknown_strategy"
    )
except ValueError as e:
    print(f"Model not found: {e}")
    # "Profitability model '1h_unknown_strategy' not found. Train it first."
```

## Best Practices

### 1. Train Once, Use Many Times

```python
# Training (one-time, after campaign)
registry = ModelRegistry(model_dir="models")
prof_models = registry.train_all_profitability_models(enriched_df)
registry.save()

# Production (load once at startup)
registry = ModelRegistry(model_dir="models")
registry.load()

# Use throughout application lifecycle
predictions = registry.predict_profitability(X, timeframe, archetype)
```

### 2. Version Your Models

```python
# Use versioned model directories
registry_v1 = ModelRegistry(model_dir="models/v1")
registry_v2 = ModelRegistry(model_dir="models/v2")

# Compare performance
preds_v1 = registry_v1.predict_profitability(X, "5min", "trend_following")
preds_v2 = registry_v2.predict_profitability(X, "5min", "trend_following")
```

### 3. Validate Before Deployment

```python
# After training, verify all expected models exist
expected_contexts = [
    ("5min", "trend_following"),
    ("15min", "trend_following"),
    ("1h", "mean_reversion"),
]

for timeframe, archetype in expected_contexts:
    key = f"{timeframe}_{archetype}"
    model = registry.get_model("profitability", key)
    if model is None:
        raise ValueError(f"Missing required model: {key}")

print("All required models present ✓")
```

## See Also

- [ProfitabilityModel Documentation](02_profitability_model.md)
- [PerformanceDiagnosticModel Documentation](04_performance_diagnostic_model.md)
- [ModelRegistry API](../src/trading_platform/ai/models/registry.py)
- [ML Data Curation Guide](05_ml_data_curation_guide.md)
