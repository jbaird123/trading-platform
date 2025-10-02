#!/usr/bin/env python3
"""
RMM Filter Experiments on BB Strategy
Test different market regime filters to improve the winning BB strategy
"""
import json
import subprocess
from pathlib import Path
import yaml
from datetime import datetime

# Base winning strategy
INSTRUMENT = "USD_JPY"
TIMEFRAME = "5min"
STRATEGY = "config/strategy/bb_mean_reversion.yaml"

# RMM filters to test
RMM_FILTERS = [
    (None, "No_RMM", "Baseline - no filtering"),
    ("config/rmm/range_relaxed.yaml", "Range_Relaxed", "Range only (ADX<40 on 15M)"),
    ("config/rmm/trend_relaxed.yaml", "Trend_Relaxed", "Trend only (ADX>20 on 15M)"),
    ("config/rmm/high_volatility.yaml", "High_Vol", "High volatility (BB width > 0.01)"),
    ("config/rmm/range_only.yaml", "Range_1H", "Range only (ADX<25 on 1H)"),
]

def run_backtest(config_path: Path, timeout: int = 180) -> dict | None:
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
        print(f"   ⚠️ Error: {e}")
        return None

def extract_metrics(brief: dict) -> dict:
    """Extract comprehensive metrics from brief."""
    try:
        equity_curve = brief.get("equity_stats", {}).get("equity_curve", [])
        initial = float(equity_curve[0][1]) if equity_curve else 100000
        final = float(equity_curve[-1][1]) if equity_curve else 100000
        pnl = final - initial

        trades = brief.get("trades", [])
        num_trades = len(trades)
        winners = sum(1 for t in trades if t.get("pnl", 0) > 0)
        win_rate = winners / num_trades if num_trades > 0 else 0

        # Analyze drawdown periods
        dd_curve = brief.get("equity_stats", {}).get("drawdown_curve", [])
        max_dd_duration_days = 0
        if dd_curve:
            in_dd = False
            dd_start = None
            for i, (timestamp, dd) in enumerate(dd_curve):
                if dd > 0 and not in_dd:
                    dd_start = timestamp
                    in_dd = True
                elif dd == 0 and in_dd and dd_start:
                    try:
                        start_time = datetime.fromisoformat(dd_start.replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(dd_curve[i-1][0].replace('Z', '+00:00'))
                        duration_days = (end_time - start_time).days
                        max_dd_duration_days = max(max_dd_duration_days, duration_days)
                    except:
                        pass
                    in_dd = False

        max_dd = brief.get("equity_stats", {}).get("max_drawdown", 0)

        # Walk-forward results
        wf = brief.get("walk_forward", {})
        oos_pnl = wf.get("oos_total_pnl", {}) if wf else {}
        oos_mean = oos_pnl.get("mean", 0) if oos_pnl else 0
        oos_median = oos_pnl.get("median", 0) if oos_pnl else 0
        n_splits = oos_pnl.get("n_splits", 0) if oos_pnl else 0

        # Calculate payoff ratio
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) < 0]
        avg_win = sum(t["pnl"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(t["pnl"] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
        payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        return {
            "pnl": pnl,
            "num_trades": num_trades,
            "win_rate": win_rate,
            "max_dd": max_dd,
            "max_dd_duration_days": max_dd_duration_days,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "payoff_ratio": payoff_ratio,
            "oos_mean": oos_mean,
            "oos_median": oos_median,
            "n_splits": n_splits,
        }
    except Exception as e:
        print(f"   ⚠️ Error extracting metrics: {e}")
        return {}

def main():
    print("\n" + "="*80)
    print("RMM FILTER EXPERIMENTS - BOLLINGER BAND MEAN REVERSION")
    print("="*80)
    print(f"Base Strategy: {STRATEGY}")
    print(f"Instrument: {INSTRUMENT}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"\nTesting {len(RMM_FILTERS)} RMM configurations...")
    print()

    results = []

    for rmm_path, rmm_name, description in RMM_FILTERS:
        print(f"📊 Testing: {rmm_name}")
        print(f"   {description}")

        config = {
            "user_id": f"rmm_exp_{rmm_name.lower()}",
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
                "symbol": INSTRUMENT,
                "timeframe": TIMEFRAME,
                "start": "2020-01-01",
                "end": "2025-09-26"
            },
            "strategy_path": STRATEGY,
            "rem_path": "config/rem/trailing_stops.yaml",
            "walk_forward": {
                "window": 60,
                "step": 30
            }
        }

        if rmm_path:
            config["rmm_path"] = rmm_path

        config_path = Path("rmm_results") / f"{rmm_name.lower()}.yaml"
        config_path.parent.mkdir(exist_ok=True)
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        brief = run_backtest(config_path, timeout=300)
        if brief:
            metrics = extract_metrics(brief)

            # Display results
            print(f"   ✅ PnL: ${metrics.get('pnl', 0):,.0f}")
            print(f"   📈 Trades: {metrics.get('num_trades', 0):,}")
            print(f"   🎯 Win Rate: {metrics.get('win_rate', 0):.1%}")
            print(f"   💰 Payoff: {metrics.get('payoff_ratio', 0):.2f}:1")
            print(f"   📉 Max DD Duration: {metrics.get('max_dd_duration_days', 0)} days")
            print(f"   🔬 OOS Median: ${metrics.get('oos_median', 0):,.0f} ({metrics.get('n_splits', 0)} windows)")

            # Pass/fail indicators
            pass_dd = metrics.get('max_dd_duration_days', 999) <= 14
            pass_oos = metrics.get('oos_median', 0) > 0
            pass_profit = metrics.get('pnl', 0) > 0

            if pass_dd and pass_oos and pass_profit:
                print(f"   ✅ PASS ALL CRITERIA")
            else:
                fails = []
                if not pass_dd: fails.append("DD>14d")
                if not pass_oos: fails.append("OOS<0")
                if not pass_profit: fails.append("Loss")
                print(f"   ⚠️ FAIL: {', '.join(fails)}")

            results.append({
                "rmm_name": rmm_name,
                "rmm_path": rmm_path,
                "description": description,
                **metrics
            })
        else:
            print(f"   ❌ Failed to run backtest")

        print()

    # Save results
    results_file = Path("rmm_results") / "comparison.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Analysis
    print("=" * 80)
    print("RESULTS COMPARISON")
    print("=" * 80)
    print()

    # Sort by PnL
    results_sorted = sorted(results, key=lambda x: x.get("pnl", 0), reverse=True)

    print("Ranked by Total PnL:")
    print()
    print(f"{'Rank':<5} {'RMM Filter':<20} {'PnL':<15} {'Trades':<10} {'WR':<8} {'Payoff':<10} {'DD Days':<10} {'OOS Med':<12}")
    print("-" * 100)

    for i, r in enumerate(results_sorted, 1):
        pnl = r.get('pnl', 0)
        trades = r.get('num_trades', 0)
        wr = r.get('win_rate', 0)
        payoff = r.get('payoff_ratio', 0)
        dd_days = r.get('max_dd_duration_days', 0)
        oos_med = r.get('oos_median', 0)

        # Highlight best
        marker = "🏆" if i == 1 else f"{i}."

        print(f"{marker:<5} {r['rmm_name']:<20} ${pnl:>12,.0f} {trades:>9,} {wr:>6.1%} {payoff:>8.2f}:1 {dd_days:>9} ${oos_med:>10,.0f}")

    print()
    print("=" * 80)

    # Best by different metrics
    best_pnl = max(results, key=lambda x: x.get("pnl", 0))
    best_dd = min(results, key=lambda x: x.get("max_dd_duration_days", 999))
    best_oos = max(results, key=lambda x: x.get("oos_median", 0))
    best_wr = max(results, key=lambda x: x.get("win_rate", 0))

    print("\n🏆 CATEGORY WINNERS:")
    print(f"   Best PnL: {best_pnl['rmm_name']} (${best_pnl.get('pnl', 0):,.0f})")
    print(f"   Best DD Duration: {best_dd['rmm_name']} ({best_dd.get('max_dd_duration_days', 0)} days)")
    print(f"   Best OOS: {best_oos['rmm_name']} (${best_oos.get('oos_median', 0):,.0f})")
    print(f"   Best Win Rate: {best_wr['rmm_name']} ({best_wr.get('win_rate', 0):.1%})")

    # Trade count reduction analysis
    baseline = next((r for r in results if r['rmm_name'] == 'No_RMM'), None)
    if baseline:
        print(f"\n📊 TRADE REDUCTION vs BASELINE ({baseline.get('num_trades', 0):,} trades):")
        for r in results_sorted:
            if r['rmm_name'] != 'No_RMM':
                reduction = (baseline.get('num_trades', 0) - r.get('num_trades', 0)) / baseline.get('num_trades', 1)
                print(f"   {r['rmm_name']:<20}: {r.get('num_trades', 0):>6,} trades ({reduction:>6.1%} reduction)")

    return results

if __name__ == "__main__":
    main()
