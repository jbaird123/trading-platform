#!/usr/bin/env python3
"""
Simple diagnostic to check crossover detection logic.
"""

import pandas as pd
import numpy as np

def test_crossover_logic():
    """Test crossover detection with synthetic data"""
    
    # Create synthetic EMA data with clear crossovers
    dates = pd.date_range('2025-01-01', periods=20, freq='h')
    
    # Fast EMA starts below slow, then crosses above, then back below
    ema_fast = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9,  # Rising
                2.0, 2.1, 2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3]   # Falling
    
    ema_slow = [1.5] * 20  # Constant
    
    df = pd.DataFrame({
        'ema_fast': ema_fast,
        'ema_slow': ema_slow
    }, index=dates)
    
    print("=== SYNTHETIC EMA DATA ===")
    print(df)
    
    # Manual crossover calculation (same as in yaml_strategy.py)
    left = df['ema_fast']
    right = df['ema_slow']
    
    # Cross above: was below or equal, now above
    prev_fast_below = left.shift(1) <= right.shift(1)
    now_fast_above = left > right
    cross_above = prev_fast_below & now_fast_above
    
    # Cross below: was above or equal, now below  
    prev_fast_above = left.shift(1) >= right.shift(1)
    now_fast_below = left < right
    cross_below = prev_fast_above & now_fast_below
    
    df['cross_above'] = cross_above
    df['cross_below'] = cross_below
    df['fast_above_slow'] = left > right
    
    print("\n=== CROSSOVER ANALYSIS ===")
    print(df[['ema_fast', 'ema_slow', 'fast_above_slow', 'cross_above', 'cross_below']])
    
    # Show where crossovers occur
    crossover_points = df[cross_above | cross_below]
    print(f"\n=== CROSSOVER EVENTS ({len(crossover_points)}) ===")
    for idx, row in crossover_points.iterrows():
        direction = "UP" if row['cross_above'] else "DOWN"
        print(f"{idx}: Fast crossed {direction} (fast={row['ema_fast']:.1f}, slow={row['ema_slow']:.1f})")
    
    # Now simulate the NEW event-based signal generation
    print(f"\n=== NEW EVENT-BASED SIGNAL GENERATION ===")
    signals = []
    
    for i, (idx, row) in enumerate(df.iterrows()):
        le = row['cross_above']  # long entry
        se = row['cross_below']  # short entry
        
        # Generate point-in-time event signals, not persistent states
        if le:
            signal = "long"
        elif se:
            signal = "short"
        else:
            signal = "flat"
        
        signals.append(signal)
        
        if signal != "flat":
            print(f"Bar {i:2d} ({idx}): EVENT signal = {signal:>5} (le={le}, se={se})")
    
    # Show all signals to see the pattern
    print(f"\n=== ALL SIGNALS ===")
    for i, (idx, signal) in enumerate(zip(df.index, signals)):
        print(f"Bar {i:2d}: {signal:>5}")
    
    # Check for consecutive same-direction entries
    state_changes = []
    for i in range(1, len(signals)):
        if signals[i] != signals[i-1]:
            state_changes.append((i, signals[i-1], signals[i]))
    
    print(f"\n=== CONSECUTIVE ENTRIES CHECK ===")
    consecutive_same = 0
    for i in range(1, len(state_changes)):
        prev_change = state_changes[i-1]
        curr_change = state_changes[i]
        
        # Check if we went flat->direction->flat->same_direction
        if (prev_change[2] != "flat" and curr_change[1] == "flat" and 
            curr_change[2] == prev_change[2]):
            consecutive_same += 1
            print(f"CONSECUTIVE: {prev_change} followed by {curr_change}")
    
    print(f"Total consecutive same-direction entries: {consecutive_same}")

if __name__ == "__main__":
    test_crossover_logic()