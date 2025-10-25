"""ML models for trading platform.

This module provides specialized machine learning models for trading strategy
optimization and analysis. The architecture uses context-specific models
(one per timeframe/archetype combination) for improved performance.

Components
----------
ProfitabilityModel
    Binary classifier for real-time signal filtering. Uses only entry-time
    features (no lookahead) to predict whether a trade will be profitable.
    Suitable for production use in live trading systems.

PerformanceDiagnosticModel
    Quintile classifier for offline regime analysis. Uses ALL available
    features (including lookahead) to identify market regimes that produce
    better/worse performance. Suitable for backtesting and strategy improvement.

ModelRegistry
    Central manager for both model families. Handles model registration,
    lazy loading, batch training, persistence, and routing predictions to
    the appropriate model based on timeframe/archetype context.

Quick Start
-----------
Training models from enriched data:

    >>> from trading_platform.ai.models import ModelRegistry
    >>> import pandas as pd
    >>>
    >>> # Load enriched trade data
    >>> enriched_df = pd.read_parquet("data/enriched/rich_trades.parquet")
    >>>
    >>> # Initialize registry
    >>> registry = ModelRegistry(model_dir="models")
    >>>
    >>> # Train all profitability models
    >>> trained = registry.train_all_profitability_models(enriched_df)
    >>> print(f"Trained {len(trained)} models")
    >>>
    >>> # Save models to disk
    >>> registry.save()

Making predictions:

    >>> # Load trained models
    >>> registry = ModelRegistry(model_dir="models")
    >>> registry.load()
    >>>
    >>> # Predict profitability for new trades
    >>> predictions = registry.predict_profitability(
    ...     X=new_trades_df,
    ...     timeframe="5min",
    ...     archetype="trend_following"
    ... )

See Also
--------
- CLI commands: train-profitability-models, train-diagnostic-models
- Documentation: docs/ai/ml_models_architecture.md
"""

from trading_platform.ai.models.diagnostic import PerformanceDiagnosticModel
from trading_platform.ai.models.profitability import ProfitabilityModel
from trading_platform.ai.models.registry import ModelRegistry

__all__ = ["ProfitabilityModel", "PerformanceDiagnosticModel", "ModelRegistry"]
