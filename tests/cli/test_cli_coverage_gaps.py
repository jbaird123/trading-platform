"""Tests to achieve 100% coverage for cli.py missing lines 96, 101, 103."""

from pathlib import Path
from unittest.mock import Mock, patch
from trading_platform.cli import cmd_run_backtest


def test_cli_data_request_with_start_end_filtering():
    """Test CLI with data_request that has start/end filtering."""
    
    # Create mock args
    args = Mock()
    args.demo = False
    args.config = "test_config.yaml"
    
    # Mock config data with data_request containing start/end
    mock_config = {
        'data_request': {
            'symbol': 'EUR_USD',
            'start': '2023-01-01',
            'end': '2023-01-02'
        },
        'user_id': 'test',
        'runs_dir': 'runs',
        'initial_cash': 100000,
        'position_size': 1000,
        'warmup_bars': 10,
        'instrument': {'symbol': 'EUR_USD'},
        'strategy_path': 'config/strategy/ema_crossover.yaml',
        'rem_path': 'config/rem/basic_price_exits.yaml'
    }
    
    # Mock strategy config that passes validation
    mock_strategy = {
        'strategy_name': 'test_strategy',
        'long_entry_rules': [
            {'all_of': [{'condition': 'cross_above', 'left': 'close', 'right': 1.1}]}
        ],
        'long_exit_rules': [
            {'all_of': [{'condition': 'cross_below', 'left': 'close', 'right': 1.0}]}
        ]
    }
    
    with patch('trading_platform.cli._load_config', return_value=mock_config), \
         patch('trading_platform.cli.RunConfig.model_validate', return_value=Mock()), \
         patch('trading_platform.cli.initialize_run', return_value=Path('test_run')), \
         patch('trading_platform.cli.run_backtest', return_value=(Mock(), Mock(), Mock())), \
         patch('trading_platform.cli.finalize_run'), \
         patch('builtins.print'), \
         patch('yaml.safe_load', return_value=mock_strategy):

        result = cmd_run_backtest(args)
        
        # Should execute successfully and print start/end filtering message
        assert result is None


def test_cli_data_request_no_timeframe_start_end():
    """Test CLI when data_request has no timeframe but has start/end."""
    
    # Create mock args
    args = Mock()
    args.demo = False
    args.config = "test_config.yaml"
    
    # Mock config data without timeframe
    mock_config = {
        'data_request': {
            'symbol': 'EUR_USD',
            'start': '2023-01-01',
            'end': '2023-01-02'
            # no timeframe key
        },
        'user_id': 'test',
        'runs_dir': 'runs',
        'initial_cash': 100000,
        'position_size': 1000,
        'warmup_bars': 10,
        'instrument': {'symbol': 'EUR_USD'},
        'strategy_path': 'config/strategy/ema_crossover.yaml',
        'rem_path': 'config/rem/basic_price_exits.yaml'
    }
    
    # Mock strategy config that passes validation
    mock_strategy = {
        'strategy_name': 'test_strategy',
        'long_entry_rules': [
            {'all_of': [{'condition': 'cross_above', 'left': 'close', 'right': 1.1}]}
        ],
        'long_exit_rules': [
            {'all_of': [{'condition': 'cross_below', 'left': 'close', 'right': 1.0}]}
        ]
    }
    
    with patch('trading_platform.cli._load_config', return_value=mock_config), \
         patch('trading_platform.cli.RunConfig.model_validate', return_value=Mock()), \
         patch('trading_platform.cli.initialize_run', return_value=Path('test_run')), \
         patch('trading_platform.cli.run_backtest', return_value=(Mock(), Mock(), Mock())), \
         patch('trading_platform.cli.finalize_run'), \
         patch('builtins.print'), \
         patch('yaml.safe_load', return_value=mock_strategy):

        result = cmd_run_backtest(args)
        
        # Should execute successfully
        assert result is None


def test_cli_no_data_request_uses_toy_data():
    """Test CLI when no data_request is provided - should use toy data."""
    
    # Create mock args
    args = Mock()
    args.demo = False
    args.config = "test_config.yaml"
    
    # Mock config data without data_request
    mock_config = {
        'user_id': 'test',
        'runs_dir': 'runs',
        'initial_cash': 100000,
        'position_size': 1000,
        'warmup_bars': 10,
        'instrument': {'symbol': 'EUR_USD'},
        'strategy_path': 'config/strategy/ema_crossover.yaml',
        'rem_path': 'config/rem/basic_price_exits.yaml'
    }
    
    # Mock strategy config that passes validation
    mock_strategy = {
        'strategy_name': 'test_strategy',
        'long_entry_rules': [
            {'all_of': [{'condition': 'cross_above', 'left': 'close', 'right': 1.1}]}
        ],
        'long_exit_rules': [
            {'all_of': [{'condition': 'cross_below', 'left': 'close', 'right': 1.0}]}
        ]
    }
    
    with patch('trading_platform.cli._load_config', return_value=mock_config), \
         patch('trading_platform.cli.RunConfig.model_validate', return_value=Mock()), \
         patch('trading_platform.cli.initialize_run', return_value=Path('test_run')), \
         patch('trading_platform.cli.run_backtest', return_value=(Mock(), Mock(), Mock())), \
         patch('trading_platform.cli.finalize_run'), \
         patch('builtins.print'), \
         patch('yaml.safe_load', return_value=mock_strategy):
        
        result = cmd_run_backtest(args)
        assert result == 0