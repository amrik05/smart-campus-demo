# Session Summary (Smart Campus Demo)

This file captures the key decisions, commands, and code touchpoints from the current Codex session. It is meant to replace chat history in Codex mode.

## What Was Built
- Pure Python demo runner to start API + Streamlit + generator in one command.
- In-memory pipeline (no SQLite required) with stages:
  - normalize + clamp
  - rolling features + lags
  - mold/water indices
  - forecast (baseline or LightGBM)
  - predictive alerts + event timing
- Two dashboard tabs:
  - **Live Sensors** (for real ESP32 stream)
  - **Controlled Demo** (synthetic stream `SIM-001`)
- Controlled synthetic mold episode designed to show:
  - predicted risk crossing threshold before current risk
  - current risk crossing later
- Sticky alert banner, explicit red threshold line, live RH chart, ETA to threshold, and event time stamps in the UI.

## Quick Commands

### Install deps
```bash
pip install -r requirements.txt
pip install -r requirements-dashboard.txt
```

### Retrain model (after generator changes)
```bash
./scripts/train_mold_demo.sh
```

### Run demo (controlled episode)
```bash
python scripts/run_demo.py --sequence NORMAL:60,MOLD_EPISODE:120 --model lgbm
```

### Run API to accept ESP32 posts
```bash
python scripts/run_demo.py --api-host 0.0.0.0 --sequence NORMAL:60,MOLD_EPISODE:120 --model lgbm
```
ESP32 should post to:
```
http://<your-laptop-ip>:8000/telemetry
```

## Key Thresholds
- Alert threshold: **0.8**
- Horizon: **60 min** (set by `FORECAST_HORIZON_MIN`)

## Important Files

### API / Pipeline
- `cloud/ingest_api/app/pipeline.py`  
  Normalize, features, mold index, forecast, alert state, event timing.
- `cloud/ingest_api/app/state.py`  
  Rolling windows, lag buffers, event timing state.
- `cloud/ingest_api/app/routes.py`  
  `/telemetry`, `/latest?air_node_id=...`, `/history`.
- `cloud/ingest_api/app/ml_model.py`  
  LightGBM loader + feature vector mapping.

### Generator
- `analytics/synthetic/scenario_generator.py`  
  Controlled mold episode with smooth ramp; supports `air_node_id` override and context fields.

### Dashboard
- `app/dashboard_streamlit/app.py`  
  Two tabs, alert banner, red threshold line, ETA, event time stamps.

### ML Training
- `analytics/etl/build_mold_dataset.py`  
  Synthetic dataset with ramp + plateau, rolling stats, lags, context features.
- `analytics/forecasting/train_mold_lgbm.py`
- `scripts/train_mold_demo.sh`

## Data Schema (Canonical)
Telemetry JSON fields (core):
- `ts`, `building_id`, `air_node_id`, `water_node_id`
- Air: `air_temp_c`, `air_rh_pct`, `air_surface_temp_c`, `air_co2_ppm`, `air_voc_index`
- Water: `water_turbidity_ntu`, `water_tds_ppm`, `water_temp_c`, `water_free_chlorine_mgL`
- Meta: `scenario`, `episode_id`, `data_source`, `seq_water`, `rssi_ble`, `battery_mv`, `flags`
- Context: `site_id`, `building_zone`, `outdoor_temp_c`, `outdoor_rh_pct`, `outdoor_dew_point_c`, `tod_sin`, `tod_cos`, `dow_sin`, `dow_cos`

## Demo Notes
- Controlled demo stream uses `SIM-001`.
- Live sensors should use a different `air_node_id` (e.g., `LIVE-001`).
- Dashboard auto-detects `air_node_id` for live tab.
- Event timestamps are tracked per episode and displayed.

## Next Ideas (Optional)
- Add UI selector for live node id.
- Add “record/replay” mode for real humidifier footage.
- Add “cloud tunnel” mode (ngrok/cloudflared).
