# 3-Minute Demo Script

1. **Start demo**
- Say: "We run the ingest API, dashboard, and generator together in a single script."
- Command: `python scripts/run_demo.py --sequence NORMAL:30,MOLD_EPISODE:90`

3. **Dashboard walkthrough**
- Show latest telemetry values
- Show RH, mold index, forecast band
- Say: "Mold risk increases with sustained RH and dew point proximity."
- Show alerts feed when prediction crosses threshold

4. **Wrap**
- Say: "This is a full pipeline: ingest, QC, physics-based indices, forecasting, alerting, and a minimal dashboard."
