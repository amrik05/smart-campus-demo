import argparse
import re
import time
from datetime import datetime, timezone

import requests
import serial


LINE_RE = re.compile(
    r"Surface Temp:\s*(?P<temp>[-0-9.]+)\s*C\s*\|\s*"
    r"Turbidity raw:\s*(?P<turb_raw>\d+)\s*\((?P<turb_v>[0-9.]+)\s*V\)\s*\|\s*"
    r"TDS raw:\s*(?P<tds_raw>\d+)\s*\((?P<tds_v>[0-9.]+)\s*V\)"
)


def parse_line(line: str) -> dict | None:
    match = LINE_RE.search(line)
    if not match:
        return None
    return {
        "water_temp_c": float(match.group("temp")),
        "turb_raw": int(match.group("turb_raw")),
        "turb_v": float(match.group("turb_v")),
        "tds_raw": int(match.group("tds_raw")),
        "tds_v": float(match.group("tds_v")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Serial bridge for water node -> ingest API")
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM10)")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--building-id", default="RUTGERS-ENG-1")
    parser.add_argument("--site-id", default="RUTGERS")
    parser.add_argument("--building-zone", default="ENG-1-BASEMENT")
    parser.add_argument("--air-node-id", default="LIVE-001")
    parser.add_argument("--water-node-id", default="WATER-LIVE-001")
    parser.add_argument("--scenario", default="NORMAL")
    parser.add_argument("--data-source", default="LIVE")
    parser.add_argument("--air-temp-c", type=float, default=22.0)
    parser.add_argument("--air-rh-pct", type=float, default=45.0)
    parser.add_argument("--air-surface-temp-c", type=float, default=21.5)
    parser.add_argument("--air-co2-ppm", type=float, default=600.0)
    parser.add_argument("--air-voc-index", type=float, default=120.0)
    parser.add_argument("--turbidity-scale", type=float, default=1.0)
    parser.add_argument("--tds-scale", type=float, default=1.0)
    args = parser.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=1)
    seq = 0
    print(f"Listening on {args.port} @ {args.baud}...")

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        data = parse_line(line)
        if not data:
            continue

        turbidity_ntu = data["turb_raw"] * args.turbidity_scale
        tds_ppm = data["tds_raw"] * args.tds_scale

        payload = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "building_id": args.building_id,
            "site_id": args.site_id,
            "building_zone": args.building_zone,
            "air_node_id": args.air_node_id,
            "water_node_id": args.water_node_id,
            "air_temp_c": args.air_temp_c,
            "air_rh_pct": args.air_rh_pct,
            "air_surface_temp_c": args.air_surface_temp_c,
            "air_co2_ppm": args.air_co2_ppm,
            "air_voc_index": args.air_voc_index,
            "water_turbidity_ntu": turbidity_ntu,
            "water_tds_ppm": tds_ppm,
            "water_temp_c": data["water_temp_c"],
            "water_free_chlorine_mgL": 1.0,
            "scenario": args.scenario,
            "episode_id": "live_water",
            "data_source": args.data_source,
            "seq_water": seq,
        }

        try:
            requests.post(f"{args.api_url}/telemetry", json=payload, timeout=3)
        except Exception:
            pass

        seq += 1
        time.sleep(0.05)


if __name__ == "__main__":
    main()
