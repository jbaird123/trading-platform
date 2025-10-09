$ bash -lc 'poetry run tp run-backtest --config workspace/research/regime_signal_discovery_20251008_223453/20251009_160725_006_bb_mean_reversion_overnight_partition/baseline/backtest.yaml --output-dir workspace/research/regime_signal_discovery_20251008_223453/20251009_160725_006_bb_mean_reversion_overnight_partition/baseline'
failed in sandbox: Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import sys; from importlib import import_module; sys.argv = ['/Users/jbaird/Library/Caches/pypoetry/virtualenvs/trading-platform-xpfdYnHi-py3.13/bin/tp', 'run-backtest', '--config', 'workspace/research/regime_signal_discovery_20251008_223453/20251009_160725_006_bb_mean_reversion_overnight_partition/baseline/backtest.yaml', '--output-dir', 'workspace/research/regime_signal_discovery_20251008_223453/20251009_160725_006_bb_mean_reversion_overnight_partition/baseline']; sys.exit(import_module('trading_platform.cli').main())
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.13/3.13.7/Frameworks/Python.framework/Versions/3.13/lib/python3.13/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 1026, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/Users/jbaird/Documents/other/trading-platform/src/trading_platform/cli.py", line 16, in <module>
    from trading_platform.backtester.core import run_backtest
  File "/Users/jbaird/Documents/other/trading-platform/src/trading_platform/backtester/__init__.py", line 3, in <module>
    from .core import run_backtest
  File "/Users/jbaird/Documents/other/trading-platform/src/trading_platform/backtester/core.py", line 17, in <module>
    from trading_platform.strategy.yaml_strategy import CompiledStrategy
  File "/Users/jbaird/Documents/other/trading-platform/src/trading_platform/strategy/__init__.py", line 4, in <module>
    from .yaml_strategy import CompiledStrategy as YamlStrategy
  File "/Users/jbaird/Documents/other/trading-platform/src/trading_platform/strategy/yaml_strategy.py", line 19, in <module>
    from .features import compute_features
  File "/Users/jbaird/Documents/other/trading-platform/src/trading_platform/strategy/features.py", line 7, in <module>
    import pandas_ta as ta
  File "/Users/jbaird/Library/Caches/pypoetry/virtualenvs/trading-platform-xpfdYnHi-py3.13/lib/python3.13/site-packages/pandas_ta/__init__.py", line 6, in <module>
    from pandas_ta.utils import *
  File "/Users/jbaird/Library/Caches/pypoetry/virtualenvs/trading-platform-xpfdYnHi-py3.13/lib/python3.13/site-packages/pandas_ta/utils/__init__.py", line 4, in <module>
    from ._math import *
  File "/Users/jbaird/Library/Caches/pypoetry/virtualenvs/trading-platform-xpfdYnHi-py3.13/lib/python3.13/site-packages/pandas_ta/utils/_math.py", line 249, in <module>
    @njit(cache=True)
     ~~~~^^^^^^^^^^^^
  File "/Users/jbaird/Library/Caches/pypoetry/virtualenvs/trading-platform-xpfdYnHi-py3.13/lib/python3.13/site-packages/numba/core/decorators.py", line 225, in wrapper
    disp.enable_caching()
    ~~~~~~~~~~~~~~~~~~~^^
  File "/Users/jbaird/Library/Caches/pypoetry/virtualenvs/trading-platform-xpfdYnHi-py3.13/lib/python3.13/site-packages/numba/core/dispatcher.py", line 807, in enable_caching
    self._cache = FunctionCache(self.py_func)
                  ~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/Users/jbaird/Library/Caches/pypoetry/virtualenvs/trading-platform-xpfdYnHi-py3.13/lib/python3.13/site-packages/numba/core/caching.py", line 647, in __init__
    self._impl = self._impl_class(py_func)
                 ~~~~~~~~~~~~~~~~^^^^^^^^^
  File "/Users/jbaird/Library/Caches/pypoetry/virtualenvs/trading-platform-xpfdYnHi-py3.13/lib/python3.13/site-packages/numba/core/caching.py", line 383, in __init__
    raise RuntimeError("cannot cache function %r: no locator available "
                       "for file %r" % (qualname, source_path))
RuntimeError: cannot cache function 'fibonacci': no locator available for file '/Users/jbaird/Library/Caches/pypoetry/virtualenvs/trading-platform-xpfdYnHi-py3.13/lib/python3.13/site-packages/pandas_ta/utils/_math.py'
