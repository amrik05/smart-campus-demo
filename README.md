# Smart Campus Demo (Rutgers/Verizon)

Demo-first monorepo for an IoT dual-node system:
Water node -> BLE -> Air node -> WiFi -> Cloud API -> Analytics -> Alerts -> Dashboard.

## Quickstart Demo (Pure Python)

1. Install deps

```bash
pip install -r requirements.txt
```

2. Run the all-in-one demo (API + dashboard + generator)

```bash
python scripts/run_demo.py --sequence NORMAL:30,MOLD_EPISODE:90
```

3. Open dashboard

- Streamlit: http://localhost:8501

## Docker (Optional)

```bash
docker-compose up --build
```

## Repo Structure

- `cloud/ingest_api`: FastAPI ingest service + SQLite storage
- `analytics`: QC, indices, forecasting, synthetic generator
- `app/dashboard_streamlit`: Minimal Streamlit dashboard
- `firmware`: ESP32 placeholders + payload schema
- `docs`: Architecture, API contract, BLE protocol, demo script, runbook

## Notes

- Demo is deterministic and accelerated (1 sec = 1 min)
- REST ingestion is real; storage is optional for now
- Hardware is stubbed but payloads are realistic and consistent

## Repo File Map

See `docs/file_map.md` for a detailed file-by-file description.

## Venv Setup

```bash
./scripts/setup_venv.sh
source .venv/bin/activate
```

## Demo GUI (Tkinter)

```bash
python scripts/tk_demo_gui.py --db /home/amrik/code/smart-campus/data/smart_campus.db
```

## ML Demo (Mold Model)

```bash
# Install all demo deps in venv
pip install -r requirements.txt

# Train + evaluate
./scripts/train_mold_demo.sh
```

Outputs:
- `data/mold_dataset.csv`
- `models/mold_lgbm.txt`
- `data/mold_eval.csv`
- `data/mold_metrics.json`
- `data/plots/mold_scatter.png`
- `data/plots/mold_timeline.png`

## ML Demo Details

See `docs/ml_demo.md` for dataset generation, imputation, and metrics.

ML demo tab is available in Streamlit after running the ML demo script.
