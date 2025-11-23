Data Directory

Purpose:
- `data/samples/` holds small, shareable CSVs for demos/tests.
- `data/full/` holds large production datasets (ignored by Git).

Rules:
- Do not commit files under `data/full/`. The root `.gitignore` keeps this
  directory tracked via `.gitkeep` but ignores its contents.
- Prefer normalized OHLCV CSVs with columns: `UTCTime, Open, High, Low, Close,
  Volume` to leverage the Data Handler normalizer.

Catalog usage:
- Point `config/data_catalog.yaml` symbol entries to files in one of these
  folders, for example:

  EURUSD:
    csv_path: "data/samples/eurusd_m1_sample.csv"  # small sample
  #EURUSD:
  #  csv_path: "data/full/eurusd_m1_2010_2024.csv"  # large file, ignored by Git
