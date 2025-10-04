#!/usr/bin/env python3
"""
Simple diagnostic to check if crossover conditions are persisting.
"""

import pandas as pd


def check_signal_persistence():
    # Load the signals and see the actual pattern
    signals = pd.read_parquet("runs/researcher/run_20250928_193525_utc/signals.parquet")

    print("=== SIGNAL PERSISTENCE ANALYSIS ===")
    print(f"Total signals: {len(signals)}")
    print("Signal value counts:")
    print(signals["signal"].value_counts())

    # Find all signal changes
    signal_changes = signals[signals["signal"] != signals["signal"].shift(1)].copy()
    print(f"\nTotal signal changes: {len(signal_changes)}")

    # Look at the pattern: long periods vs single events
    print("\n=== SIGNAL DURATION ANALYSIS ===")

    current_signal = None
    signal_start = None
    durations = []

    for timestamp, row in signals.iterrows():
        if current_signal != row["signal"]:
            # Signal changed
            if current_signal is not None:
                duration = len(signals.loc[signal_start:timestamp]) - 1  # type: ignore[misc]
                durations.append((current_signal, signal_start, timestamp, duration))
                print(
                    f"{current_signal:>5}: {signal_start} to {timestamp} "
                    f"({duration:>3} bars)"
                )

            current_signal = row["signal"]
            signal_start = timestamp

    # Handle the last signal
    if current_signal is not None:
        duration = len(signals.loc[signal_start:])  # type: ignore[misc]
        durations.append((current_signal, signal_start, signals.index[-1], duration))
        print(
            f"{current_signal:>5}: {signal_start} to {signals.index[-1]} "
            f"({duration:>3} bars)"
        )

    # Analyze durations
    long_durations = [d for d in durations if d[0] == "long"]
    short_durations = [d for d in durations if d[0] == "short"]

    if long_durations:
        long_bars = [d[3] for d in long_durations]
        print(
            f"\nLong signal durations: min={min(long_bars)}, "
            f"max={max(long_bars)}, avg={sum(long_bars)/len(long_bars):.1f}"
        )

    if short_durations:
        short_bars = [d[3] for d in short_durations]
        print(
            f"Short signal durations: min={min(short_bars)}, "
            f"max={max(short_bars)}, avg={sum(short_bars)/len(short_bars):.1f}"
        )

    # The key insight: If signals were point-in-time events, each should last 1 bar
    # If they're persistent states, they'll last many bars
    long_duration_signals = [d for d in durations if d[3] > 1]
    print(f"\n🚨 PROBLEM: {len(long_duration_signals)} signals last more than 1 bar!")
    print("This proves signals are persistent states, not point-in-time events.")

    if len(long_duration_signals) > 0:
        print("\nExamples of persistent signals:")
        for signal, start, end, duration in long_duration_signals[:5]:
            print(f"  {signal}: {start} ({duration} bars)")


if __name__ == "__main__":
    check_signal_persistence()
