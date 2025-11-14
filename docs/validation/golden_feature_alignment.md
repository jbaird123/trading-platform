## Golden Feature Alignment

This builder is responsible for the parquet snapshots under
`data/dvc/golden/features/tradingview/cache/eurusd`. Every row in those files
represents the set of facts that were **available the instant a bar opened**,
across all of the timeframes we care about (1h, 4h, 1d, …). The rules below are
what keep the snapshots free of look‑ahead bias.

### Terms

- **available_at** – the timestamp of the bar that just opened (taken directly
  from the TradingView CSV for the base timeframe).
- **bar_open / bar_close** – the true session open/close timestamps for the
  bar whose data we copied into the row. For example, `4h_bar_open` is the
  actual open of the 4‑hour bar that closed before `available_at`.
- **bar_lookup_key** – the exact timestamp stored in the TradingView CSV. This
  lets us look up the original row without having to reverse the timezone math.
- **feature columns** – all indicator columns start with lowercase Pandas-
  style timeframe aliases (`1h_`, `4h_`, `1d_`, `5min_`, …). This ensures the
  parquet schema always reflects canonical timeframe labels.

### How rows are produced

1. **Start with the raw CSV for the base timeframe** (e.g. the 1h file). For
   each CSV row we create one parquet row and set `available_at` equal to the
   CSV timestamp (the bar’s open).

2. **For each timeframe (including the base one)** we derive bar closes by
   adding the timeframe duration to the CSV open. We then find the most recent
   bar whose derived close is `<= available_at`. That is the bar whose data is
   safe to copy into the parquet row.

3. **Copy indicator columns** from that bar into the parquet row. This includes
   the base timeframe (so a 1h parquet row contains the 1h values from the
   *previous* bar).

4. **Record metadata**:
   - `*_bar_open` – the true session open of the bar we copied.
   - `*_bar_close` – the true session close of that bar.
   - `*_bar_lookup_key` – the TradingView timestamp for the bar (so you can
     paste it into the CSV and get the matching row).

5. **Repeat** the same process for the 4h parquet, the 1d parquet, etc.

### Invariants

- `*_bar_open < *_bar_close`
- `*_bar_close <= available_at`
- `*_bar_lookup_key` matches the `time` column inside the corresponding CSV.

If any of those invariants are violated the validation suite will fail, which
signals that the builder introduced look‑ahead risk. This document is the
canonical reference for how the builder is expected to work.
