# Architecture

**Flow**
Water node -> BLE -> Air node -> WiFi -> Cloud Ingest API -> Analytics -> Alerts -> Dashboard.

**Components**
- Water node (ESP32 placeholder): Water quality sensors
- Air node (ESP32 placeholder): Air environment sensors + BLE receiver
- Ingest API (FastAPI): Validates and stores telemetry, computes QC/indices/forecast/alerts
- SQLite: Demo storage (raw telemetry, features, predictions, alerts)
- Analytics modules: QC, physics helpers, indices, forecasting, synthetic data
- Streamlit dashboard: Real-time demo view

**Demo constraints**
- Deterministic synthetic generator
- Accelerated time: 1 second = 1 minute
- Minimal dependencies, real computations
