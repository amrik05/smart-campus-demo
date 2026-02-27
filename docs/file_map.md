# File Map

This is a low-level map of the repo, with purpose and integration notes.

## Root
- `README.md`: Quickstart + top-level usage.
- `docker-compose.yml`: Runs FastAPI ingest and Streamlit dashboard, shared SQLite file in `./data/`.
- `.gitignore`: Python/SQLite artifacts.

## docs/
- `docs/architecture.md`: Component flow and high-level architecture.
- `docs/api_contract.md`: Exact ingest contract for `/telemetry`.
- `docs/ble_protocol.md`: Placeholder BLE payload spec.
- `docs/demo_script.md`: 3-minute talk track and steps.
- `docs/runbook.md`: Troubleshooting commands and issues.
- `docs/file_map.md`: This document.
- `docs/samples/*.json`: Example payloads for NORMAL, MOLD_EPISODE, WATER_EVENT.

## firmware/
- `firmware/air_node_esp32/README.md`: Air node intent and integration plan.
- `firmware/air_node_esp32/main_stub.cpp`: Placeholder main stub.
- `firmware/water_node_esp32/README.md`: Water node intent and integration plan.
- `firmware/water_node_esp32/main_stub.cpp`: Placeholder main stub.
- `firmware/shared/payload_schema.h`: Shared schema notes for payload fields.

## cloud/ingest_api/
FastAPI service. Mounts SQLite at `/data/smart_campus.db` in docker-compose.

- `cloud/ingest_api/app/main.py`: FastAPI app + startup DB init.
- `cloud/ingest_api/app/db.py`: SQLAlchemy engine/session.
- `cloud/ingest_api/app/models.py`: SQLAlchemy models.
- `cloud/ingest_api/app/schemas.py`: Pydantic input/output schemas.
- `cloud/ingest_api/app/routes.py`: `/telemetry` endpoint, QC, indices, forecast, alerts.
- `cloud/ingest_api/app/settings.py`: Config via env vars.
- `cloud/ingest_api/tests/test_schema_validation.py`: Basic schema validation tests.
- `cloud/ingest_api/requirements.txt`: API dependencies.
- `cloud/ingest_api/Dockerfile`: Container for FastAPI service.

Integration flow:
1. POST `/telemetry` -> Pydantic validation.
2. Raw row stored to `raw_telemetry`.
3. QC flags + sensor health score computed.
4. Mold + water risk indices computed.
5. Baseline forecast computed for mold index.
6. Alerts emitted for consecutive threshold breaches.
7. Results stored in `features`, `predictions`, `alerts` tables.

## analytics/
Local Python modules used by ingest and generator.

- `analytics/indices/physics.py`: Dew point + clamp helpers.
- `analytics/indices/mold_index.py`: Mold risk index (0-1).
- `analytics/indices/water_index.py`: Water event risk index (0-1).
- `analytics/features/rolling.py`: Rolling mean/slope helpers.
- `analytics/features/build_features.py`: Feature builders.
- `analytics/forecasting/baseline.py`: Baseline mold risk forecasting.
- `analytics/forecasting/metrics.py`: Forecast metrics.
- `analytics/synthetic/demo_clock.py`: Accelerated-time clock (1 sec = 1 min).
- `analytics/synthetic/scenario_generator.py`: Synthetic telemetry generator.
- `analytics/evaluation/make_plots.py`: Placeholder for evaluation.

Integration notes:
- Analytics modules are imported by FastAPI container and Streamlit container.
- `scenario_generator.py` can be run locally to POST data to ingest API.

## app/dashboard_streamlit/
Streamlit dashboard.

- `app/dashboard_streamlit/app.py`: Dashboard views and queries to SQLite.
- `app/dashboard_streamlit/requirements.txt`: Dashboard deps.
- `app/dashboard_streamlit/Dockerfile`: Container for Streamlit.

Integration notes:
- Reads same SQLite DB as ingest via `DATABASE_URL` env.
- Uses simple SQL queries to show latest telemetry, indices, forecasts, alerts.
