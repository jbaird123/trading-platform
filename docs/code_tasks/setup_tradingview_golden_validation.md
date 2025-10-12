# TradingView Golden Validation Testing Strategy

**Status:** Draft - To be implemented after ML Data Curation Pipeline

**Prerequisites:**
- `docs/code_tasks/setup_ml_data_curation_pipeline.md` must be completed first
- DVC must be configured and working

---

## Overview

This plan implements comprehensive validation testing by comparing our platform's
calculations against TradingView exports. We validate both:

1. **Indicator calculations** - Ensure our pandas-ta calculations match TradingView
2. **Strategy execution** - Ensure our backtests produce same trades/PnL as TradingView

---

## Current State

### What Already Exists ✅

We already have basic indicator validation:

**Files:**
- `tests/data/test_golden_datasets.py` - 8 passing tests validating indicators
- `data/fixtures/eurusd_1h_sample.csv` - TradingView export with indicators
- `data/fixtures/eurusd_1min_sample.csv` - 1-minute data for resampling tests

**Validated Indicators:**
- EMA (20, 50)
- RSI (14)
- ADX (14)
- ATR (14)
- Bollinger Bands (20, 2.0)

**Test Status:** All passing with appropriate tolerances for library differences

### What's Missing ❌

1. **Strategy/Trade Validation** - No comparison of backtest trades vs TradingView
2. **PnL Validation** - No comparison of equity curves
3. **Comprehensive Indicator Coverage** - Missing MACD, Stochastic, CCI, etc.
4. **PineScript Reference Implementations** - No reference strategies
5. **Larger Golden Datasets** - Current samples are small (164KB + 712KB)

---

## Proposed Directory Structure

### Data Organization

```
data/
├── dvc/
│   ├── raw/                     # From ML pipeline (already planned)
│   │   ├── full/
│   │   └── incremental/
│   │
│   ├── golden/                  # NEW - Golden validation datasets (DVC-tracked)
│   │   ├── indicators/
│   │   │   ├── eurusd_1h_full.csv        # Comprehensive dataset
│   │   │   ├── eurusd_4h_full.csv        # Multiple timeframes
│   │   │   ├── gbpusd_1h_full.csv        # Multiple instruments
│   │   │   └── metadata.json             # Dataset catalog
│   │   │
│   │   └── strategies/          # Strategy validation datasets
│   │       ├── ema_crossover/
│   │       │   ├── ohlcv.csv             # Market data used
│   │       │   ├── trades.csv            # TradingView trade export
│   │       │   └── equity_curve.csv      # Running equity
│   │       │
│   │       ├── bb_mean_reversion/
│   │       │   ├── ohlcv.csv
│   │       │   ├── trades.csv
│   │       │   └── equity_curve.csv
│   │       │
│   │       └── multi_indicator_strategy/
│   │           ├── ohlcv.csv
│   │           ├── trades.csv
│   │           └── equity_curve.csv
│   │
│   └── processed/               # From ML pipeline (already planned)
│       └── training_sets/
│
└── fixtures/                    # Small test data (git-committed)
    ├── eurusd_1h_sample.csv     # Existing - keep as-is
    ├── eurusd_1min_sample.csv   # Existing - keep as-is
    └── README.md
```

### Configuration & Code Organization

```
configs/
└── golden_strategies/           # NEW - Reference strategy implementations
    ├── ema_crossover/
    │   ├── strategy.yaml         # Our platform's strategy definition
    │   ├── strategy.pine         # PineScript equivalent
    │   ├── run_config.yaml       # Backtest configuration
    │   ├── rem.yaml             # Risk/exit management
    │   └── README.md            # How to run in TradingView & regenerate
    │
    ├── bb_mean_reversion/
    │   ├── strategy.yaml
    │   ├── strategy.pine
    │   ├── run_config.yaml
    │   ├── rem.yaml
    │   └── README.md
    │
    └── multi_indicator_strategy/
        └── ... (same structure)

tests/
├── data/
│   ├── test_golden_datasets.py          # Existing - keep as-is
│   └── test_golden_data_validation.py   # Existing placeholder
│
└── validation/                          # NEW - Comprehensive validation
    ├── test_indicator_validation.py     # Expanded indicator tests
    ├── test_strategy_validation.py      # Trade/PnL comparison
    └── conftest.py                      # Shared fixtures
```

---

## Implementation Phases

### Phase 1: Expand Indicator Coverage

**Goal:** Validate all indicators used in our strategies

#### 1.1 Additional Indicators to Test
- [ ] MACD (and signal/histogram)
- [ ] Stochastic Oscillator
- [ ] CCI (Commodity Channel Index)
- [ ] Any other indicators your strategies use

#### 1.2 Export Process
1. Open TradingView chart
2. Add all indicators with same parameters as platform
3. Export to CSV with indicators included
4. Place in `data/dvc/golden/indicators/`
5. Track with DVC: `dvc add data/dvc/golden/indicators/`

#### 1.3 Test Implementation
- Create `tests/validation/test_indicator_validation.py`
- Parametrize tests for all indicators
- Use DVC-tracked datasets
- Document tolerances and rationale

---

### Phase 2: Strategy Selection & PineScript Development

**Goal:** Choose 3-5 representative strategies and implement PineScript versions

#### 2.1 Recommended Strategy Selection

**Start Simple, Add Complexity:**

1. **Simple EMA Crossover** (Easiest - Start Here)
   - Purpose: Baseline validation
   - Complexity: Low
   - Entry: EMA 20 crosses above EMA 50 (long)
   - Exit: EMA 20 crosses below EMA 50
   - Why: Minimal indicator complexity, easy to debug

2. **BB Mean Reversion** (Medium)
   - Purpose: Test indicator calculations
   - Complexity: Medium
   - Entry: Price touches lower BB
   - Exit: Price reaches middle BB or upper BB
   - Why: Tests Bollinger Band calculations

3. **Multi-Indicator Strategy** (Complex)
   - Purpose: Test feature combination
   - Complexity: High
   - Entry: EMA cross + RSI < 30 + ADX > 25
   - Exit: RSI > 70 or stop loss
   - Why: Tests multiple indicators working together

4. **Time-Filtered Strategy** (Optional)
   - Purpose: Test session handling
   - Entry: EMA cross + within London session
   - Why: Tests time/session filters

5. **ATR-Based Stop Strategy** (Optional)
   - Purpose: Test risk management
   - Entry: EMA cross
   - Exit: ATR-based trailing stop
   - Why: Tests dynamic risk management

#### 2.2 PineScript Development Workflow

For each strategy:

1. **Write PineScript Version**
   - Mirror YAML strategy exactly
   - Same indicator parameters
   - Same entry/exit logic
   - Use fixed position size (e.g., 1 contract)
   - Initially NO stop-loss/take-profit (validate signals first)

2. **Document Parameters**
   - TradingView version used
   - Date range used
   - Indicator settings
   - Commission settings (if any)

3. **Export Format Requirements**

   **Trades Export (CSV):**
   ```
   Columns: Entry Time, Entry Price, Exit Time, Exit Price,
            Side (Long/Short), Profit, Cumulative Profit,
            Size (contracts/shares)
   ```

   **Equity Curve Export (CSV):**
   ```
   Columns: Timestamp, Equity, Drawdown
   ```

4. **Metadata File (JSON)**
   ```json
   {
     "strategy_name": "ema_crossover",
     "tradingview_version": "TradingView Pro 2025.1",
     "export_date": "2025-10-10",
     "date_range": {
       "start": "2023-01-01",
       "end": "2024-12-31"
     },
     "instrument": "EURUSD",
     "timeframe": "1H",
     "position_size": 1.0,
     "commission": 0.0,
     "initial_capital": 100000.0
   }
   ```

---

### Phase 3: Trade & PnL Validation Framework

**Goal:** Build automated comparison between our trades and TradingView trades

#### 3.1 Tolerance Strategy

Define acceptable variances:

```python
TRADE_VALIDATION_TOLERANCES = {
    "entry_time": timedelta(minutes=0),   # Exact match required
    "exit_time": timedelta(minutes=0),    # Exact match required
    "entry_price": 0.0001,                # 1 pip for forex (0.01%)
    "exit_price": 0.0001,                 # 1 pip for forex
    "trade_pnl": 0.50,                    # $0.50 per trade
    "total_pnl": 1.00,                    # $1.00 total
    "trade_count": 0,                     # Must match exactly
}

EQUITY_CURVE_TOLERANCES = {
    "correlation": 0.999,                 # r > 0.999
    "final_equity": 1.00,                 # $1.00 difference
}

METRICS_TOLERANCES = {
    "win_rate": 0.01,                     # 1 percentage point
    "profit_factor": 0.05,                # 5% difference
    "max_drawdown": 0.02,                 # 2% difference
}
```

#### 3.2 Test Implementation

**File:** `tests/validation/test_strategy_validation.py`

**Key Test Functions:**

```python
def test_trade_count_matches_tradingview():
    """Trade count must match exactly"""

def test_trade_times_match_tradingview():
    """Entry/exit times must match within tolerance"""

def test_trade_prices_match_tradingview():
    """Entry/exit prices must match within tolerance"""

def test_trade_pnl_matches_tradingview():
    """Individual and total PnL must match"""

def test_equity_curve_correlation():
    """Equity curves should be highly correlated"""

def test_final_metrics_match():
    """Win rate, profit factor, etc. should match"""
```

**Helper Functions Needed:**

```python
def load_tradingview_trades(strategy_name: str) -> pd.DataFrame:
    """Load TradingView trade export"""

def load_platform_trades(strategy_name: str) -> list[Trade]:
    """Run backtest and return trades"""

def align_trades(
    our_trades: list[Trade],
    tv_trades: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Align trades by entry time for comparison"""

def compare_trade_sequences(
    our_trades: pd.DataFrame,
    tv_trades: pd.DataFrame,
    tolerances: dict
) -> dict[str, Any]:
    """Compare and report differences"""

def calculate_equity_curve(trades: list[Trade]) -> pd.Series:
    """Calculate running equity from trades"""

def compare_metrics(
    our_metrics: dict,
    tv_metrics: dict,
    tolerances: dict
) -> bool:
    """Compare aggregate metrics"""
```

#### 3.3 Pytest Fixtures

**File:** `tests/validation/conftest.py`

```python
@pytest.fixture(scope="module")
def dvc_golden_data():
    """Ensure DVC data is pulled before tests"""
    # Check if data exists, run dvc pull if needed

@pytest.fixture
def golden_strategy_config(strategy_name):
    """Load strategy config from configs/golden_strategies/"""

@pytest.fixture
def tradingview_trades(strategy_name):
    """Load TradingView trade export"""

@pytest.fixture
def platform_trades(strategy_name, golden_strategy_config):
    """Run backtest and return our trades"""
```

---

### Phase 4: Data Export & DVC Setup

#### 4.1 TradingView Export Process

**Document:** `configs/golden_strategies/README.md`

1. Open TradingView
2. Load strategy from PineScript file
3. Set date range (e.g., 2023-01-01 to 2024-12-31)
4. Set initial capital ($100,000)
5. Set position size (1 contract)
6. Disable commission (or set to known value)
7. Run backtest
8. Export trades to CSV
9. Export equity curve (if possible)
10. Take screenshot of backtest results
11. Record metadata (TV version, date, parameters)

#### 4.2 File Placement

```bash
# For each strategy:

# 1. Place data files
data/dvc/golden/strategies/ema_crossover/
├── ohlcv.csv           # Market data
├── trades.csv          # TradingView export
└── equity_curve.csv    # TradingView equity

# 2. Place configs
configs/golden_strategies/ema_crossover/
├── strategy.yaml       # Your platform config
├── strategy.pine       # PineScript source
├── run_config.yaml
├── rem.yaml
└── README.md           # How to regenerate
```

#### 4.3 DVC Tracking

```bash
# Track golden datasets
dvc add data/dvc/golden/indicators/
dvc add data/dvc/golden/strategies/

# Push to S3
dvc push

# Commit DVC pointer files
git add data/dvc/golden/.dvc
git commit -m "data: Track golden validation datasets"
```

---

### Phase 5: Documentation

#### 5.1 Main Documentation

**File:** `docs/testing/tradingview_validation.md`

**Contents:**
- Purpose and rationale
- How to export data from TradingView
- How to add new golden strategies
- Tolerance rationale
- Troubleshooting guide
- When to regenerate datasets

#### 5.2 Per-Strategy Documentation

**File:** `configs/golden_strategies/{strategy_name}/README.md`

**Contents:**
- Strategy description
- TradingView setup instructions
- Parameter values used
- Export process
- Last regenerated date
- Known differences/tolerances

#### 5.3 Dataset Documentation

**File:** `data/dvc/golden/README.md` (committed to git, not tracked by DVC)

**Contents:**
- Dataset inventory
- Which TradingView version was used
- When each dataset was generated
- How to regenerate
- DVC commands to pull data

---

## Implementation Order

### Recommended Sequence:

1. **Start Small - One Strategy End-to-End**
   - [ ] Pick simplest strategy (EMA crossover)
   - [ ] Write PineScript version
   - [ ] Export from TradingView
   - [ ] Place files in correct locations
   - [ ] Track with DVC
   - [ ] Write comparison test
   - [ ] Tune tolerances until passing

2. **Validate Framework is Reusable**
   - [ ] Add 2nd strategy (BB mean reversion)
   - [ ] Ensure helper functions are generic
   - [ ] Refactor any hard-coded values

3. **Expand Coverage**
   - [ ] Add remaining strategies (3-5 total)
   - [ ] Add more indicators to indicator validation
   - [ ] Document everything

4. **CI/CD Integration**
   - [ ] Decide if validation tests run on every commit or manually
   - [ ] Set up DVC pull in CI if needed
   - [ ] Create "validation" test marker for pytest

---

## Open Questions & Decisions Needed

### 1. Tolerance Levels
**Question:** How strict should matching be?

**Options:**
- **Strict:** Exact match on trade count, ≤1 pip on prices
- **Moderate:** Allow 1-2 trades difference, ≤5 pips on prices
- **Lenient:** Focus on final PnL being close, allow execution differences

**Recommendation:** Start strict, loosen if needed

---

### 2. Data Source
**Question:** Should we use existing market data or export fresh from TradingView?

**Options:**
- **Option A:** Use our existing data (`data/dvc/raw/`)
  - Pros: Consistency, already have it
  - Cons: TV might not have same data source

- **Option B:** Export OHLCV from TradingView along with trades
  - Pros: Guaranteed same data source
  - Cons: Redundant data storage

**Recommendation:** Option B - export from TV to ensure exact match

---

### 3. Test Organization
**Question:** Should these be part of regular test suite or separate?

**Options:**
- **Option A:** Regular test suite (run on every commit)
  - Pros: Continuous validation
  - Cons: Slower, requires DVC pull

- **Option B:** Separate "validation" suite (run manually/pre-release)
  - Pros: Faster CI, intentional validation
  - Cons: Might forget to run

**Recommendation:** Option B with pytest markers:
```python
@pytest.mark.validation
def test_strategy_matches_tradingview():
    ...
```

Run with: `pytest -m validation`

---

### 4. Risk Management Testing
**Question:** Should we validate stop-loss/take-profit logic?

**Options:**
- **Phase 1:** Validate signals only (no stops)
- **Phase 2:** Add stop-loss validation later

**Recommendation:** Phase 1 approach - get signals right first

---

### 5. Dataset Size
**Question:** How much data should golden datasets contain?

**Options:**
- **Small:** 1 month (fast tests, limited coverage)
- **Medium:** 1 year (good balance)
- **Large:** 3+ years (comprehensive, slow)

**Recommendation:** Start with 1 year, expand if needed

---

## Success Criteria

### Phase 1 (Indicators) Complete When:
- [ ] All platform indicators validated against TradingView
- [ ] Tests pass with documented tolerances
- [ ] Tolerances documented and justified

### Phase 2 (Strategies) Complete When:
- [ ] 3+ strategies validated end-to-end
- [ ] Trade counts match exactly
- [ ] PnL matches within $1.00
- [ ] All tests passing consistently

### Phase 3 (Documentation) Complete When:
- [ ] Export process documented
- [ ] Each strategy has README
- [ ] Tolerances explained
- [ ] Regeneration process documented

---

## Migration from Current State

### Do NOT Change These Files:
- ✅ Keep `data/fixtures/eurusd_1h_sample.csv` (already exists)
- ✅ Keep `data/fixtures/eurusd_1min_sample.csv` (already exists)
- ✅ Keep `tests/data/test_golden_datasets.py` (already working)
- ✅ Update paths in test file from `data/samples/` to `data/fixtures/`

### Add These New Directories:
```bash
# Data directories (DVC-tracked)
mkdir -p data/dvc/golden/indicators
mkdir -p data/dvc/golden/strategies

# Config directories (git-committed)
mkdir -p configs/golden_strategies

# Test directories
mkdir -p tests/validation
```

### Update .gitignore:
```
# Already planned for ML pipeline
/data/dvc/

# Should already be there, but confirm
*.pyc
__pycache__/
```

---

## Maintenance & Evolution

### When to Regenerate Golden Datasets:

1. **TradingView Updates** - If TV updates indicator calculations
2. **Indicator Library Changes** - If we change pandas-ta version
3. **New Strategies** - When adding new strategies to platform
4. **Data Quality Issues** - If we discover issues with current datasets

### Version Control Strategy:

- **DVC** tracks data versions automatically
- **Git** tracks config changes
- Tag releases with data version: `v1.0.0-golden-2025-10`

---

## References

### Existing Code to Review:
- `tests/data/test_golden_datasets.py` - Current indicator validation
- `tests/core/test_golden_brief.py` - Brief validation pattern
- `tests/fixtures/golden_run/` - Existing test fixture structure

### External Documentation:
- TradingView Pine Script documentation
- pandas-ta documentation
- DVC documentation

---

## Notes

- This plan assumes ML pipeline is completed first
- DVC must be working and configured
- S3 bucket must be available
- TradingView subscription may be required for data exports
- Consider starting with just 1-2 strategies before full implementation

---

### Phase 6: Formalizing Metadata with a JSON Schema (Recommended)

**Goal:** To ensure all golden validation datasets are consistently documented and
programmatically verifiable, preventing missing information and making the
validation process more robust and auditable over the long term.

#### 6.1 Rationale

While the plan includes creating `metadata.json` files, their structure is
informal. A formal JSON Schema provides several key benefits:

-   **Consistency:** Enforces that all required fields (like `tradingview_version`
    or `export_date`) are present in every metadata file.
-   **Validation:** Allows for automated checks to ensure the data types and
    formats are correct (e.g., dates are in `YYYY-MM-DD` format).
-   **Discoverability:** The schema itself serves as clear, machine-readable
    documentation for what constitutes a valid metadata file.

#### 6.2 Proposed Schema Definition

I recommend creating a new schema file at
`docs/schemas/golden_metadata.schema.json` with the following content. This
schema is designed to be flexible enough to describe metadata for both
individual strategy validations and general indicator datasets.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/golden_metadata.schema.json",
  "title": "Golden Validation Dataset Metadata",
  "description": "Metadata for a TradingView golden validation dataset.",
  "type": "object",
  "properties": {
    "dataset_type": {
      "description": "The type of validation data.",
      "type": "string",
      "enum": ["strategy", "indicator"]
    },
    "strategy_name": { "type": "string" },
    "tradingview_version": { "type": "string" },
    "export_date": { "type": "string", "format": "date" },
    "date_range": {
      "type": "object",
      "properties": {
        "start": { "type": "string", "format": "date" },
        "end": { "type": "string", "format": "date" }
      },
      "required": ["start", "end"]
    },
    "instrument": { "type": "string" },
    "timeframe": { "type": "string" },
    "initial_capital": { "type": "number" },
    "position_size": { "type": "number" },
    "commission": { "type": "number", "minimum": 0 }
  },
  "required": [
    "dataset_type", "tradingview_version", "export_date", "date_range",
    "instrument", "timeframe"
  ]
}
```

#### 6.3 How to Use the Schema

The schema can be integrated directly into the testing workflow. When a test
fixture loads a golden dataset for validation, it should first load the
accompanying `metadata.json` and validate it against this schema.

A helper function can be created in `tests/validation/conftest.py` or a similar
shared testing module.

**Example Validation Logic:**

```python
import json
from pathlib import Path
import jsonschema

def load_and_validate_golden_metadata(metadata_path: Path) -> dict:
    """Loads a metadata.json file and validates it against the schema."""

    # Define paths to schema and metadata
    schema_path = Path("docs/schemas/golden_metadata.schema.json")

    # Load schema and data
    with open(schema_path, "r") as f:
        schema = json.load(f)
    with open(metadata_path, "r") as f:
        metadata = json.load(f)

    # Validate
    jsonschema.validate(instance=metadata, schema=schema)

    return metadata

# This function would then be used in a pytest fixture
# to ensure all golden data is valid before a test runs.
```

By implementing this, we build a more reliable foundation for our entire
validation strategy, ensuring that as we add more golden datasets, their quality
and completeness are automatically maintained.

**Next Steps:**
1. Complete ML data curation pipeline
2. Review this plan
3. Choose first strategy to validate
4. Begin Phase 1 implementation

---

## Implementation Status (2025-10-11)

### ✅ Completed Tasks

#### Infrastructure Setup
- [x] Created directory structure:
  - `data/dvc/golden/indicators/`
  - `data/dvc/golden/strategies/ema_crossover/`
  - `data/dvc/golden/strategies/bb_mean_reversion/`
  - `data/dvc/golden/strategies/multi_indicator_strategy/`
  - `configs/golden_strategies/ema_crossover/`
  - `tests/validation/`

#### Schema & Metadata (Phase 6)
- [x] Created `docs/schemas/golden_metadata.schema.json`
  - Validates dataset metadata (TradingView exports)
  - Required fields: dataset_type, tradingview_version, etc.
  - Used by test fixtures for validation

#### EMA Crossover Strategy (Phase 2.1 - First Strategy)
- [x] Created platform strategy YAML:
  - `configs/golden_strategies/ema_crossover/strategy.yaml`
  - Simple EMA(20)/EMA(50) crossover
  - Long and short sides
  - No stop-loss/take-profit for baseline validation

- [x] Created risk/exit management:
  - `configs/golden_strategies/ema_crossover/rem.yaml`
  - No exit rules (signals only)

- [x] Created run configuration:
  - `configs/golden_strategies/ema_crossover/run_config.yaml`
  - $100k initial capital
  - $10k position size
  - No costs for baseline

- [x] Created PineScript equivalent:
  - `configs/golden_strategies/ema_crossover/strategy.pine`
  - Matches platform logic exactly
  - Same parameters and entry/exit rules
  - Ready for TradingView import

- [x] Created strategy README:
  - `configs/golden_strategies/ema_crossover/README.md`
  - Step-by-step TradingView export instructions
  - Parameter documentation
  - Regeneration guidelines

#### Test Framework (Phase 3)
- [x] Created `tests/validation/conftest.py`:
  - DVC data pull fixture
  - Strategy name extraction fixture
  - Golden paths fixture
  - Config loading fixtures
  - TradingView CSV loading fixtures
  - Metadata validation helper

- [x] Created `tests/validation/test_strategy_validation.py`:
  - Tolerance definitions
  - Helper functions:
    - `load_platform_trades()` (stub)
    - `align_trades()`
    - `compare_trade_sequences()`
    - `calculate_equity_curve()`
    - `compare_metrics()`
  - Test cases (all properly skip until data exists):
    - `test_ema_crossover_trade_count_matches_tradingview`
    - `test_ema_crossover_trade_times_match_tradingview`
    - `test_ema_crossover_trade_pnl_matches_tradingview`
    - `test_ema_crossover_equity_curve_correlation`
    - `test_metadata_schema_validation` ✅ PASSING

- [x] Registered `validation` pytest marker in pyproject.toml
  - Run with: `pytest -m validation`

#### Documentation (Phase 5)
- [x] Created `data/dvc/golden/README.md`:
  - Dataset inventory
  - Pull/usage instructions
  - When to regenerate
  - Troubleshooting

- [x] Created `docs/validation/tradingview_validation.md`:
  - Complete workflow guide
  - TradingView export process
  - Tolerance explanations
  - Adding new strategies
  - CI/CD integration
  - Troubleshooting common issues

#### Comprehensive Indicator Dataset (Phase 1 Complete)
- [x] Created 9 PineScript batch files for TradingView export:
  - `configs/golden_strategies/indicators/batch1_moving_averages.pine`
    - 6 indicators: SMA 20, EMA 20, WMA 20, RSI 14, ATR 14, PSAR
    - 11 total columns (5 OHLCV + 6 indicators)
  - `configs/golden_strategies/indicators/batch2_oscillators.pine`
    - 8 indicators: MACD×3, Stochastic×2, CCI 20, ROC 12, Choppiness
    - 13 total columns (5 OHLCV + 8 indicators)
  - `configs/golden_strategies/indicators/batch3_volume.pine`
    - 2 indicators: OBV, VWAP
    - 7 total columns (5 OHLCV + 2 indicators)
  - `configs/golden_strategies/indicators/batch4_adx.pine`
    - 3 indicators: DMI+, DMI-, ADX 14
    - 8 total columns (5 OHLCV + 3 indicators)
  - `configs/golden_strategies/indicators/batch5_bollinger.pine`
    - 3 indicators: BB Upper, BB Middle, BB Lower (20, 2.0σ)
    - 8 total columns (5 OHLCV + 3 indicators)
  - `configs/golden_strategies/indicators/batch6_supertrend.pine`
    - 2 indicators: SuperTrend, ST Direction (3.0, 7)
    - 7 total columns (5 OHLCV + 2 indicators)
  - `configs/golden_strategies/indicators/batch7_keltner.pine`
    - 3 indicators: KC Upper, KC Middle, KC Lower (20, 20, 2.0)
    - 8 total columns (5 OHLCV + 3 indicators)
  - `configs/golden_strategies/indicators/batch8_ichimoku.pine`
    - 5 indicators: Ich Conversion, Ich Base, Ich Span A, Ich Span B, Ich Lagging
    - 10 total columns (5 OHLCV + 5 indicators)
  - `configs/golden_strategies/indicators/batch9_cmf.pine`
    - 1 indicator: CMF 20
    - 6 total columns (5 OHLCV + 1 indicator)
  - **Total: 32 indicators across 9 batches**
  - Each batch designed to stay within TradingView's ~11 column export limit

- [x] Exported all batches from TradingView:
  - Instrument: OANDA:EURUSD
  - Timeframe: 1 hour
  - Date range: March 4, 2022 - October 10, 2025
  - Row count: 22,447 hourly bars per batch
  - All batches share identical OHLCV data
  - Files kept unmodified from TradingView export

- [x] Organized indicator batch data:
  - Created `data/dvc/golden/indicators/comprehensive/` directory
  - Placed all 9 CSV batch files:
    - `batch1_moving_averages_eurusd_1h.csv`
    - `batch2_oscillators_eurusd_1h.csv`
    - `batch3_volume_eurusd_1h.csv`
    - `batch4_adx_eurusd_1h.csv`
    - `batch5_bollinger_eurusd_1h.csv`
    - `batch6_supertrend_eurusd_1h.csv`
    - `batch7_keltner_eurusd_1h.csv`
    - `batch8_ichimoku_eurusd_1h.csv`
    - `batch9_cmf_eurusd_1h.csv`

- [x] Created comprehensive metadata:
  - `data/dvc/golden/indicators/comprehensive/metadata.json`
  - Validates against `docs/schemas/golden_metadata.schema.json`
  - Documents all 32 indicators with parameters
  - Maps indicator names to CSV column names
  - Records batch structure and row/column counts
  - Documents TradingView export limitations and merge strategy

- [x] Tracked with DVC and pushed to S3:
  - All 9 batch CSV files tracked with DVC
  - DVC pointer files committed to git
  - Successfully pushed to S3 remote
  - Metadata.json committed to git (not DVC-tracked)

- [x] Created indicator batch documentation:
  - `configs/golden_strategies/indicators/README.md`
  - Explains purpose of batch files
  - Provides step-by-step TradingView export instructions
  - Includes batch overview table
  - Documents troubleshooting steps
  - Explains merge strategy (in-memory during tests)

### ✅ Phase 1: Indicator Validation - COMPLETE

#### Data Export ✅
- [x] Exported 32 indicators from TradingView in 9 batches
- [x] All batches tracked with DVC and pushed to S3
- [x] Comprehensive metadata.json created and validated

#### Test Implementation ✅
- [x] Created `tests/validation/test_indicator_validation.py`
- [x] Implemented test fixtures to load batch data
- [x] All 41 indicator validation tests PASSING
- [x] Validated all 32 indicators against platform calculations:
  - [x] Moving averages: SMA, EMA, WMA (3 tests passing)
  - [x] Oscillators: RSI, MACD, Stochastic, CCI, ROC, Choppiness (8 tests passing)
  - [x] Volatility: ATR, Bollinger Bands, Keltner Channels (7 tests passing)
  - [x] Trend: ADX/DMI, PSAR, SuperTrend, Ichimoku Cloud (14 tests passing)
  - [x] Volume: OBV, VWAP, CMF (3 tests passing)
  - [x] Levels: HHV, LLV, Donchian Channels, Swing Points, ATRPercentile (6 tests passing)

#### Library Migration ✅
- [x] Migrated from pandas-ta to TA-Lib library (2025-10-12)
- [x] All indicators re-validated with new library
- [x] pandas-ta completely removed from system
- [x] Pre-commit hook prevents pandas-ta re-introduction

#### Tolerance Optimization ✅
- [x] OBV: Tightened to strictest possible (rtol=1e-10, atol=1e-10)
  - Perfect match on non-flat bars (100% accuracy)
  - Special handling for flat bar convention differences
- [x] SuperTrend: Optimized to rtol=1e-7
  - Removed redundant warm-up logic (global WARMUP_PERIOD handles it)
- [x] PSAR: Documented reversal timing decision
  - Divergence window filtering required (0.86% of bars)
  - 99.64% accuracy with 0.15% tolerance after filtering
  - Custom implementation not worth maintenance burden

### 📋 Pending Tasks

#### Phase 2: Complete Strategy Portfolio
- [ ] Export EMA crossover data from TradingView
  - [ ] Export trades.csv
  - [ ] Export ohlcv.csv
  - [ ] Export equity_curve.csv (if available)
  - [ ] Create metadata.json
  - [ ] Track with DVC
- [ ] Implement BB mean reversion strategy
- [ ] Implement multi-indicator strategy

#### Phase 3: Complete Test Implementation
- [ ] Implement `load_platform_trades()` function
- [ ] Integrate with backtester
- [ ] Verify tests pass with real TradingView data
- [ ] Tune tolerances if needed

#### Phase 4: DVC Integration
- [ ] Add golden datasets to DVC
- [ ] Push to S3
- [ ] Document pull process for team

### 🎯 Next Immediate Steps

1. **Export TradingView Data**
   - Open TradingView
   - Load `configs/golden_strategies/ema_crossover/strategy.pine`
   - Configure per README instructions
   - Export trades and OHLCV
   - Create metadata.json

2. **Track with DVC**
   ```bash
   dvc add data/dvc/golden/strategies/ema_crossover/
   dvc push
   git add data/dvc/golden/strategies/ema_crossover.dvc
   git commit -m "data: Add EMA crossover golden validation"
   ```

3. **Implement Test Integration**
   - Complete `load_platform_trades()` in test file
   - Run tests against real data
   - Adjust tolerances if needed

### 📝 Notes

- ✅ Phase 1 (indicator validation) is COMPLETE
- All infrastructure is in place for Phase 2
- Tests properly skip until strategy data is exported
- Documentation is complete
- Framework is reusable for additional strategies
- Ready for Phase 2 (strategy data export)

### 📊 Recent Work Summary (2025-10-12)

#### TA-Lib Migration & Validation Refinement
Over multiple sessions, we completed a comprehensive migration from pandas-ta to TA-Lib
and optimized all indicator validation tests:

1. **Library Migration:**
   - Replaced pandas-ta with TA-Lib library across all indicators
   - Updated 32+ indicator implementations
   - All 41 validation tests passing with new library
   - Completely removed pandas-ta from system
   - Added pre-commit hook to prevent re-introduction

2. **Indicator-Specific Optimizations:**
   - **OBV:** Discovered and documented flat bar convention differences
     - TradingView: OBV unchanged on flat bars
     - TA-Lib: adds volume on flat bars
     - Solution: Compare first-order differences, filter flat bars
     - Tightened tolerance to strictest possible (rtol=1e-10)

   - **SuperTrend:** Simplified warm-up handling
     - Discovered global WARMUP_PERIOD=100 already handles edge cases
     - Removed redundant SuperTrend-specific warm-up logic
     - Tightened tolerance to rtol=1e-7

   - **PSAR:** Re-evaluated reversal timing with TA-Lib
     - Reversal timing still differs (192 bars / 0.86%)
     - 99.64% accuracy after filtering divergence windows
     - Decided to keep divergence window filtering approach
     - Documented that this is well-known in trading communities

3. **Test Quality Improvements:**
   - All tests use strictest possible tolerances while maintaining correctness
   - Comprehensive documentation of tolerance decisions
   - Special handling only where necessary (PSAR, OBV, VWAP)
   - Global WARMUP_PERIOD=100 for all indicators

4. **Next Steps:**
   - Phase 1 indicator validation is complete and stable
   - Ready to begin Phase 2: Strategy validation
   - EMA crossover strategy infrastructure ready, needs TradingView data export
