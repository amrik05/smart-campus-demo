#!/usr/bin/env bash
set -euo pipefail

# Build synthetic dataset
python -m analytics.etl.build_mold_dataset \
  --out /home/amrik/code/smart-campus/data/mold_dataset.csv \
  --hours 12 \
  --horizon-min 60 \
  --window-min 60 \
  --episodes-per-scenario 3 \
  --missing-rate 0.02

# Train model
python -m analytics.forecasting.train_mold_lgbm \
  --data /home/amrik/code/smart-campus/data/mold_dataset.csv \
  --out-model /home/amrik/code/smart-campus/models/mold_lgbm.txt

# Evaluate model
python -m analytics.forecasting.eval_mold_demo \
  --data /home/amrik/code/smart-campus/data/mold_dataset.csv \
  --model /home/amrik/code/smart-campus/models/mold_lgbm.txt \
  --out /home/amrik/code/smart-campus/data/mold_eval.csv \
  --threshold 0.6 \
  --out-metrics /home/amrik/code/smart-campus/data/mold_metrics.json

# Generate plots for demo
python -m analytics.evaluation.mold_demo_plots \
  --eval /home/amrik/code/smart-campus/data/mold_eval.csv \
  --out-dir /home/amrik/code/smart-campus/data/plots
