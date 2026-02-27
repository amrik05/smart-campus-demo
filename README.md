# Smart Campus Demo (Rutgers/Verizon)

Demo-first monorepo for an IoT dual-node system:
Water node -> BLE -> Air node -> WiFi -> Cloud API -> Analytics -> Alerts -> Dashboard.

## Quickstart Demo

1. Start services

```bash
cd /home/amrik/code/smart-campus
docker-compose up --build
```

2. Run synthetic generator (accelerated time: 1 sec = 1 min)

```bash
python -m analytics.synthetic.scenario_generator --api-url http://localhost:8000 --scenario MOLD_EPISODE --rate-sec 1
```

3. Open dashboard

- Streamlit: http://localhost:8501

## Repo Structure

- `cloud/ingest_api`: FastAPI ingest service + SQLite storage
- `analytics`: QC, indices, forecasting, synthetic generator
- `app/dashboard_streamlit`: Minimal Streamlit dashboard
- `firmware`: ESP32 placeholders + payload schema
- `docs`: Architecture, API contract, BLE protocol, demo script, runbook

## Notes

- Demo is deterministic and accelerated (1 sec = 1 min)
- REST ingestion is real; storage and analytics are real
- Hardware is stubbed but payloads are realistic and consistent

## Repo File Map

See `docs/file_map.md` for a detailed file-by-file description.

## Venv Setup

```bash
./scripts/setup_venv.sh
source .venv/bin/activate
```
