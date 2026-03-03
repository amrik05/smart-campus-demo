# BLE Protocol (Placeholder)

**Purpose**
Water node transmits water telemetry to air node over BLE.

**Payload (JSON over BLE or CBOR in real build)**
- `ts`
- `water_temp_c`
- `water_turbidity_ntu`
- `water_free_chlorine_mgL`
- `water_tds_ppm`
- `seq_water` (optional)
- `battery_mv` (optional)
- `flags` (optional)

**Notes**
- In demo, BLE is simulated by synthetic generator
