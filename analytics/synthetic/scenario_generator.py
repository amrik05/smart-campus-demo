import argparse
import random
import time
from datetime import datetime, timezone
from typing import Dict

import requests

from .demo_clock import DemoClock, utc_now_floor


def _quantize(value: float, step: float) -> float:
    return round(value / step) * step


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def build_payload(
    ts: datetime,
    scenario: str,
    step: int,
    seed: int,
) -> Dict[str, object]:
    rng = random.Random(seed + step)

    air_temp = 22.0 + rng.uniform(-0.3, 0.3)
    air_rh = 45.0 + rng.uniform(-2.0, 2.0)
    water_temp = 18.5 + rng.uniform(-0.2, 0.2)
    turb = 0.8 + rng.uniform(-0.1, 0.1)
    chlorine = 1.2 + rng.uniform(-0.1, 0.1)
    ph = 7.4 + rng.uniform(-0.05, 0.05)
    cond = 350.0 + rng.uniform(-10.0, 10.0)
    pressure = 280.0 + rng.uniform(-5.0, 5.0)

    if scenario == "MOLD_EPISODE":
        air_rh = min(95.0, 70.0 + 0.4 * step + rng.uniform(-1.5, 1.5))
        air_temp = 23.0 + rng.uniform(-0.2, 0.2)
    elif scenario == "WATER_EVENT":
        turb = 5.0 + 1.2 * step + rng.uniform(-2.0, 2.0)
        chlorine = max(0.1, 0.6 - 0.02 * step + rng.uniform(-0.05, 0.05))
        cond = 500.0 + 15.0 * step + rng.uniform(-20.0, 20.0)
    elif scenario == "SENSOR_FAULT":
        air_rh = 110.0  # out of range
        turb = 0.0
        chlorine = 0.0

    # Quantize and clip to mimic cheap sensors
    air_temp = _clip(_quantize(air_temp, 0.1), 15.0, 30.0)
    air_rh = _clip(_quantize(air_rh, 0.1), 20.0, 98.0)
    water_temp = _clip(_quantize(water_temp, 0.1), 5.0, 30.0)
    turb = _clip(_quantize(turb, 0.1), 0.0, 1000.0)
    chlorine = _clip(_quantize(chlorine, 0.01), 0.0, 5.0)
    ph = _clip(_quantize(ph, 0.01), 0.0, 14.0)
    cond = _clip(_quantize(cond, 1.0), 0.0, 5000.0)
    pressure = _clip(_quantize(pressure, 0.1), 0.0, 1000.0)

    air_co2 = _clip(_quantize(620.0 + rng.uniform(-40.0, 40.0), 1.0), 400.0, 2000.0)
    air_pm25 = _clip(_quantize(8.0 + rng.uniform(-3.0, 3.0), 1.0), 0.0, 150.0)
    air_tvoc = _clip(_quantize(150.0 + rng.uniform(-30.0, 30.0), 1.0), 0.0, 2000.0)
    air_surface_temp = _quantize(air_temp - 0.6 + rng.uniform(-0.1, 0.1), 0.1)
    air_material_moisture = _clip(_quantize(0.08 + (air_rh - 45.0) / 500.0, 0.01), 0.01, 0.6)

    payload = {
        "ts": ts.isoformat().replace("+00:00", "Z"),
        "building_id": "RUTGERS-ENG-1",
        "air_node_id": "AIR-001",
        "water_node_id": "WATER-001",
        "air_temp_c": air_temp,
        "air_rh_pct": air_rh,
        "water_temp_c": water_temp,
        "water_turbidity_ntu": turb,
        "water_free_chlorine_mgL": chlorine,
        "water_ph": ph,
        "water_conductivity_uScm": cond,
        "water_pressure_kpa": pressure,
        "scenario": scenario,
        "data_source": "EMULATED",
        "air_co2_ppm": air_co2,
        "air_pm25_ugm3": air_pm25,
        "air_tvoc": air_tvoc,
        "air_surface_temp_c": air_surface_temp,
        "air_material_moisture": air_material_moisture,
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
