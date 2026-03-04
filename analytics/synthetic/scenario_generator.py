import argparse
import math
import random
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests

from .demo_clock import DemoClock, utc_now_floor


def _quantize(value: float, step: float) -> float:
    return round(value / step) * step


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _tod_features(ts: datetime) -> Tuple[float, float, float, float]:
    minutes = ts.hour * 60 + ts.minute
    angle = 2.0 * math.pi * minutes / (24 * 60)
    tod_sin = math.sin(angle)
    tod_cos = math.cos(angle)
    dow = ts.weekday()
    dow_angle = 2.0 * math.pi * dow / 7.0
    dow_sin = math.sin(dow_angle)
    dow_cos = math.cos(dow_angle)
    return tod_sin, tod_cos, dow_sin, dow_cos


def build_payload(
    ts: datetime,
    scenario: str,
    step: int,
    seed: int,
    episode_id: Optional[str],
    air_node_id: str,
    water_node_id: str,
    building_id: str,
    site_id: str,
    building_zone: str,
) -> Dict[str, object]:
    rng = random.Random(seed + step)

    air_temp = 22.0 + rng.uniform(-0.3, 0.3)
    air_rh = 45.0 + rng.uniform(-2.0, 2.0)
    water_temp = 18.5 + rng.uniform(-0.2, 0.2)
    turb = 0.8 + rng.uniform(-0.1, 0.1)
    chlorine = 1.2 + rng.uniform(-0.1, 0.1)
    tds = 350.0 + rng.uniform(-20.0, 20.0)

    if scenario == "MOLD_EPISODE":
        # Faster ramp for short demo: ensure threshold crossing within ~40s
        ramp = min(1.0, max(0.0, (step - 3) / 24.0))
        air_rh = 62.0 + 36.0 * ramp + rng.uniform(-0.4, 0.4)
        air_temp = 23.0 + rng.uniform(-0.15, 0.15)
    elif scenario == "WATER_EVENT":
        turb = 5.0 + 1.2 * step + rng.uniform(-2.0, 2.0)
        chlorine = max(0.1, 0.6 - 0.02 * step + rng.uniform(-0.05, 0.05))
        tds = 500.0 + 15.0 * step + rng.uniform(-20.0, 20.0)

    # Quantize and clip to mimic cheap sensors
    air_temp = _clip(_quantize(air_temp, 0.1), 15.0, 30.0)
    air_rh = _clip(_quantize(air_rh, 0.1), 20.0, 98.0)
    water_temp = _clip(_quantize(water_temp, 0.1), 5.0, 30.0)
    turb = _clip(_quantize(turb, 0.1), 0.0, 1000.0)
    chlorine = _clip(_quantize(chlorine, 0.01), 0.0, 5.0)
    tds = _clip(_quantize(tds, 1.0), 0.0, 5000.0)

    air_co2 = _clip(_quantize(620.0 + rng.uniform(-40.0, 40.0), 1.0), 400.0, 2000.0)
    air_voc_index = _clip(_quantize(120.0 + rng.uniform(-30.0, 30.0), 1.0), 0.0, 500.0)
    # Surface temp drifts down during mold episode to reduce dew margin
    surface_delta = -0.6 - (0.01 * step if scenario == "MOLD_EPISODE" else 0.0)
    air_surface_temp = _clip(_quantize(air_temp + surface_delta + rng.uniform(-0.1, 0.1), 0.1), -20.0, 80.0)

    outdoor_temp = _quantize(10.0 + 5.0 * math.sin(step / 30.0) + rng.uniform(-0.5, 0.5), 0.1)
    outdoor_rh = _clip(_quantize(65.0 + 10.0 * math.cos(step / 40.0) + rng.uniform(-1.5, 1.5), 0.1), 20.0, 100.0)
    outdoor_dp = _quantize(outdoor_temp - (100.0 - outdoor_rh) / 5.0, 0.1)
    tod_sin, tod_cos, dow_sin, dow_cos = _tod_features(ts)

    payload = {
        "ts": ts.isoformat().replace("+00:00", "Z"),
        "building_id": building_id,
        "site_id": site_id,
        "building_zone": building_zone,
        "air_node_id": air_node_id,
        "water_node_id": water_node_id,
        "air_temp_c": air_temp,
        "air_rh_pct": air_rh,
        "water_temp_c": water_temp,
        "water_turbidity_ntu": turb,
        "water_free_chlorine_mgL": chlorine,
        "water_tds_ppm": tds,
        "scenario": scenario,
        "episode_id": episode_id,
        "data_source": "EMULATED",
        "seq_water": step,
        "rssi_ble": int(-60 + rng.uniform(-5, 5)),
        "battery_mv": int(3850 + rng.uniform(-30, 30)),
        "flags": 0,
        "outdoor_temp_c": outdoor_temp,
        "outdoor_rh_pct": outdoor_rh,
        "outdoor_dew_point_c": outdoor_dp,
        "tod_sin": tod_sin,
        "tod_cos": tod_cos,
        "dow_sin": dow_sin,
        "dow_cos": dow_cos,
        "air_co2_ppm": air_co2,
        "air_voc_index": air_voc_index,
        "air_surface_temp_c": air_surface_temp,
    }
    return payload


def run_generator(
    api_url: str,
    scenario: str,
    rate_sec: float,
    count: int,
    seed: int,
    episode_id: Optional[str],
    air_node_id: str,
    water_node_id: str,
    building_id: str,
    site_id: str,
    building_zone: str,
) -> None:
    start_ts = utc_now_floor()
    clock = DemoClock(start_ts, speed=60.0)

    steps = count if count > 0 else None
    step = 0
    while steps is None or step < steps:
        ts = clock.tick()
        payload = build_payload(
            ts,
            scenario,
            step,
            seed,
            episode_id,
            air_node_id,
            water_node_id,
            building_id,
            site_id,
            building_zone,
        )
        requests.post(f"{api_url}/telemetry", json=payload, timeout=5)
        time.sleep(rate_sec)
        step += 1


def run_sequence(
    api_url: str,
    sequence: List[Tuple[str, int]],
    rate_sec: float,
    seed: int,
    air_node_id: str,
    water_node_id: str,
    building_id: str,
    site_id: str,
    building_zone: str,
) -> None:
    start_ts = utc_now_floor()
    clock = DemoClock(start_ts, speed=60.0)
    step = 0
    for scenario, duration_s in sequence:
        episode_id = f"{scenario.lower()}_{int(time.time())}"
        steps = max(1, int(duration_s / rate_sec))
        for _ in range(steps):
            ts = clock.tick()
            payload = build_payload(
                ts,
                scenario,
                step,
                seed,
                episode_id,
                air_node_id,
                water_node_id,
                building_id,
                site_id,
                building_zone,
            )
            requests.post(f"{api_url}/telemetry", json=payload, timeout=5)
            time.sleep(rate_sec)
            step += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic telemetry generator")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--scenario", default="NORMAL")
    parser.add_argument("--sequence", default="")
    parser.add_argument("--rate-sec", type=float, default=1.0)
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--episode-id", default=None)
    parser.add_argument("--air-node-id", default="SIM-001")
    parser.add_argument("--water-node-id", default="WATER-001")
    parser.add_argument("--building-id", default="RUTGERS-ENG-1")
    parser.add_argument("--site-id", default="RUTGERS")
    parser.add_argument("--building-zone", default="ENG-1-BASEMENT")
    args = parser.parse_args()

    if args.sequence:
        parts = []
        for chunk in args.sequence.split(","):
            name, dur = chunk.split(":")
            parts.append((name.upper(), int(dur)))
        run_sequence(
            args.api_url,
            parts,
            args.rate_sec,
            args.seed,
            args.air_node_id,
            args.water_node_id,
            args.building_id,
            args.site_id,
            args.building_zone,
        )
    else:
        scenario = args.scenario.upper()
        run_generator(
            args.api_url,
            scenario,
            args.rate_sec,
            args.count,
            args.seed,
            args.episode_id,
            args.air_node_id,
            args.water_node_id,
            args.building_id,
            args.site_id,
            args.building_zone,
        )


if __name__ == "__main__":
    main()
