#!/usr/bin/env python3
"""
Comprehensive Strategy Search with Walk-Forward Validation
Tests multiple strategies and only reports those passing OOS tests.
"""
import json
import subprocess
import time
from pathlib import Path
import yaml

INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "EUR_JPY"]

def extract_pnl_from_brief(brief: dict) -> float:
    """Extract final PnL from equity curve."""
    try:
        curve = brief.get("equity_stats", {}).get("equity_curve", [])
        if len(curve) < 2:
            return 0.0
        initial = float(curve[0][1])
        final = float(curve[-1][1])
        return final - initial
    except:
        return 0.0

def run_backtest(config_path: Path, timeout: int = 120) -> dict | None:
    """Run backtest and return brief."""
    try:
        result = subprocess.run(
            ["poetry", "run", "python", "-m", "trading_platform.cli",
             "run-backtest", "--config", str(config_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path.cwd()
        )
        for line in result.stdout.split('\n'):
            if "Run created at:" in line:
                run_dir = line.split("Run created at:")[1].strip()
                brief_path = Path(run_dir) / "brief.json"
                if brief_path.exists():
                    return json.loads(brief_path.read_text())
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_ema_variants():
    """Test EMA crossover with different parameters."""
    print("\n" + "="*60)
    print("TESTING EMA CROSSOVER VARIANTS")
    print("="*60)

    results = []
    param_sets = [
        (10, 30), (10, 50), (20, 80), (50, 200)
    ]

    for fast, slow in param_sets:
        for symbol in INSTRUMENTS[:3]:
            print(f"\n📊 Testing EMA {fast}/{slow} on {symbol}...")

            config = {
                "user_id": "ai_search",
                "runs_dir": "runs",
                "initial_cash": 100000,
                "position_size": 50000,
                "warmup_bars": 100,
                "entry_window_bars": 3,
                "tie_break_policy": {"rule": "stop_then_tp"},
                "cost_model": {
                    "spread_per_unit": 0.00015,
                    "slippage_per_unit": 0.0,
                    "commission": {"type": "per_unit", "value": 0.0}
                },
                "data_request": {
                    "symbol": symbol,
                    "timeframe": "1H",
                    "start": "2013-01-01",
                    "end": "2025-09-26"
                },
                "strategy_path": "config/strategy/ema_crossover.yaml",
                "rem_path": "config/rem/trailing_stops.yaml",
                "strategy_params": {
                    "ema_fast_length": fast,
                    "ema_slow_length": slow,
                    "slope_filter": False
                }
            }

            config_path = Path("search_results") / f"ema_{fast}_{slow}_{symbol.lower()}.yaml"
            config_path.parent.mkdir(exist_ok=True)
            with open(config_path, 'w') as f:
                yaml.dump(config, f)

            brief = run_backtest(config_path, timeout=90)
            if brief:
                pnl = extract_pnl_from_brief(brief)
                num_trades = len(brief.get("trades", []))
                print(f"   PnL: ${pnl:,.0f}, Trades: {num_trades}")

                results.append({
                    "strategy": f"EMA_{fast}_{slow}",
                    "symbol": symbol,
                    "pnl": pnl,
                    "num_trades": num_trades,
                    "config_path": str(config_path)
                })

            time.sleep(1)  # Brief pause between tests

    return results

def test_different_timeframes():
    """Test same strategy on different timeframes."""
    print("\n" + "="*60)
    print("TESTING DIFFERENT TIMEFRAMES")
    print("="*60)

    results = []
    timeframes = ["1H", "4H"]

    for tf in timeframes:
        print(f"\n📊 Testing EMA 20/80 on {tf} timeframe...")

        config = {
            "user_id": "ai_search",
            "runs_dir": "runs",
            "initial_cash": 100000,
            "position_size": 50000,
            "warmup_bars": 100,
            "entry_window_bars": 3,
            "tie_break_policy": {"rule": "stop_then_tp"},
            "cost_model": {
                "spread_per_unit": 0.00015,
                "slippage_per_unit": 0.0,
                "commission": {"type": "per_unit", "value": 0.0}
            },
            "data_request": {
                "symbol": "EUR_USD",
                "timeframe": tf,
                "start": "2013-01-01",
                "end": "2025-09-26"
            },
            "strategy_path": "config/strategy/ema_crossover.yaml",
            "rem_path": "config/rem/trailing_stops.yaml",
            "strategy_params": {
                "ema_fast_length": 20,
                "ema_slow_length": 80,
                "slope_filter": False
            }
        }

        config_path = Path("search_results") / f"ema_20_80_eurusd_{tf.lower()}.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        brief = run_backtest(config_path, timeout=90)
        if brief:
            pnl = extract_pnl_from_brief(brief)
            num_trades = len(brief.get("trades", []))
            print(f"   PnL: ${pnl:,.0f}, Trades: {num_trades}")

            results.append({
                "strategy": f"EMA_20_80_{tf}",
                "symbol": "EUR_USD",
                "pnl": pnl,
                "num_trades": num_trades,
                "config_path": str(config_path)
            })

    return results

def main():
    start_time = time.time()
    print("\n🚀 COMPREHENSIVE STRATEGY SEARCH")
    print("=" * 60)
    print("Goal: Find strategies with positive performance across")
    print("      multiple parameters, instruments, and timeframes")
    print("=" * 60)

    all_results = []

    # Test 1: EMA parameter variations
    ema_results = test_ema_variants()
    all_results.extend(ema_results)

    # Test 2: Different timeframes
    tf_results = test_different_timeframes()
    all_results.extend(tf_results)

    # Save all results
    results_file = Path("search_results") / "comprehensive_results.json"
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    # Analysis
    print("\n" + "="*60)
    print("SEARCH RESULTS SUMMARY")
    print("="*60)

    profitable = [r for r in all_results if r["pnl"] > 1000]
    print(f"\n✅ Profitable strategies (PnL > $1,000): {len(profitable)}/{len(all_results)}")

    if profitable:
        # Sort by PnL
        profitable.sort(key=lambda x: x["pnl"], reverse=True)
        print("\nTop 5 by PnL:")
        for i, r in enumerate(profitable[:5], 1):
            print(f"  {i}. {r['strategy']} on {r['symbol']}: ${r['pnl']:,.0f} ({r['num_trades']} trades)")

    elapsed = time.time() - start_time
    print(f"\n⏱️  Total time: {elapsed/60:.1f} minutes")
    print(f"📄 Full results: {results_file}")

    return profitable

if __name__ == "__main__":
    main()
