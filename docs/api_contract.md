# API Contract

**Endpoint**
- `POST /telemetry`

**Required fields**
- `ts` (ISO8601 string)
- `building_id` (string)
- `air_node_id` (string)
- `water_node_id` (string)
- `air_temp_c` (float)
- `air_rh_pct` (float)
- `water_temp_c` (float)
- `water_turbidity_ntu` (float)
- `water_free_chlorine_mgL` (float)
- `water_ph` (float)
- `water_conductivity_uScm` (float)
- `water_pressure_kpa` (float)
- `scenario` (enum: `NORMAL`, `MOLD_EPISODE`, `WATER_EVENT`, `SENSOR_FAULT`)
- `data_source` (enum: `LIVE`, `EMULATED`)

**Optional fields**
- `air_co2_ppm`
- `air_pm25_ugm3`
- `air_tvoc`
- `air_surface_temp_c`
- `air_material_moisture`

**Behavior**
- Validate schema
- Store raw telemetry
- Compute QC + sensor health score
- Compute indices + forecast + alerts
- Store outputs in separate tables
