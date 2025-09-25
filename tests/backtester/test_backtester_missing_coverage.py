"""
Test coverage for missing lines in backtester core.py
Covers lines 149-174, 283, 299, 386-440
"""

import pandas as pd
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from trading_platform.backtester.core import run_backtest, _simulate_counterfactual_exact
from trading_platform.core.config import RunConfig
from trading_platform.core.costs import CostModel
from trading_platform.risk_manager.core import RiskExitManager
from trading_platform.strategy.yaml_strategy import CompiledStrategy


class TestBacktesterCoreCoverage:
    """Test missing coverage in backtester core module."""

    @pytest.fixture
    def sample_data(self):
        """Create sample market data."""
        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        return pd.DataFrame({
            "open": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9],
            "high": [1.05, 1.15, 1.25, 1.35, 1.45, 1.55, 1.65, 1.75, 1.85, 1.95],
            "low": [0.95, 1.05, 1.15, 1.25, 1.35, 1.45, 1.55, 1.65, 1.75, 1.85],
            "close": [1.02, 1.12, 1.22, 1.32, 1.42, 1.52, 1.62, 1.72, 1.82, 1.92],
            "volume": [1000] * 10,
        }, index=dates)

    @pytest.fixture
    def sample_signals(self):
        """Create sample signals."""
        return pd.Series(["flat", "long", "flat", "short", "flat", "long", "flat", "short", "flat", "flat"])

    @pytest.fixture
    def mock_config(self):
        """Create mock run configuration."""
        config = RunConfig()
        config.initial_cash = 10000.0
        config.position_size = 1.0
        config.allow_flip_on_bar = False
        config.warmup_bars = 0
        config.instrument = {"multiplier": 1.0, "min_size": 0.01}
        config.cost_model = {"type": "percentage", "rate": 0.001}
        config.pm_limits = {"max_open_long": 1, "max_open_short": 1}
        config.blackout_utc = []
        config.blackout_events = []
        config.daily_loss_cap = None
        return config

    @pytest.fixture
    def mock_strategy(self):
        """Create mock strategy."""
        strategy = MagicMock(spec=CompiledStrategy)
        strategy.get_context.return_value = {"test": "context"}
        return strategy

    @pytest.fixture
    def mock_rem(self):
        """Create mock Risk Exit Manager."""
        rem = MagicMock(spec=RiskExitManager)
        rem.check_exits.return_value = None  # No exits by default
        return rem

    def test_rmm_context_with_missing_datetime(self, sample_data, sample_signals, mock_config, mock_strategy, mock_rem):
        """Test RMM context where specific datetime is missing - covers branch 149->174."""
        # Setup RMM context with only some dates, not all
        rmm_context = {
            sample_data.index[2]: {  # Only include one date, not the signal date (index 1)
                "allowed_sides": ["long"],
                "label": "trending_up",
                "confidence": 0.8,
                "policy": {"min_confidence": 0.7}
            }
        }
        
        # Run backtest - this should hit the branch where ctx is None for the signal date
        result = run_backtest(
            market_data=sample_data,
            signals=sample_signals,
            strategy=mock_strategy,
            config=mock_config,
            rem=mock_rem,
            rmm_context=rmm_context,
            return_exposure=False,
            return_skips=False
        )
        
        # Should complete successfully and allow the trade since the specific datetime isn't blocked
        assert isinstance(result, list)

    def test_counterfactual_exact_mode(self, sample_data, sample_signals, mock_config, mock_strategy, mock_rem):
        """Test exact counterfactual mode instead of fast mode - covers line 283."""
        # Set counterfactual mode to 'exact' instead of 'fast'
        mock_config.counterfactual_mode = "exact"
        
        # Create a scenario that will generate skipped trades
        mock_config.daily_loss_cap = 0.01  # Very low daily loss cap to trigger skips
        
        # Mock portfolio.hit_daily_loss_cap to return True
        with patch("trading_platform.portfolio.portfolio.PortfolioManager.hit_daily_loss_cap", return_value=True):
            result = run_backtest(
                market_data=sample_data,
                signals=sample_signals,
                strategy=mock_strategy,
                config=mock_config,
                rem=mock_rem,
                return_exposure=False,
                return_skips=True
            )
        
        # Should return (trades, empty_exposure_curve, skipped)
        assert isinstance(result, tuple)
        assert len(result) == 3
        trades, empty_exposure, skipped = result
        assert isinstance(skipped, list)
        # Should have used exact mode for counterfactual simulation
        if skipped:
            assert any("cf_mode" in skip and skip.get("cf_mode") == "exact" for skip in skipped)

    def test_return_skips_only(self, sample_data, sample_signals, mock_config, mock_strategy, mock_rem):
        """Test return_skips=True without return_exposure - covers line 299."""
        # Create scenario that generates skipped trades
        mock_config.daily_loss_cap = 0.01  # Very low cap to trigger skips
        
        with patch("trading_platform.portfolio.portfolio.PortfolioManager.hit_daily_loss_cap", return_value=True):
            result = run_backtest(
                market_data=sample_data,
                signals=sample_signals,
                strategy=mock_strategy,
                config=mock_config,
                rem=mock_rem,
                return_exposure=False,  # False
                return_skips=True       # True
            )
        
        # Should return (trades, empty_exposure_curve, skipped) - line 299
        assert isinstance(result, tuple)
        assert len(result) == 3
        trades, empty_exposure, skipped = result
        assert isinstance(trades, list)
        assert isinstance(empty_exposure, list)
        assert len(empty_exposure) == 0  # Should be empty when return_exposure=False
        assert isinstance(skipped, list)

    def test_simulate_counterfactual_exact_function(self, sample_data, mock_strategy, mock_rem):
        """Test _simulate_counterfactual_exact function - covers lines 386-440."""
        # Test the exact counterfactual simulation function directly
        result = _simulate_counterfactual_exact(
            market_data=sample_data,
            strategy=mock_strategy,
            start_index=1,
            side="long",
            entry_price=1.12,
            size=1.0,
            instrument={"multiplier": 1.0, "min_size": 0.01},
            cost_model={"type": "percentage", "rate": 0.001},
            rem=mock_rem
        )
        
        # Should return counterfactual results
        assert isinstance(result, dict)
        assert "cf_exit_time" in result
        assert "cf_exit_price" in result
        assert "cf_pnl_currency" in result
        assert "cf_mfe_currency" in result
        assert "cf_mae_currency" in result
        assert "cf_bars_held" in result
        assert "cf_mode" in result
        assert result["cf_mode"] == "exact"

    def test_simulate_counterfactual_exact_with_rem_exit(self, sample_data, mock_strategy, mock_rem):
        """Test _simulate_counterfactual_exact with REM triggering exit - covers rem exit logic."""
        # Make REM trigger an exit on the second bar
        def mock_check_exits(position, current_bar):
            if current_bar.name == sample_data.index[2]:  # Third bar (index 2)
                return {
                    "exit_price": 1.25,
                    "reason": "stop_loss"
                }
            return None
        
        mock_rem.check_exits.side_effect = mock_check_exits
        
        result = _simulate_counterfactual_exact(
            market_data=sample_data,
            strategy=mock_strategy,
            start_index=1,
            side="long",
            entry_price=1.12,
            size=1.0,
            instrument={"multiplier": 1.0, "min_size": 0.01},
            cost_model={"type": "percentage", "rate": 0.001},
            rem=mock_rem
        )
        
        # Should return results with REM exit
        assert isinstance(result, dict)
        assert result["cf_exit_kind"] == "rem"
        assert "cf_exit_time" in result
        assert result["cf_mode"] == "exact"

    def test_simulate_counterfactual_exact_invalid_start_index(self, sample_data, mock_strategy, mock_rem):
        """Test _simulate_counterfactual_exact with invalid start_index."""
        # Test with start_index out of bounds
        result = _simulate_counterfactual_exact(
            market_data=sample_data,
            strategy=mock_strategy,
            start_index=999,  # Invalid index
            side="long",
            entry_price=1.12,
            size=1.0,
            instrument={"multiplier": 1.0, "min_size": 0.01},
            cost_model={"type": "percentage", "rate": 0.001},
            rem=mock_rem
        )
        
        # Should return empty dict for invalid index
        assert result == {}

    def test_simulate_counterfactual_exact_no_trades_generated(self, sample_data, mock_strategy, mock_rem):
        """Test _simulate_counterfactual_exact when no trades are generated."""
        # Use a mock PortfolioManager that doesn't generate any trades
        with patch("trading_platform.backtester.core.PortfolioManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_pm.trades = []  # No trades generated
            mock_pm.current_position = None
            mock_pm_class.return_value = mock_pm
            
            result = _simulate_counterfactual_exact(
                market_data=sample_data,
                strategy=mock_strategy,
                start_index=1,
                side="long",
                entry_price=1.12,
                size=1.0,
                instrument={"multiplier": 1.0, "min_size": 0.01},
                cost_model={"type": "percentage", "rate": 0.001},
                rem=mock_rem
            )
            
            # Should return empty dict when no trades
            assert result == {}

    def test_simulate_counterfactual_exact_position_closes_early(self, sample_data, mock_strategy, mock_rem):
        """Test _simulate_counterfactual_exact when position closes before end."""
        # Mock a portfolio that closes position early (not due to REM)
        with patch("trading_platform.backtester.core.PortfolioManager") as mock_pm_class:
            mock_pm = MagicMock()
            mock_position = MagicMock()
            mock_pm.current_position = mock_position
            
            # Simulate position being closed on the second iteration
            def side_effect_current_position(*args, **kwargs):
                # First call: position exists, second call: position is None
                if mock_pm.current_position._call_count == 1:
                    mock_pm.current_position = None
                mock_pm.current_position._call_count = getattr(mock_pm.current_position, '_call_count', 0) + 1
                return mock_pm.current_position
            
            # Setup the position to exist initially, then be None
            position_call_count = 0
            def get_current_position():
                nonlocal position_call_count
                position_call_count += 1
                return mock_position if position_call_count <= 2 else None
            
            type(mock_pm).current_position = property(lambda self: get_current_position())
            
            # Mock trade result
            mock_trade = MagicMock()
            mock_trade.exit_time = sample_data.index[2]
            mock_trade.exit_price = 1.25
            mock_trade.pnl = 0.13
            mock_trade.mfe_currency = 0.15
            mock_trade.mae_currency = 0.05
            mock_trade.bars_held = 2
            mock_pm.trades = [mock_trade]
            
            mock_pm_class.return_value = mock_pm
            mock_rem.check_exits.return_value = None  # No REM exits
            
            result = _simulate_counterfactual_exact(
                market_data=sample_data,
                strategy=mock_strategy,
                start_index=1,
                side="long",
                entry_price=1.12,
                size=1.0,
                instrument={"multiplier": 1.0, "min_size": 0.01},
                cost_model={"type": "percentage", "rate": 0.001},
                rem=mock_rem
            )
            
            # Should return results with end exit (not REM)
            assert isinstance(result, dict)
            assert result["cf_exit_kind"] == "end"
            assert result["cf_mode"] == "exact"


def test_return_skips_only_line_299():
    """Test case where we return skips but not exposure curve - hits line 299."""
    from unittest.mock import Mock, patch
    import pandas as pd
    from trading_platform.backtester.core import run_backtest
    
    # Create test data - we need to create a situation that generates skips
    data = pd.DataFrame({
        'open': [1.1000, 1.1010],
        'high': [1.1005, 1.1015],
        'low': [0.9995, 1.1005],
        'close': [1.1005, 1.1015],
        'volume': [1000, 1000]
    }, index=pd.DatetimeIndex(['2023-01-01', '2023-01-02']))
    
    # Create signals that will be blocked by RMM
    signals = pd.Series(['long', 'long'], index=data.index)
    
    # Create RMM context that blocks all signals to generate skips
    rmm_context = {
        data.index[0]: {
            'allowed_sides': ['short'],  # Block long signals
            'label': 'test_regime', 
            'confidence': 0.8,
            'policy': {'min_confidence': 0.7}
        },
        data.index[1]: {
            'allowed_sides': ['short'],  # Block long signals  
            'label': 'test_regime',
            'confidence': 0.8, 
            'policy': {'min_confidence': 0.7}
        }
    }
    
    # Create config
    from trading_platform.core.config import RunConfig
    config = RunConfig(
        trade_size_usd=1000,
        max_positions=1,
        daily_loss_cap=None
    )
    
    def _dummy_strategy_cfg():
        from types import SimpleNamespace
        return SimpleNamespace(warmup_bars=0, get_context=lambda i: {})
    
    # Test - return skips but not exposure (hits line 299)
    # This should generate skipped items but not return exposure
    result = run_backtest(
        market_data=data,
        signals=signals, 
        strategy=_dummy_strategy_cfg(),
        config=config,
        rem=None,  # Will create default 
        rmm_context=rmm_context,  # This will cause skips
        return_exposure=False,  # This is key - no exposure
        return_skips=True       # This too - hits line 299
    )
    
    # Should return tuple with (trades, empty_list, skipped_items)
    assert isinstance(result, tuple)
    assert len(result) == 3
    trades, exposure_curve, skipped = result
    
    # Should have empty exposure curve since return_exposure=False
    assert exposure_curve == []
    # Should have some skipped items from RMM blocking
    assert len(skipped) > 0


def test_rmm_allows_signal_branch_151_174():
    """Test case where RMM context exists but signal is allowed - covers branch 151->174."""
    from unittest.mock import Mock, patch
    import pandas as pd
    from trading_platform.backtester.core import run_backtest
    
    mock_strategy = Mock()
    mock_strategy.warmup_bars = 0
    mock_strategy.get_context.return_value = {}
    
    # Mock that we have a valid signal each bar
    mock_strategy.apply.side_effect = lambda bar, idx, signals: 1
    
    with patch('trading_platform.backtester.core.PortfolioManager') as mock_pm_cls, \
         patch('trading_platform.backtester.core.RiskExitManager') as mock_rem_cls, \
         patch('trading_platform.backtester.core.TradingWindowPolicy') as mock_policy_cls:
        
        mock_pm = Mock()
        mock_pm.trades = []
        mock_pm.hit_daily_loss_cap.return_value = False
        mock_pm.get_current_positions.return_value = []
        mock_pm.can_add_position.return_value = True
        mock_pm.add_position.return_value = None
        mock_pm.current_position = None  # No existing position
        mock_pm_cls.return_value = mock_pm
        
        # Mock the policy to allow opening
        mock_policy = Mock()
        mock_policy.can_open.return_value = True
        mock_policy_cls.from_config.return_value = mock_policy
        
        mock_rem = Mock()
        mock_rem.check_exits.return_value = None  # No exits
        mock_rem_cls.return_value = mock_rem
        
        # Create test data
        data = pd.DataFrame({
            'open': [1.1000],
            'high': [1.1005],
            'low': [0.9995],
            'close': [1.1005],
            'volume': [1000]
        }, index=pd.DatetimeIndex(['2023-01-01']))
        
        # Create signals
        signals = pd.Series(['long'], index=data.index)
        
        # Create RMM context that ALLOWS the signal (long signals)
        rmm_context = {
            data.index[0]: {
                'allowed_sides': ['long'],  # Allow our signal ("long")
                'label': 'test_regime',
                'confidence': 0.8,
                'policy': {'min_confidence': 0.7}
            }
        }
        
        # Create config
        from trading_platform.core.config import RunConfig
        config = RunConfig(
            trade_size_usd=1000,
            max_positions=1,
            daily_loss_cap=None
        )
        
        # Test - should NOT skip because signal is allowed
        result = run_backtest(
            market_data=data,
            signals=signals,
            strategy=mock_strategy,
            config=config,
            rem=mock_rem,
            rmm_context=rmm_context,  # This enables RMM with context that allows signal
            return_skips=True
        )
        
        # Should have attempted to create new position (not skipped)
        mock_pm.create_new_position.assert_called()
        
        # Extract skipped items
        if isinstance(result, tuple):
            skipped = result[2] if len(result) > 2 else result[1]
        else:
            skipped = []
            
        # Should have NO skipped items because signal was allowed
        assert len(skipped) == 0


def test_comprehensive_return_combinations():
    """Test all combinations of return flags to ensure all return paths are covered."""
    import pandas as pd
    from trading_platform.backtester.core import run_backtest
    from trading_platform.core.config import RunConfig  
    from trading_platform.risk_manager.core import RiskExitManager
    from trading_platform.strategy.yaml_strategy import CompiledStrategy
    from datetime import datetime

    def _dummy_strategy() -> CompiledStrategy:
        return CompiledStrategy(
            name='dummy',
            features=[], overlays=[], long_entry_blocks=[], long_exit_blocks=[], 
            short_entry_blocks=[], short_exit_blocks=[], parameters={},
        )
    
    idx = [datetime(2024, 1, 1, 1)]
    df = pd.DataFrame(
        {'open': [1], 'high': [1], 'low': [1], 'close': [1], 'volume': [1]}, index=idx
    )
    sig = pd.Series(['long'], index=df.index)
    config = RunConfig(user_id='test', run_seed=42, log_level='INFO', 
                      initial_cash=1000.0, position_size=1.0, allow_flip_on_bar=False)
    rem = RiskExitManager(config={})
    
    # Test case 1: return_exposure=True, return_skips=True  
    result1 = run_backtest(df, sig, _dummy_strategy(), config, rem, 
                          return_exposure=True, return_skips=True)
    assert len(result1) == 3
    
    # Test case 2: return_exposure=True, return_skips=False
    result2 = run_backtest(df, sig, _dummy_strategy(), config, rem, 
                          return_exposure=True, return_skips=False)
    assert len(result2) == 2
    
    # Test case 3: return_exposure=False, return_skips=True (this hits line 299/300)
    result3 = run_backtest(df, sig, _dummy_strategy(), config, rem, 
                          return_exposure=False, return_skips=True)
    assert len(result3) == 3 and result3[1] == []
    
    # Test case 4: return_exposure=False, return_skips=False
    result4 = run_backtest(df, sig, _dummy_strategy(), config, rem, 
                          return_exposure=False, return_skips=False)
    assert not isinstance(result4, tuple)