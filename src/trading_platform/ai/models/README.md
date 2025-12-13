# ML Models for Trading Platform

This directory contains specialized machine learning models for trading strategy optimization and regime analysis.

## Architecture Overview

The ML models architecture uses **context-specific models** - one model per timeframe/archetype combination (e.g., `5min_trend_following`, `15min_mean_reversion`). This approach provides better performance than a single universal model.

### Two Model Families

1. **ProfitabilityModel** - Real-time signal filtering
   - **Purpose**: Predict expected R-multiple (risk-adjusted return) before entry
   - **Features**: Only entry-time data (NO lookahead), including `initial_stop_loss_pips`
   - **Target**: R-multiple regression (continuous values, e.g., 2.5R, -1.0R)
   - **Use case**: Production trading systems, live signal filtering, risk-adjusted forecasting

2. **PerformanceDiagnosticModel** - Offline regime analysis
   - **Purpose**: Identify market regimes with better/worse performance
   - **Features**: ALL available data (including lookahead)
   - **Target**: Quintile classification based on adaptable metric (r_multiple or pnl)
   - **Use case**: Backtesting, strategy improvement, regime detection
   - **Segregated training**: Separate models for data with/without risk parameters

### ModelRegistry

Central manager that:
- Registers and organizes models by context
- Routes predictions to the appropriate model
- Handles batch training from enriched data
- Manages model persistence (save/load)
- Supports lazy loading for efficiency

## Quick Start

### Training Models

```python
from trading_platform.ai.models import ModelRegistry
import pandas as pd

# Load enriched trade data
enriched_df = pd.read_parquet("data/enriched/rich_trades.parquet")

# Initialize registry
registry = ModelRegistry(model_dir="models")

# Train profitability models (one per context)
prof_models = registry.train_all_profitability_models(
    enriched_df,
    n_estimators=100,
    random_state=42
)
print(f"Trained {len(prof_models)} profitability models")

# Train diagnostic models (one per context)
contexts = enriched_df[["execution_timeframe", "strategy_archetype"]].drop_duplicates()
for _, row in contexts.iterrows():
    from trading_platform.ai.models import PerformanceDiagnosticModel
    model = PerformanceDiagnosticModel(
        timeframe=row["execution_timeframe"],
        archetype=row["strategy_archetype"]
    )
    try:
        model.fit(enriched_df)
        registry.register_model("diagnostic", model.get_model_key(), model)
    except ValueError as e:
        print(f"Skipped: {e}")

# Save all models
registry.save()
```

### Making Predictions

```python
from trading_platform.ai.models import ModelRegistry

# Load trained models
registry = ModelRegistry(model_dir="models")
registry.load()

# List available models
print("Profitability models:", registry.list_models("profitability"))
print("Diagnostic models:", registry.list_models("diagnostic"))

# Predict R-multiple for new trades
r_multiple_predictions = registry.predict_profitability(
    X=new_trades_df,
    timeframe="5min",
    archetype="trend_following"
)

# Analyze regime performance (diagnostic models)
regime_predictions = registry.analyze_performance_regime(
    X=enriched_trades_df,
    timeframe="5min",
    archetype="trend_following"
)
```

## CLI Commands

### Train Profitability Models

```bash
poetry run tp train-profitability-models \
    --enriched-data data/enriched/rich_trades.parquet \
    --model-dir models \
    --n-estimators 100 \
    --random-state 42
```

### Train Diagnostic Models

```bash
poetry run tp train-diagnostic-models \
    --enriched-data data/enriched/rich_trades.parquet \
    --model-dir models \
    --n-estimators 100 \
    --random-state 42
```

### Generate Predictions

```bash
poetry run tp predict-profitability \
    --input-data data/new_trades.parquet \
    --model-dir models \
    --output predictions.csv
```

### Analyze Regime Performance

```bash
poetry run tp analyze-regime \
    --input-data data/enriched/rich_trades.parquet \
    --model-dir models \
    --output regime_analysis.csv
```

## Feature Engineering

### ProfitabilityModel Features (Entry-time only)

- **Context features**: All `context_at_entry_*` columns
- **Risk parameter**: `initial_stop_loss_pips` (known at entry)
- **Side**: One-hot encoded (`side_long`, `side_short`)
- **Symbol**: One-hot encoded (e.g., `symbol_EURUSD`)
- **Temporal features**:
  - `hour_of_day` (0-23)
  - `day_of_week` (0-6, Monday=0)

**Excluded** (lookahead):
- Any `exit_*` features
- `bars_held`, `mae_currency`, `mfe_currency`, `r_multiple`
- `context_at_exit_*`, `post_exit_analysis_*`
- `pnl`, `pnl_movement`

**Target**: `r_multiple` (continuous regression)

### PerformanceDiagnosticModel Features (All available data)

- **Entry features**: All `context_at_entry_*` columns
- **Exit features**: All `context_at_exit_*` columns
- **Post-trade analysis**: All `post_exit_analysis_*` columns
- **Trade execution**: `bars_held`, `mae_currency`, `mfe_currency`
- **Exit metadata**: `exit_reason` (one-hot encoded)
- **Cost features**: `cost_breakdown_commission`, `cost_breakdown_slippage`, `cost_breakdown_spread`
- **Categorical/temporal**: Same as ProfitabilityModel

**Target**: Quintiles based on adaptable metric (default: `r_multiple`, can be `pnl`) (0=worst, 4=best)

## Model Storage

Models are saved in the following structure:

```
models/
├── profitability/
│   ├── 5min_trend_following.pkl
│   ├── 5min_mean_reversion.pkl
│   ├── 15min_trend_following.pkl
│   └── 15min_mean_reversion.pkl
└── diagnostic/
    ├── 5min_trend_following.pkl
    ├── 5min_mean_reversion.pkl
    ├── 15min_trend_following.pkl
    └── 15min_mean_reversion.pkl
```

Each `.pkl` file contains:
- Fitted RandomForestRegressor (profitability) or RandomForestClassifier (diagnostic)
- SimpleImputer for handling missing values
- Feature names for alignment
- Model metadata (timeframe, archetype, hyperparameters, training dates)
- Lookahead bias prevention: training_start_date, training_end_date

## Requirements

- Minimum 50 trades per context for training
- Enriched trade data with all required features
- scikit-learn for model training
- joblib for model persistence

## Testing

Run the test suite:

```bash
# Test all ML models
poetry run pytest tests/ai/models/ -v

# Test specific model
poetry run pytest tests/ai/models/test_profitability.py -v
poetry run pytest tests/ai/models/test_performance_diagnostic.py -v
poetry run pytest tests/ai/models/test_registry.py -v
```

## Integration with Trading Platform

### Real-time Signal Filtering

```python
# In your signal generator
from trading_platform.ai.models import ModelRegistry

registry = ModelRegistry()
registry.load()

# Filter signals before execution
signal_features = extract_entry_features(current_market_state)
predicted_r_multiple = registry.predict_profitability(
    X=signal_features,
    timeframe=strategy.timeframe,
    archetype=strategy.archetype
)

# Only execute if expected R-multiple > threshold
if predicted_r_multiple.iloc[0] > 0.5:  # Expect at least 0.5R
    execute_trade(signal)
```

### Regime Analysis

```python
# Analyze historical performance by regime
from trading_platform.ai.models import ModelRegistry

registry = ModelRegistry()
registry.load()

# Get regime classification for each trade
model = registry.get_model("diagnostic", "5min_trend_following")
quintiles = model.predict(historical_trades)

# Analyze performance by quintile
for q in range(5):
    trades_in_quintile = historical_trades[quintiles == q]
    print(f"Quintile {q}: {len(trades_in_quintile)} trades, "
          f"avg R-multiple: {trades_in_quintile['r_multiple'].mean():.2f}")
```

## Troubleshooting

### "Insufficient data" Error

**Cause**: Context has fewer than 50 trades

**Solution**: Either collect more data for that context or use a broader context definition

### Feature Mismatch During Prediction

**Cause**: Input data missing features that were present during training

**Solution**: Models automatically add missing features (filled with 0) and drop extra features. Verify your input data has the expected structure.

### Model Not Found

**Cause**: Trying to predict with a context that wasn't trained

**Solution**: Check available models with `registry.list_models("profitability")` and ensure you've trained models for the desired context.

## Future Enhancements

- [ ] Support for additional model types (XGBoost, LightGBM)
- [ ] Automated hyperparameter tuning
- [ ] Model versioning and A/B testing
- [ ] Online learning / incremental updates
- [ ] SHAP values for feature importance
- [ ] Model performance monitoring and drift detection

## See Also

- [Data Curation Pipeline](../../../docs/ai/data_curation.md)
- [Campaign System](../campaigns/README.md)
- [Rule-Based Diagnostics](../../reporting/diagnostics/README.md)
