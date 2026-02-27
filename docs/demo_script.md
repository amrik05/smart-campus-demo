# 3-Minute Demo Script

1. **Start services**
- Say: "We run the ingest API and dashboard locally with docker-compose."
- Command: `docker-compose up --build`

2. **Start synthetic telemetry**
- Say: "We generate accelerated telemetry at 1 second per minute for quick validation."
- Command: `python -m analytics.synthetic.scenario_generator --api-url http://localhost:8000 --scenario MOLD_EPISODE --rate-sec 1`

3. **Dashboard walkthrough**
- Show latest telemetry values
- Show RH, mold index, forecast band
- Say: "Mold risk increases with sustained RH and dew point proximity."
- Show alerts feed when prediction crosses threshold

4. **Switch scenario**
- Stop generator, restart with `WATER_EVENT`
- Say: "Water event risk rises with turbidity spikes and low chlorine."

5. **Wrap**
- Say: "This is a full pipeline: ingest, QC, physics-based indices, forecasting, alerting, and a minimal dashboard."
