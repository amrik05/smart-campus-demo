# API Contract

**Endpoint**
- `POST /telemetry`
- `GET /latest`
- `GET /history?air_node_id=...&minutes=...`

**Required fields**
- `ts` (ISO8601 string)
- `building_id` (string)
- `air_node_id` (string)
- `water_node_id` (string)
- `air_temp_c` (float)
- `air_rh_pct` (float)
- `water_turbidity_ntu` (float)
- `water_tds_ppm` (float)
- `water_temp_c` (float)
- `water_free_chlorine_mgL` (float)
- `scenario` (enum: `NORMAL`, `MOLD_EPISODE`, `WATER_EVENT`)
- `data_source` (enum: `LIVE`, `EMULATED`)

**Optional fields**
- `air_co2_ppm`
- `air_surface_temp_c`
- `air_voc_index`
- `episode_id`
- `seq_water`
- `rssi_ble`
- `battery_mv`
- `flags`

**Behavior**
- Validate schema
- Normalize and clamp values
- Compute features + indices + forecast + alerts
- Return normalized + features + prediction + alert in response
