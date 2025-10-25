# ProfitabilityModel - Real-Time Signal Filtering

## Overview

`ProfitabilityModel` is a **binary classifier** designed for real-time signal filtering in production trading systems. Each model is specialized for a specific timeframe/archetype combination (e.g., `5min_trend_following`, `15min_mean_reversion`).

### Key Characteristics

- **Multiple Models**: One model per timeframe/archetype context
- **No Lookahead**: Uses ONLY entry-time features (production-safe)
- **Binary Target**: Predicts profitable (1) vs unprofitable (0)
- **Purpose**: Filter signals before execution in live trading

## Architecture

### Context-Specific Training

Unlike a single universal model, we train separate models for each context:

```
models/profitability/
├── 5min_trend_following.pkl
├── 5min_mean_reversion.pkl
├── 15min_trend_following.pkl
├── 1h_trend_following.pkl
└── ...
```

**Why separate models?**
- Different timeframes have fundamentally different patterns
- Entry signals behave differently across archetypes
- Specialized models achieve better performance than one-size-fits-all

### Feature Selection: Entry Context Only

ProfitabilityModel uses **strictly entry-time features**:

✅ **Allowed Features** (no lookahead):
- `context_at_entry_*` - All context features at entry time
- `side` - Long/short direction
- `symbol` - Trading pair
- Temporal features: `hour_of_day`, `day_of_week`, `is_london_session`

❌ **Forbidden Features** (lookahead):
- `pnl`, `pnl_movement`
- `exit_*` fields
- `bars_held`
- `mae_currency`, `mfe_currency`, `r_multiple`
- `context_at_exit_*`
- `post_exit_analysis_*`

This strict separation ensures the model can be used in production without data leakage.

## Training

### From Enriched Campaign Data

```python
from trading_platform.ai.models import ModelRegistry
import pandas as pd

# Load enriched trades from campaign
enriched_df = pd.read_parquet("data/enriched/campaign_id/rich_trades.parquet")

# Initialize registry
registry = ModelRegistry(model_dir="models")

# Train all profitability models (auto-discovers contexts)
trained_models = registry.train_all_profitability_models(
    enriched_df,
    n_estimators=100,
    random_state=42
)

print(f"Trained {len(trained_models)} models:")
for key in trained_models.keys():
    print(f"  - {key}")

# Save to disk
registry.save()
```

### CLI Training

```bash
# Train from enriched campaign data
poetry run tp train-profitability-models \
  --enriched-path data/enriched/trend_following_15m_v1/rich_trades.parquet \
  --model-dir models \
  --n-estimators 100
```

### Minimum Data Requirements

- **Minimum 50 trades** per timeframe/archetype context
- Raises `ValueError` if insufficient data (fail-fast)
- No silent failures or skipping

## Prediction

### Via ModelRegistry

```python
# Load trained models
registry = ModelRegistry(model_dir="models")
registry.load()

# Predict for specific context
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

### Direct Model Use

```python
from trading_platform.ai.models import ProfitabilityModel

# Train single model
model = ProfitabilityModel(
    timeframe="5min",
    archetype="trend_following"
)
model.fit(enriched_df)

# Predict
predictions = model.predict(X)
probabilities = model.predict_proba(X)
```

## CLI Usage

### Training

```bash
# Train all models from enriched data
poetry run tp train-profitability-models \
  --enriched-path data/enriched/campaign/rich_trades.parquet \
  --model-dir models

# Specify hyperparameters
poetry run tp train-profitability-models \
  --enriched-path data/enriched/campaign/rich_trades.parquet \
  --model-dir models \
  --n-estimators 200 \
  --random-state 42
```

### Prediction

```bash
# Predict profitability for trades
poetry run tp predict-profitability \
  --model-dir models \
  --timeframe 5min \
  --archetype trend_following \
  --features features.json
```

## Integration with Trading Systems

### Pre-Entry Signal Filtering

```python
# In your trading strategy
def should_enter_trade(signal, context):
    """Filter signal using profitability model."""

    # Extract features from current context
    features = {
        "context_at_entry_rsi": context["rsi"],
        "context_at_entry_ema_fast": context["ema_fast"],
        "side": signal.side,
        "symbol": signal.symbol,
        "hour_of_day": datetime.now().hour,
        # ... other entry features
    }

    # Get prediction
    prob = registry.predict_proba_profitability(
        X=pd.DataFrame([features]),
        timeframe=strategy.timeframe,
        archetype=strategy.archetype
    )[0][1]  # Probability of profitable trade

    # Filter: only take high-probability trades
    return prob > 0.65  # Threshold tuned via backtesting
```

### Batch Analysis

```python
# Analyze a set of potential signals
signals_df = pd.DataFrame([...])  # Candidate signals with features

predictions = registry.predict_profitability(
    X=signals_df,
    timeframe="5min",
    archetype="trend_following"
)

# Keep only predicted profitable signals
filtered_signals = signals_df[predictions == 1]
```

## Model Persistence

Models are saved using joblib:

```
models/
└── profitability/
    ├── 5min_trend_following.pkl
    ├── 15min_trend_following.pkl
    └── ...
```

Each model file contains:
- Trained RandomForestClassifier
- SimpleImputer (fitted)
- Feature names (for validation)
- Metadata (timeframe, archetype)

## Evaluation

See [03_model_registry.md](03_model_registry.md) for batch evaluation workflows and [05_ml_data_curation_guide.md](05_ml_data_curation_guide.md) for campaign-based model training and evaluation.

## See Also

- [ProfitabilityModel API](../src/trading_platform/ai/models/profitability.py)
- [ModelRegistry Documentation](03_model_registry.md)
- [ML Data Curation Guide](05_ml_data_curation_guide.md)
- [Campaign Runner Guide](06_campaign_runner_guide.md)
