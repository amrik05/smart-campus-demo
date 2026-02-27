import argparse
import random
import time
from datetime import datetime, timezone
from typing import Dict

import requests

from .demo_clock import DemoClock, utc_now_floor


def build_payload(
    ts: datetime,
    scenario: str,
    step: int,
    seed: int,
) -> Dict[str, object]:
    rng = random.Random(seed + step)

    air_temp = 22.0 + rng.uniform(-0.4, 0.4)
    air_rh = 45.0 + rng.uniform(-3.0, 3.0)
    water_temp = 18.5 + rng.uniform(-0.2, 0.2)
    turb = 0.8 + rng.uniform(-0.1, 0.1)
    chlorine = 1.2 + rng.uniform(-0.1, 0.1)
    ph = 7.4 + rng.uniform(-0.05, 0.05)
    cond = 350.0 + rng.uniform(-10.0, 10.0)
    pressure = 280.0 + rng.uniform(-5.0, 5.0)

    if scenario == "MOLD_EPISODE":
        air_rh = min(95.0, 75.0 + 0.5 * step + rng.uniform(-2.0, 2.0))
        air_temp = 23.0 + rng.uniform(-0.3, 0.3)
    elif scenario == "WATER_EVENT":
        turb = 5.0 + 1.2 * step + rng.uniform(-2.0, 2.0)
        chlorine = max(0.1, 0.6 - 0.02 * step + rng.uniform(-0.05, 0.05))
        cond = 500.0 + 15.0 * step + rng.uniform(-20.0, 20.0)
    elif scenario == "SENSOR_FAULT":
        air_rh = 110.0  # out of range
        turb = 0.0
        chlorine = 0.0

    payload = {
        "ts": ts.isoformat().replace("+00:00", "Z"),
        "building_id": "RUTGERS-ENG-1",
        "air_node_id": "AIR-001",
        "water_node_id": "WATER-001",
        "air_temp_c": round(air_temp, 2),
        "air_rh_pct": round(air_rh, 2),
        "water_temp_c": round(water_temp, 2),
        "water_turbidity_ntu": round(turb, 2),
        "water_free_chlorine_mgL": round(chlorine, 3),
        "water_ph": round(ph, 2),
        "water_conductivity_uScm": round(cond, 2),
        "water_pressure_kpa": round(pressure, 2),
        "scenario": scenario,
        "data_source": "EMULATED",
        "air_co2_ppm": 620.0 + rng.uniform(-30.0, 30.0),
        "air_pm25_ugm3": 8.0 + rng.uniform(-2.0, 2.0),
        "air_tvoc": 150.0 + rng.uniform(-20.0, 20.0),
        "air_surface_temp_c": round(air_temp - 0.6, 2),
        "air_material_moisture": round(0.08 + (air_rh - 45.0) / 500.0, 3),
    }
    return payload


def run_generator(api_url: str, scenario: str, rate_sec: float, count: int, seed: int) -> None:
    start_ts = utc_now_floor()
    clock = DemoClock(start_ts, speed=60.0)

    steps = count if count > 0 else None
    step = 0
    while steps is None or step < steps:
        ts = clock.tick()
        payload = build_payload(ts, scenario, step, seed)
        requests.post(f"{api_url}/telemetry", json=payload, timeout=5)
        time.sleep(rate_sec)
        step += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic telemetry generator")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--scenario", default="NORMAL")
    parser.add_argument("--rate-sec", type=float, default=1.0)
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    scenario = args.scenario.upper()
    run_generator(args.api_url, scenario, args.rate_sec, args.count, args.seed)


if __name__ == "__main__":
    main()
