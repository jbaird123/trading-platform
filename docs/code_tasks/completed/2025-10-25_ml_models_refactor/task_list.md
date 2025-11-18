# ML Models Architecture Refactor - Implementation Plan

**Status:** ✅ COMPLETE (2025-10-25)

**Branch Name:** `refactor/ml-models-architecture`

**Feature Description:** Refactor AI module to support multiple specialized ML models per timeframe/archetype combination. Create both ProfitabilityModel and PerformanceDiagnosticModel instances for each context (e.g., 5min_trend, 15min_mean_reversion). Move rule-based diagnostics to reporting/.

**Implementation Summary:** See [ml_models_refactor_completion.md](../ai/ml_models_refactor_completion.md) for full details.
- ✅ 40 ML model tests passing
- ✅ 4 new CLI commands
- ✅ ~2,500 lines of code
- ✅ Comprehensive documentation
- ⚠️ Minor linting issues to address in follow-up

**Objectives:**
1. Multiple specialized ProfitabilityModels per timeframe/archetype combination
2. Multiple specialized PerformanceDiagnosticModels per timeframe/archetype combination
3. ModelRegistry for managing and routing to appropriate models (both types)
4. Clear separation between ML models and rule-based heuristics
5. Consistent naming conventions and scikit-learn compatible interfaces
6. Proper organization: ML models in ai/models/, rule-based analysis in reporting/diagnostics/

**Architecture Overview:**
- **Predictive Models (Many)**: One ProfitabilityModel per timeframe/archetype
  - `profitability_5min_trend.pkl`
  - `profitability_15min_trend.pkl`
  - `profitability_1h_mean_reversion.pkl`
  - etc.
- **Diagnostic Models (Many)**: One PerformanceDiagnosticModel per timeframe/archetype
  - `diagnostic_5min_trend.pkl`
  - `diagnostic_15min_trend.pkl`
  - `diagnostic_1h_mean_reversion.pkl`
  - etc.
- **Rule-Based (One)**: RuleBasedAnalyzer for heuristic checks

---

## Phase 1: Create New Module Structure

### 1. [ ] Create branch for refactoring work
```bash
git checkout -b refactor/ml-models-architecture
```

### 2. [ ] Create ai/models/ directory structure
- Create directory: `src/trading_platform/ai/models/`
- Create file: `src/trading_platform/ai/models/__init__.py`
  - Content: Empty file (will be populated in later tasks)

### 3. [ ] Create reporting/diagnostics/ directory structure
- Create directory: `src/trading_platform/reporting/diagnostics/`
- Create file: `src/trading_platform/reporting/diagnostics/__init__.py`
  - Content: Empty file (will be populated in later tasks)

---

## Phase 2: Implement ProfitabilityModel Base Class

### 4. [ ] Write tests for ProfitabilityModel
- Create file: `tests/ai/models/test_profitability.py`
- Test class: `TestProfitabilityModel`
- Test methods:
  - `test_fit_with_valid_trades_df()` - Verify model trains successfully with entry context features
  - `test_fit_extracts_only_entry_features()` - Verify no lookahead features used
  - `test_fit_filters_by_context()` - Verify training data filtered by timeframe/archetype
  - `test_predict_returns_binary_array()` - Verify predict() returns 0/1 values
  - `test_predict_proba_returns_probabilities()` - Verify predict_proba() returns [0.0-1.0] values
  - `test_save_and_load()` - Verify model serialization works
  - `test_metadata_stored()` - Verify timeframe/archetype stored in model
  - `test_fit_with_empty_dataframe_raises()` - Verify error handling
  - `test_fit_with_insufficient_data_raises()` - Need minimum 50 trades
  - `test_fit_with_missing_pnl_column_raises()` - Verify validation
  - `test_feature_names_stored()` - Verify feature names tracked for inference

### 5. [ ] Implement ProfitabilityModel class
- Create file: `src/trading_platform/ai/models/profitability.py`
- Class: `ProfitabilityModel`
- Constructor: `__init__(self, timeframe: str, archetype: str, n_estimators=100, random_state=42)`
  - Store `self.timeframe = timeframe`
  - Store `self.archetype = archetype`
  - Store hyperparameters
  - Initialize `self.model = None`
  - Initialize `self.feature_names_ = None`
  - Initialize `self.imputer = None`
- Method: `fit(self, trades_df: pd.DataFrame) -> ProfitabilityModel`
  - Filter data: `df = trades_df[(trades_df['execution_timeframe'] == self.timeframe) & (trades_df['strategy_archetype'] == self.archetype)]`
  - Validate minimum samples: `if len(df) < 50: raise ValueError(f"Insufficient data: need 50+ trades, got {len(df)}")`
  - Extract feature columns (ONLY features known at entry time - NO lookahead):
    - Pattern match: All columns matching `context_at_entry_*` (e.g., `context_at_entry_strategy_features_ema_fast`, `context_at_entry_strategy_features_1h_rsi`)
    - Categorical: `side` (one-hot encode: long=1/short=0 or create dummy variables)
    - Categorical: `symbol` (one-hot encode if multiple pairs, or use label encoding)
    - Temporal: Derived from `entry_time`: `hour_of_day`, `day_of_week`, `is_london_session`, `is_ny_session`, etc.
  - DO NOT include lookahead features: `pnl`, `pnl_movement`, `exit_*`, `bars_held`, `mae_currency`, `mfe_currency`, `r_multiple`, `context_at_exit_*`, `post_exit_analysis_*`
  - Create target: `y = (df['pnl'] > 0).astype(int)` (binary: 1=profitable, 0=unprofitable)
  - Store feature names in `self.feature_names_`
  - Initialize `SimpleImputer(strategy='mean')` and fit
  - Initialize `RandomForestClassifier(n_estimators=self.n_estimators, random_state=self.random_state)`
  - Call `self.model.fit(X_imputed, y)`
  - Return `self`
- Method: `predict(self, X: pd.DataFrame) -> np.ndarray`
  - Validate model is fitted
  - Align features with `self.feature_names_`
  - Impute missing values
  - Return `self.model.predict(X_imputed)`
- Method: `predict_proba(self, X: pd.DataFrame) -> np.ndarray`
  - Validate model is fitted
  - Align features with `self.feature_names_`
  - Impute missing values
  - Return `self.model.predict_proba(X_imputed)`
- Method: `save(self, path: Path) -> None`
  - Save dictionary with: `{'model': self.model, 'feature_names': self.feature_names_, 'imputer': self.imputer, 'timeframe': self.timeframe, 'archetype': self.archetype, 'hyperparams': {...}}`
  - Use `joblib.dump()`
- Class method: `load(cls, path: Path) -> ProfitabilityModel`
  - Load using `joblib.load()`
  - Reconstruct instance: `instance = cls(data['timeframe'], data['archetype'])`
  - Set attributes: `instance.model = data['model']`, etc.
  - Return instance
- Method: `get_model_key(self) -> str`
  - Return `f"{self.timeframe}_{self.archetype}"`

### 6. [ ] Update ai/models/__init__.py to export ProfitabilityModel
- Edit file: `src/trading_platform/ai/models/__init__.py`
- Add import: `from trading_platform.ai.models.profitability import ProfitabilityModel`
- Add to `__all__`: `["ProfitabilityModel"]`

---

## Phase 3: Implement ModelRegistry

### 7. [ ] Write tests for ModelRegistry
- Create file: `tests/ai/models/test_registry.py`
- Test class: `TestModelRegistry`
- Test methods:
  - `test_register_model()` - Verify model registration
  - `test_register_duplicate_key_raises()` - Verify duplicate detection
  - `test_get_model_exists()` - Verify model retrieval
  - `test_get_model_not_exists_returns_none()` - Verify missing model handling
  - `test_list_models()` - Verify listing all registered models
  - `test_save_registry()` - Verify registry serialization
  - `test_load_registry()` - Verify registry deserialization
  - `test_get_or_create_model()` - Verify lazy model instantiation
  - `test_train_all_models_from_enriched_data()` - Verify batch training

### 8. [ ] Implement ModelRegistry class
- Create file: `src/trading_platform/ai/models/registry.py`
- Class: `ModelRegistry`
- Constructor: `__init__(self, models_dir: Path = None)`
  - Store `self.models_dir = models_dir or paths.PROJECT_ROOT / "models"`
  - Initialize `self._profitability_models: dict[str, ProfitabilityModel] = {}`
  - Initialize `self._diagnostic_models: dict[str, PerformanceDiagnosticModel] = {}`
- Method: `register_profitability(self, model: ProfitabilityModel) -> None`
  - Get key: `key = model.get_model_key()`
  - Check for duplicates: `if key in self._profitability_models: raise ValueError(f"Profitability model {key} already registered")`
  - Store: `self._profitability_models[key] = model`
- Method: `register_diagnostic(self, model: PerformanceDiagnosticModel) -> None`
  - Get key: `key = model.get_model_key()`
  - Check for duplicates: `if key in self._diagnostic_models: raise ValueError(f"Diagnostic model {key} already registered")`
  - Store: `self._diagnostic_models[key] = model`
- Method: `get_profitability(self, timeframe: str, archetype: str) -> ProfitabilityModel | None`
  - Construct key: `key = f"{timeframe}_{archetype}"`
  - Return `self._profitability_models.get(key)`
- Method: `get_diagnostic(self, timeframe: str, archetype: str) -> PerformanceDiagnosticModel | None`
  - Construct key: `key = f"{timeframe}_{archetype}"`
  - Return `self._diagnostic_models.get(key)`
- Method: `get_or_load_profitability(self, timeframe: str, archetype: str) -> ProfitabilityModel | None`
  - Try memory: `model = self.get_profitability(timeframe, archetype)`
  - If found, return it
  - Try disk: `path = self.models_dir / "profitability" / f"profitability_{timeframe}_{archetype}.pkl"`
  - If exists: `model = ProfitabilityModel.load(path); self.register_profitability(model); return model`
  - Return `None`
- Method: `get_or_load_diagnostic(self, timeframe: str, archetype: str) -> PerformanceDiagnosticModel | None`
  - Try memory: `model = self.get_diagnostic(timeframe, archetype)`
  - If found, return it
  - Try disk: `path = self.models_dir / "diagnostic" / f"diagnostic_{timeframe}_{archetype}.pkl"`
  - If exists: `model = PerformanceDiagnosticModel.load(path); self.register_diagnostic(model); return model`
  - Return `None`
- Method: `list_profitability_models(self) -> list[dict[str, str]]`
  - Return list of dicts: `[{"timeframe": m.timeframe, "archetype": m.archetype, "key": m.get_model_key(), "type": "profitability"} for m in self._profitability_models.values()]`
- Method: `list_diagnostic_models(self) -> list[dict[str, str]]`
  - Return list of dicts: `[{"timeframe": m.timeframe, "archetype": m.archetype, "key": m.get_model_key(), "type": "diagnostic"} for m in self._diagnostic_models.values()]`
- Method: `list_all_models(self) -> list[dict[str, str]]`
  - Return `self.list_profitability_models() + self.list_diagnostic_models()`
- Method: `save_all_profitability(self) -> None`
  - Create `self.models_dir / "profitability"` if not exists
  - For each model: `model.save(self.models_dir / "profitability" / f"profitability_{model.get_model_key()}.pkl")`
- Method: `save_all_diagnostic(self) -> None`
  - Create `self.models_dir / "diagnostic"` if not exists
  - For each model: `model.save(self.models_dir / "diagnostic" / f"diagnostic_{model.get_model_key()}.pkl")`
- Method: `save_all(self) -> None`
  - Call `self.save_all_profitability()`
  - Call `self.save_all_diagnostic()`
- Method: `load_all_profitability(self) -> None`
  - Scan `self.models_dir / "profitability"` for `profitability_*.pkl` files
  - Load each model: `model = ProfitabilityModel.load(path)`
  - Register: `self.register_profitability(model)`
- Method: `load_all_diagnostic(self) -> None`
  - Scan `self.models_dir / "diagnostic"` for `diagnostic_*.pkl` files
  - Load each model: `model = PerformanceDiagnosticModel.load(path)`
  - Register: `self.register_diagnostic(model)`
- Method: `load_all(self) -> None`
  - Call `self.load_all_profitability()`
  - Call `self.load_all_diagnostic()`
- Method: `train_all_profitability_from_enriched(self, enriched_df: pd.DataFrame, min_trades: int = 50) -> dict[str, int]`
  - Get unique combinations: `contexts = enriched_df[['execution_timeframe', 'strategy_archetype']].drop_duplicates()`
  - For each context:
    - Filter data: `df_context = enriched_df[(enriched_df['execution_timeframe'] == timeframe) & (enriched_df['strategy_archetype'] == archetype)]`
    - Check minimum: `if len(df_context) < min_trades: log warning and skip`
    - Create model: `model = ProfitabilityModel(timeframe, archetype)`
    - Train: `model.fit(enriched_df)`
    - Register: `self.register_profitability(model)`
  - Return summary: `{model_key: n_trades, ...}`
- Method: `train_all_diagnostic_from_enriched(self, enriched_df: pd.DataFrame, min_trades: int = 50) -> dict[str, int]`
  - Get unique combinations: `contexts = enriched_df[['execution_timeframe', 'strategy_archetype']].drop_duplicates()`
  - For each context:
    - Filter data: `df_context = enriched_df[(enriched_df['execution_timeframe'] == timeframe) & (enriched_df['strategy_archetype'] == archetype)]`
    - Check minimum: `if len(df_context) < min_trades: log warning and skip`
    - Create model: `model = PerformanceDiagnosticModel(timeframe, archetype)`
    - Train: `model.fit(enriched_df)`
    - Register: `self.register_diagnostic(model)`
  - Return summary: `{model_key: n_trades, ...}`

### 9. [ ] Update ai/models/__init__.py to export ModelRegistry
- Edit file: `src/trading_platform/ai/models/__init__.py`
- Add import: `from trading_platform.ai.models.registry import ModelRegistry`
- Update `__all__`: `["ProfitabilityModel", "ModelRegistry"]`

---

## Phase 4: Implement PerformanceDiagnosticModel (Context-Specific Models)

### 10. [ ] Write tests for PerformanceDiagnosticModel
- Create file: `tests/ai/models/test_performance_diagnostic.py`
- Test class: `TestPerformanceDiagnosticModel`
- Test methods:
  - `test_fit_with_valid_trades_df()` - Verify model trains with all features
  - `test_fit_uses_all_features_including_lookahead()` - Verify post_exit features included
  - `test_fit_filters_by_context()` - Verify training data filtered by timeframe/archetype
  - `test_target_creates_quintiles()` - Verify target is [0,1,2,3,4] categories
  - `test_predict_returns_quintile_array()` - Verify predict() returns 0-4 values
  - `test_predict_proba_returns_quintile_probabilities()` - Verify 5-class probability distribution
  - `test_get_feature_importance()` - Verify feature importance extraction
  - `test_save_and_load()` - Verify model serialization
  - `test_metadata_stored()` - Verify timeframe/archetype stored in model
  - `test_fit_with_insufficient_trades_raises()` - Need at least 50 trades per context
  - `test_fit_with_missing_pnl_column_raises()` - Verify validation

### 11. [ ] Implement PerformanceDiagnosticModel class
- Create file: `src/trading_platform/ai/models/performance_diagnostic.py`
- Class: `PerformanceDiagnosticModel`
- Constructor: `__init__(self, timeframe: str, archetype: str, n_estimators=100, random_state=42)`
  - Store `self.timeframe = timeframe`
  - Store `self.archetype = archetype`
  - Store hyperparameters
  - Initialize `self.model = None`
  - Initialize `self.feature_names_ = None`
  - Initialize `self.imputer = None`
- Method: `fit(self, trades_df: pd.DataFrame) -> PerformanceDiagnosticModel`
  - Filter data: `df = trades_df[(trades_df['execution_timeframe'] == self.timeframe) & (trades_df['strategy_archetype'] == self.archetype)]`
  - Validate minimum samples: `if len(df) < 50: raise ValueError(f"Insufficient data: need 50+ trades, got {len(df)}")`
  - Extract ALL feature columns (includes lookahead - this is offline analysis):
    - **Entry features**: All columns matching `context_at_entry_*`
    - **Entry metadata**: `side` (one-hot), `symbol` (one-hot/label encoded), temporal features from `entry_time`
    - **Exit features**: All columns matching `context_at_exit_*`
    - **Exit metadata**: `exit_reason` (one-hot encode if categorical: "stop_loss", "take_profit", "trailing_stop", etc.)
    - **Trade execution features**: `bars_held` (how long trade lasted), `mae_currency` (max adverse excursion), `mfe_currency` (max favorable excursion), `r_multiple` (risk/reward ratio)
    - **Post-trade analysis**: All columns matching `post_exit_analysis_*` (e.g., `post_exit_analysis_simulated_holds`)
    - **Cost features**: `cost_breakdown_commission`, `cost_breakdown_slippage`, `cost_breakdown_spread`
  - DO NOT include: `pnl` (this is the target!), `pnl_movement` (derived from pnl), `entry_price`/`exit_price` (absolute prices not useful), `entry_time`/`exit_time` (use derived features instead)
  - Create target using quintiles: `y = pd.qcut(df['pnl'], q=5, labels=[0, 1, 2, 3, 4], duplicates='drop')` (0=worst 20%, 4=best 20%)
  - Handle case where quintiles can't be created (< 5 unique values): raise `ValueError`
  - Store feature names in `self.feature_names_`
  - Initialize `SimpleImputer(strategy='mean')` and fit
  - Initialize `RandomForestClassifier(n_estimators=self.n_estimators, random_state=self.random_state)`
  - Call `self.model.fit(X_imputed, y)`
  - Return `self`
- Method: `predict(self, X: pd.DataFrame) -> np.ndarray`
  - Validate model is fitted
  - Align features with `self.feature_names_`
  - Impute missing values
  - Return `self.model.predict(X_imputed)`
- Method: `predict_proba(self, X: pd.DataFrame) -> np.ndarray`
  - Validate model is fitted
  - Align features with `self.feature_names_`
  - Impute missing values
  - Return `self.model.predict_proba(X_imputed)` (5-column array)
- Method: `get_feature_importance(self) -> dict[str, float]`
  - Validate model is fitted
  - Extract `self.model.feature_importances_`
  - Return dictionary: `{feature_name: importance_value}`
  - Sort by importance descending
- Method: `save(self, path: Path) -> None`
  - Save dictionary with: `{'model': self.model, 'feature_names': self.feature_names_, 'imputer': self.imputer, 'timeframe': self.timeframe, 'archetype': self.archetype, 'hyperparams': {...}}`
  - Use `joblib.dump()`
- Class method: `load(cls, path: Path) -> PerformanceDiagnosticModel`
  - Load using `joblib.load()`
  - Reconstruct instance: `instance = cls(data['timeframe'], data['archetype'])`
  - Set attributes: `instance.model = data['model']`, etc.
  - Return instance
- Method: `get_model_key(self) -> str`
  - Return `f"{self.timeframe}_{self.archetype}"`

### 12. [ ] Update ai/models/__init__.py to export PerformanceDiagnosticModel
- Edit file: `src/trading_platform/ai/models/__init__.py`
- Add import: `from trading_platform.ai.models.performance_diagnostic import PerformanceDiagnosticModel`
- Update `__all__`: `["ProfitabilityModel", "ModelRegistry", "PerformanceDiagnosticModel"]`

---

## Phase 5: Move Rule-Based Analysis to reporting/diagnostics/

### 13. [ ] Copy synthesis/rules.py to reporting/diagnostics/
- Copy file: `src/trading_platform/ai/synthesis/rules.py` → `src/trading_platform/reporting/diagnostics/rules.py`
- No code changes in this step (just copy)

### 14. [ ] Copy synthesis/recommendations.py to reporting/diagnostics/
- Copy file: `src/trading_platform/ai/synthesis/recommendations.py` → `src/trading_platform/reporting/diagnostics/recommendations.py`
- No code changes in this step (just copy)

### 15. [ ] Write tests for RuleBasedAnalyzer
- Create file: `tests/reporting/diagnostics/test_rule_based.py`
- Test class: `TestRuleBasedAnalyzer`
- Test methods:
  - `test_run_executes_all_rules()` - Verify all rules evaluated
  - `test_run_stores_conclusions()` - Verify conclusions stored
  - `test_generate_report_markdown()` - Verify markdown generation
  - `test_generate_report_json()` - Verify JSON generation
  - `test_with_empty_analysis_data()` - Verify handles empty input
  - `test_generate_recommendations()` - Verify recommendation generation

### 16. [ ] Create RuleBasedAnalyzer class
- Create file: `src/trading_platform/reporting/diagnostics/rule_based.py`
- Copy content from `src/trading_platform/ai/synthesis/engine.py`
- Rename class: `DiagnosticSynthesisEngine` → `RuleBasedAnalyzer`
- Update imports to reference local modules:
  - `from trading_platform.reporting.diagnostics.recommendations import generate_recommendations`
  - `from trading_platform.reporting.diagnostics.rules import get_all_rules`
- Remove any references to `ai.synthesis` module
- Keep all existing functionality intact (just rename and update imports)

### 17. [ ] Update reporting/diagnostics/__init__.py
- Edit file: `src/trading_platform/reporting/diagnostics/__init__.py`
- Add import: `from trading_platform.reporting.diagnostics.rule_based import RuleBasedAnalyzer`
- Add to `__all__`: `["RuleBasedAnalyzer"]`

---

## Phase 6: Update CLI for Multi-Model Support

### 18. [ ] Update cli.py to support ModelRegistry
- Edit file: `src/trading_platform/cli.py`
- Function: `cmd_ai_diagnose()`
- Replace imports:
  - OLD: `from trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine`
  - NEW: `from trading_platform.reporting.diagnostics import RuleBasedAnalyzer`
  - OLD: `from trading_platform.ai.lab.trainer import train_profitability_model, save_model`
  - NEW: `from trading_platform.ai.models import ProfitabilityModel, ModelRegistry, PerformanceDiagnosticModel`

### 19. [ ] Add --train-profitability-models flag (plural)
- Edit file: `src/trading_platform/cli.py`
- Add new CLI flag: `--train-profitability-models` (note: plural)
- Implementation:
  - Load enriched parquet from campaign: `df = pd.read_parquet(enriched_path)`
  - Create registry: `registry = ModelRegistry()`
  - Train all profitability models: `results = registry.train_all_profitability_from_enriched(df, min_trades=50)`
  - Save all models: `registry.save_all_profitability()`
  - Print summary table:
    ```
    Trained 5 profitability models:
    - 5min_trend: 150 trades
    - 15min_trend: 200 trades
    - 1h_mean_reversion: 80 trades
    - 4h_swing: 120 trades
    - 1d_position: 60 trades

    Skipped (insufficient data):
    - 5min_mean_reversion: only 30 trades (need 50+)
    ```

### 20. [ ] Add --train-diagnostic-models flag (plural)
- Edit file: `src/trading_platform/cli.py`
- Add new CLI flag: `--train-diagnostic-models` (note: plural)
- Implementation:
  - Load enriched parquet from campaign
  - Create registry: `registry = ModelRegistry()`
  - Train all diagnostic models: `results = registry.train_all_diagnostic_from_enriched(df, min_trades=50)`
  - Save all models: `registry.save_all_diagnostic()`
  - Print summary table with feature importance for each model:
    ```
    Trained 5 diagnostic models:
    - 5min_trend: 150 trades, top features: [exit_volatility, bars_held, exit_rsi]
    - 15min_trend: 200 trades, top features: [exit_momentum, entry_rsi, bars_held]
    - 1h_mean_reversion: 80 trades, top features: [exit_price_change, entry_ma_dist, bars_held]

    Skipped (insufficient data):
    - 5min_mean_reversion: only 30 trades (need 50+)
    ```

### 21. [ ] Add --list-models flag
- Edit file: `src/trading_platform/cli.py`
- Add new CLI flag: `--list-models`
- Implementation:
  - Create registry: `registry = ModelRegistry()`
  - Load all: `registry.load_all()`
  - List models: `models = registry.list_all_models()`
  - Print formatted table with type, timeframe, archetype, path, and last modified date
  - Group by model type (profitability vs diagnostic)

### 22. [ ] Add --predict-profitability flag
- Edit file: `src/trading_platform/cli.py`
- Add new CLI flag: `--predict-profitability`
- Implementation:
  - Parse entry context from user input (JSON or dict)
  - Extract timeframe and archetype from context
  - Load registry: `registry = ModelRegistry(); registry.load_all_profitability()`
  - Get model: `model = registry.get_or_load_profitability(timeframe, archetype)`
  - If not found: `print(f"No profitability model found for {timeframe}_{archetype}. Available models: {registry.list_profitability_models()}")`
  - Predict: `prediction = model.predict_proba(entry_features)`
  - Print: `"Probability of profitable trade: {prediction[1]:.2%}"`

### 23. [ ] Add --analyze-performance flag
- Edit file: `src/trading_platform/cli.py`
- Add new CLI flag: `--analyze-performance`
- Implementation:
  - Parse trade data from user input (JSON with all features including lookahead)
  - Extract timeframe and archetype from context
  - Load registry: `registry = ModelRegistry(); registry.load_all_diagnostic()`
  - Get model: `model = registry.get_or_load_diagnostic(timeframe, archetype)`
  - If not found: `print(f"No diagnostic model found for {timeframe}_{archetype}. Available models: {registry.list_diagnostic_models()}")`
  - Predict: `quintile = model.predict(trade_features)`
  - Get probabilities: `probs = model.predict_proba(trade_features)`
  - Print: `"Performance quintile: {quintile[0]} (0=worst, 4=best)"`
  - Print: `"Quintile probabilities: Q0={probs[0]:.1%}, Q1={probs[1]:.1%}, Q2={probs[2]:.1%}, Q3={probs[3]:.1%}, Q4={probs[4]:.1%}"`
  - Print feature importance for this model

### 24. [ ] Update argument parser
- Edit file: `src/trading_platform/cli.py`
- Update CLI argument definitions:
  - Remove: `--train-model` (old singular)
  - Add: `--train-profitability-models` (plural) - trains all context-specific profitability models
  - Add: `--train-diagnostic-models` (plural) - trains all context-specific diagnostic models
  - Add: `--list-models` - lists all trained models (both types)
  - Add: `--predict-profitability` - uses profitability model for signal filtering
  - Add: `--analyze-performance` - uses diagnostic model for regime analysis

### 25. [ ] Update ai/training/pipeline.py imports
- Edit file: `src/trading_platform/ai/training/pipeline.py`
- Replace import (line 24):
  - OLD: `from trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine`
  - NEW: `from trading_platform.reporting.diagnostics import RuleBasedAnalyzer`
- Update usage (lines 201-210):
  - Replace `DiagnosticSynthesisEngine` → `RuleBasedAnalyzer`

---

## Phase 7: Delete Old Code

### 25. [ ] Delete ai/synthesis/ module
- Delete directory: `src/trading_platform/ai/synthesis/` (entire directory)
- Files to be deleted:
  - `src/trading_platform/ai/synthesis/__init__.py`
  - `src/trading_platform/ai/synthesis/engine.py`
  - `src/trading_platform/ai/synthesis/rules.py`
  - `src/trading_platform/ai/synthesis/recommendations.py`

### 26. [ ] Delete ai/lab/trainer.py
- Delete file: `src/trading_platform/ai/lab/trainer.py`
- Functionality now in `ai/models/profitability.py`

### 27. [ ] Delete ai/lab/predictor.py (if no longer needed)
- Check if `ai/lab/predictor.py` is used anywhere else
- If `get_trade_insights()` is used by RuleBasedAnalyzer:
  - Move function to `reporting/diagnostics/insights.py`
  - Update import in `rule_based.py`
- Delete file: `src/trading_platform/ai/lab/predictor.py`

---

## Phase 8: Update Tests

### 28. [ ] Update existing tests that import from ai/synthesis/
- Find all test files importing from `ai.synthesis`:
  ```bash
  grep -r "from trading_platform.ai.synthesis" tests/
  ```
- Update each file to import from `reporting.diagnostics` instead
- Replace `DiagnosticSynthesisEngine` → `RuleBasedAnalyzer`

### 29. [ ] Update existing tests that import from ai/lab/trainer
- Find all test files importing from `ai.lab.trainer`:
  ```bash
  grep -r "from trading_platform.ai.lab.trainer" tests/
  ```
- Update each file to import from `ai.models` instead
- Replace `train_profitability_model()` function calls with `ProfitabilityModel(timeframe, archetype).fit()`

### 30. [ ] Run all tests to verify no breakage
```bash
poetry run pytest --cov=src/trading_platform --cov-report=term-missing
```
- Verify 100% test coverage maintained for changed code
- Fix any failing tests

---

## Phase 9: Documentation Updates

### 31. [ ] Create docs/ai/02_profitability_model.md
- Create file: `docs/ai/02_profitability_model.md`
- Sections:
  - **Overview**: Multiple specialized models per timeframe/archetype
  - **Architecture**: Entry context features only, context-specific training
  - **Why Multiple Models**: Different timeframes have fundamentally different patterns
  - **Training**: How to train all models from enriched campaign data
  - **Usage Examples**:
    - Single model: `model = ProfitabilityModel('5min', 'trend_following'); model.fit(trades_df)`
    - Registry: `registry = ModelRegistry(); registry.train_all_from_enriched(df); registry.save_all()`
    - Prediction: `model = registry.get('5min', 'trend_following'); predictions = model.predict(entry_features)`
  - **Model Selection**: How to choose the right model for a given context
  - **CLI**:
    - Train all: `tp ai-diagnose --campaign-id <id> --train-profitability-models`
    - List models: `tp ai-diagnose --list-models`
    - Predict: `tp ai-diagnose --predict --timeframe 5min --archetype trend_following --features <json>`

### 32. [ ] Create docs/ai/03_model_registry.md
- Create file: `docs/ai/03_model_registry.md`
- Sections:
  - **Overview**: Central registry for managing multiple profitability models
  - **Purpose**: Route predictions to the correct model based on context
  - **Storage**: File system layout (`models/profitability/<timeframe>_<archetype>.pkl`)
  - **Batch Training**: How `train_all_from_enriched()` discovers contexts and trains models
  - **Lazy Loading**: Models loaded on-demand to save memory
  - **Usage Examples**:
    - Create registry: `registry = ModelRegistry()`
    - Load all models: `registry.load_all()`
    - Get specific model: `model = registry.get_or_load('5min', 'trend_following')`
    - List available: `models = registry.list_models()`
  - **Integration**: How to use in live trading systems

### 33. [ ] Create docs/ai/04_performance_diagnostic_model.md
- Create file: `docs/ai/04_performance_diagnostic_model.md`
- Sections:
  - **Overview**: Multiple specialized models for regime analysis (context-specific)
  - **Why Multiple Models**: Each timeframe/archetype has unique performance drivers
  - **Architecture**: All features including post_exit_analysis (lookahead allowed)
  - **Target Variable**: Performance quintiles (0-4)
  - **Training**: How to train all models from enriched campaign data
  - **Usage Examples**:
    - Single model: `model = PerformanceDiagnosticModel('5min', 'trend_following'); model.fit(trades_df)`
    - Registry: `registry = ModelRegistry(); registry.train_all_diagnostic_from_enriched(df); registry.save_all_diagnostic()`
    - Analysis: `model = registry.get_diagnostic('5min', 'trend_following'); quintiles = model.predict(trades_df)`
    - Feature Importance: `model.get_feature_importance()`
  - **Use Cases**:
    - "What market conditions produce top 20% trades for 5min trend following?"
    - "Which features matter most for performance in 1h mean reversion?"
    - "When should I trade this specific timeframe/archetype?"
  - **CLI**: `tp ai-diagnose --campaign-id <id> --train-diagnostic-models`

### 34. [ ] Create docs/ai/05_rule_based_analyzer.md
- Create file: `docs/ai/05_rule_based_analyzer.md`
- Sections:
  - **Overview**: Rule-based heuristic analysis (NOT ML)
  - **Purpose**: Quick diagnostic insights without model training
  - **Location**: Moved from `ai/synthesis/` to `reporting/diagnostics/`
  - **Available Rules**:
    - List all rules from `diagnostics/rules.py`
    - Explain what each rule checks
  - **Adding Custom Rules**:
    - Inherit from `BaseDiagnosticRule`
    - Implement `evaluate()` method
    - Return `DiagnosticConclusion` or `None`
  - **Usage**: Automatic in `tp ai-diagnose --brief <path>`
  - **Output**: Markdown and JSON reports

### 35. [ ] Update docs/ai/01_overview.md
- Edit file: `docs/ai/01_overview.md`
- Update **Module Structure** section:
  - Show new `ai/models/` directory with profitability.py, registry.py, performance_diagnostic.py
  - Show `reporting/diagnostics/` directory
  - Remove references to `ai/synthesis/`
- Add **Three Distinct Components** section:
  - **ProfitabilityModels (Many)**: Context-specific predictive models (entry features only)
  - **PerformanceDiagnosticModels (Many)**: Context-specific diagnostic models (all features including lookahead)
  - **ModelRegistry**: Central manager for routing to correct model (both types)
  - **RuleBasedAnalyzer**: Heuristic rules for quick insights
- Add **Multi-Model Architecture** section:
  - Explain why multiple specialized models (both profitability and diagnostic)
  - Different timeframes have fundamentally different patterns
  - Show decision tree for which model to use when
  - Profitability models: real-time signal filtering (no lookahead)
  - Diagnostic models: offline regime analysis (uses lookahead)
- Update architecture diagram showing parallel model families

### 36. [ ] Update docs/ai/06_campaign_runner_guide.md
- Edit file: `docs/ai/06_campaign_runner_guide.md`
- Add new section after Step 6 (Enrichment): **Step 7: Train Models**
  - **7a: Train All Profitability Models**:
    - Command: `poetry run tp ai-diagnose --campaign-id <id> --train-profitability-models`
    - Explains automatic context discovery
    - Shows expected output with model counts per context
  - **7b: Train All Diagnostic Models**:
    - Command: `poetry run tp ai-diagnose --campaign-id <id> --train-diagnostic-models`
    - Explains context-specific training (one model per timeframe/archetype)
    - Shows feature importance output for each model
  - **7c: List Trained Models**:
    - Command: `poetry run tp ai-diagnose --list-models`
    - Shows model inventory (both profitability and diagnostic)
    - Grouped by model type
- Update any references to old module paths

### 37. [ ] Update README.md (if applicable)
- Edit file: `README.md` (project root)
- Update AI features section to mention multi-model architecture
- Update module structure references
- Update quickstart examples to show ModelRegistry usage

### 38. [ ] Create migration guide
- Create file: `docs/ai/MIGRATION_GUIDE.md`
- Sections:
  - **Breaking Changes Summary**
  - **Architecture Change**: Single model → Multiple specialized models
  - **Import Changes**:
    - OLD: `from trading_platform.ai.synthesis.engine import DiagnosticSynthesisEngine`
    - NEW: `from trading_platform.reporting.diagnostics import RuleBasedAnalyzer`
    - OLD: `from trading_platform.ai.lab.trainer import train_profitability_model`
    - NEW: `from trading_platform.ai.models import ProfitabilityModel, ModelRegistry`
  - **API Changes**:
    - OLD: `model, features = train_profitability_model(brief_data)`
    - NEW:
      ```python
      registry = ModelRegistry()
      registry.train_all_from_enriched(enriched_df)
      registry.save_all()
      model = registry.get('5min', 'trend_following')
      ```
  - **CLI Changes**:
    - OLD: `--train-model` (singular, context-agnostic)
    - NEW: `--train-profitability-models` (plural, creates one profitability model per context)
    - NEW: `--train-diagnostic-models` (plural, creates one diagnostic model per context)
    - NEW: `--list-models` (inventory management for both model types)
    - NEW: `--predict-profitability` (uses profitability models)
    - NEW: `--analyze-performance` (uses diagnostic models)
  - **File Changes**: List of deleted/moved files
  - **Model Storage**: Old vs new directory structure (`models/profitability/` and `models/diagnostic/`)

---

## Phase 10: Integration Testing

### 39. [ ] Test ProfitabilityModel with real campaign data
- Load enriched parquet from completed campaign
- Verify multiple contexts exist in data
- Train models for 2-3 specific contexts manually
- Verify predictions are reasonable (0/1)
- Verify probabilities sum to 1.0
- Check feature importance makes sense
- Save models and verify they load correctly

### 40. [ ] Test ModelRegistry with real campaign data
- Load enriched parquet with multiple timeframe/archetype combinations
- Create registry: `registry = ModelRegistry()`
- Train all: `results = registry.train_all_from_enriched(df, min_trades=50)`
- Verify correct number of models created
- Verify models skipped with insufficient data
- Save all: `registry.save_all()`
- Verify files created in correct locations
- Load all: `registry.load_all()`
- Test retrieval: `model = registry.get('5min', 'trend_following')`
- Test prediction routing

### 41. [ ] Test PerformanceDiagnosticModel with real campaign data
- Load enriched parquet from completed campaign (must have post_exit_analysis data)
- Verify data includes multiple contexts
- Train models for 2-3 specific contexts manually
- Verify quintile distribution per context (should be ~20% per quintile)
- Check feature importance - verify post_exit features show up
- Compare feature importance across different contexts (5min vs 1h, trend vs mean_reversion)
- Analyze top quintile for each model: print top 10 trades and their common features
- Save models and verify they load correctly

### 42. [ ] Test RuleBasedAnalyzer with real backtest
- Run backtest: `poetry run tp run-backtest --config <config>`
- Run analyzer: `poetry run tp ai-diagnose --brief <path>`
- Verify reports generated (markdown + JSON)
- Verify recommendations added to brief.json
- Check that no errors occur

### 43. [ ] Test full workflow: campaign → enrichment → all models
- Run complete campaign workflow (plan → run → validate → review → approve → enrich)
- Train profitability models:
  ```bash
  poetry run tp ai-diagnose --campaign-id <id> --train-profitability-models
  ```
- Train diagnostic models:
  ```bash
  poetry run tp ai-diagnose --campaign-id <id> --train-diagnostic-models
  ```
- List models:
  ```bash
  poetry run tp ai-diagnose --list-models
  ```
- Verify all models saved correctly in proper directory structure
- Load registry and test profitability predictions for each context
- Load registry and test diagnostic analysis for each context
- Compare feature importance between profitability and diagnostic models for same context
- Verify diagnostic models include post_exit features that profitability models don't have

---

## Phase 11: Code Review and Cleanup

### 44. [ ] Run linting and formatting
```bash
poetry run ruff check .
poetry run ruff format .
poetry run mypy src/trading_platform/ai/models/
poetry run mypy src/trading_platform/reporting/diagnostics/
```

### 45. [ ] Verify test coverage
```bash
poetry run pytest --cov=src/trading_platform --cov-report=html
```
- Open `htmlcov/index.html`
- Verify 100% coverage for:
  - `ai/models/profitability.py`
  - `ai/models/registry.py`
  - `ai/models/performance_diagnostic.py`
  - `reporting/diagnostics/rule_based.py`

### 46. [ ] Create pull request
- Commit all changes
- Push branch: `git push origin refactor/ml-models-architecture`
- Create PR with description:
  - Summary of multi-model architecture
  - Breaking changes listed
  - Link to migration guide
  - Test coverage proof
  - Example usage for common scenarios

---

## Completion Checklist

- [ ] All 46 tasks completed
- [ ] All tests passing (`pytest`)
- [ ] 100% test coverage maintained
- [ ] All documentation updated
- [ ] No references to deleted modules (`ai/synthesis/`, `ai/lab/trainer.py`)
- [ ] ModelRegistry works with real campaign data (both model types)
- [ ] Multiple profitability models train and predict correctly per context
- [ ] Multiple diagnostic models train and analyze correctly per context
- [ ] CLI commands updated and tested (all 6 new flags)
- [ ] Migration guide created
- [ ] Code review completed
- [ ] PR merged to main

---

## Summary of Multi-Model Architecture

### Predictive Models (Many)
- **One ProfitabilityModel per timeframe/archetype combination**
- Each model specializes in its specific trading context
- Examples: `5min_trend`, `15min_mean_reversion`, `1h_swing`, `4h_position`
- Managed by ModelRegistry for routing
- Trained from `context_at_entry_*` features only (no lookahead)
- Used in real-time for signal filtering

### Diagnostic Models (Many)
- **One PerformanceDiagnosticModel per timeframe/archetype combination**
- Each model specializes in understanding performance patterns for its specific context
- Examples: `diagnostic_5min_trend`, `diagnostic_15min_mean_reversion`, `diagnostic_1h_swing`
- Managed by ModelRegistry for routing
- Trained on ALL features including `post_exit_analysis_*` (lookahead allowed)
- Used offline for regime analysis
- Answers: "What conditions produce best trades for THIS specific timeframe/archetype?"

### Rule-Based Analyzer (One)
- **Heuristic rules for quick diagnostics**
- No ML, no training required
- Fast insights for strategy debugging
- Located in `reporting/diagnostics/`
