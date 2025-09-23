# Validates: [SYS-1.3.1]
import inspect

from trading_platform.portfolio.portfolio import PortfolioManager


def test_portfolio_manager_interface_uses_canonical_types():
    """
    Verifies that the PortfolioManager's public methods use canonical types
    (float, datetime) for prices and times, enforcing SYS-1.3.1.
    """
    # Check create_new_position
    create_sig = inspect.signature(PortfolioManager.create_new_position)
    assert create_sig.parameters["entry_price"].annotation == "float"
    assert create_sig.parameters["size"].annotation == "float"
    assert create_sig.parameters["entry_time"].annotation == "datetime"

    # Check close_position
    close_sig = inspect.signature(PortfolioManager.close_position)
    assert close_sig.parameters["exit_price"].annotation == "float"
    assert close_sig.parameters["exit_time"].annotation == "datetime"

    # Check stop/profit checks, which receive price levels from upstream
    stop_sig = inspect.signature(PortfolioManager.check_stop_loss)
    assert stop_sig.parameters["stop_price"].annotation == "float"

    profit_sig = inspect.signature(PortfolioManager.check_take_profit)
    assert profit_sig.parameters["profit_price"].annotation == "float"
