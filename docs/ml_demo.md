# ML Demo (Mold Forecasting)

## Overview
This demo trains a LightGBM regressor to predict `idx_mold_risk(t+H)` from the last W minutes of engineered features.
No manual labels are required: targets are derived from physics-based indices.

## Data Generation (Synthetic)
- Scenarios: `NORMAL` and `MOLD_EPISODE`
- Accelerated time: 1 minute per row
- Episodes are stitched sequentially to avoid overlap
- Sensor realism:
  - Quantization (e.g., 0.1C, 0.1% RH)
  - Clipping to plausible ranges
  - Low-cost sensor noise

## Features
Base:
- `air_temp_c`, `air_rh_pct`, `dew_point_c`

Engineered:
- `rh_mean_w`
- `rh_slope_w`
- `temp_slope_w`
- `dew_point_slope_w`

Target:
- `target_idx_mold_h` = `idx_mold_now` shifted by `H` minutes

## Imputation Strategy (Demo)
When missing values are injected (optional):
1. Forward-fill (carry last observation)
2. Rolling mean for remaining gaps
3. Global mean fallback

This keeps the demo deterministic and stable while demonstrating a realistic ETL pattern.

## Metrics
- MAE
- Threshold-cross accuracy (default threshold = 0.6)
- Precision / Recall / F1 at threshold
- Average lead time (minutes) for threshold crossing

## Commands
```bash
pip install -r requirements-ml.txt
./scripts/train_mold_demo.sh
```

Outputs:
- `data/mold_dataset.csv`
- `models/mold_lgbm.txt`
- `data/mold_eval.csv`
- `data/plots/mold_scatter.png`
- `data/plots/mold_timeline.png`

## Dashboard Demo
- The Streamlit dashboard includes an 'ML Demo' tab.
- It replays a trained model's predictions from `data/mold_eval.csv`.
- Controls: scenario selection, playback speed, window size, threshold.
- Metrics: MAE + threshold accuracy + lead time.

Generate demo data with:
```bash
./scripts/train_mold_demo.sh
```
