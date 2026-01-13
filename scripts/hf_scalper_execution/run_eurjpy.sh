#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
poetry run python -m trading_platform.cli run-backtest --config scripts/hf_scalper_execution/hf_scalper_eurjpy.yaml
