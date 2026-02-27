#!/usr/bin/env bash
set -euo pipefail

# Build synthetic dataset
python -m analytics.etl.build_mold_dataset \
  --out /home/amrik/code/smart-campus/data/mold_dataset.csv \
  --hours 12 \
  --horizon-min 60 \
  --window-min 60

# Train model
python -m analytics.forecasting.train_mold_lgbm \
  --data /home/amrik/code/smart-campus/data/mold_dataset.csv \
  --out-model /home/amrik/code/smart-campus/models/mold_lgbm.txt

# Evaluate model
python -m analytics.forecasting.eval_mold_demo \
  --data /home/amrik/code/smart-campus/data/mold_dataset.csv \
  --model /home/amrik/code/smart-campus/models/mold_lgbm.txt \
  --out /home/amrik/code/smart-campus/data/mold_eval.csv
