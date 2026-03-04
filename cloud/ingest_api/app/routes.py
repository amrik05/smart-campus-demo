from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

from fastapi import APIRouter, Query, HTTPException

from . import schemas
import os
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock, Thread, Event
import time
import csv

from .pipeline import AlertConfig, ForecastConfig, run_pipeline
from .state import GlobalState
from analytics.synthetic.scenario_generator import build_payload
import requests
from analytics.synthetic.demo_clock import DemoClock, utc_now_floor

router = APIRouter()
state = GlobalState()
demo_state = GlobalState()
# Keep merged output separate from raw live nodes
state.latest_live_path = os.getenv("LATEST_LIVE_PATH", "data/latest_merged.json")

forecast_cfg = ForecastConfig(
    horizon_min=int(os.getenv("FORECAST_HORIZON_MIN", "30")),
    model_mode=os.getenv("MODEL_MODE", "baseline"),
)
demo_forecast_cfg = ForecastConfig(
    horizon_min=int(os.getenv("DEMO_FORECAST_HORIZON_MIN", "30")),
    model_mode=os.getenv("MODEL_MODE", "baseline"),
)
alert_cfg = AlertConfig(threshold=0.8, hysteresis=0.05, persistence_n=3, interval_s=10)

# Raw ingest defaults for ESP32 bridge
DEFAULT_BUILDING_ID = os.getenv("BUILDING_ID", "RUTGERS-ENG-1")
DEFAULT_SITE_ID = os.getenv("SITE_ID", "RUTGERS")
DEFAULT_ZONE = os.getenv("BUILDING_ZONE", "ENG-1-BASEMENT")
DEFAULT_AIR_NODE = os.getenv("AIR_NODE_ID", "LIVE-001")
DEFAULT_WATER_NODE = os.getenv("WATER_NODE_ID", "WATER-LIVE-001")
TURB_SCALE = float(os.getenv("TURBIDITY_SCALE", "1.0"))
TDS_SCALE = float(os.getenv("TDS_SCALE", "1.0"))
WATER_LOG_PATH = Path(os.getenv("WATER_LOG_PATH", "data/live_water_log.csv"))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _merge_if_ready() -> dict | None:
    air = state.latest_air_raw
    water = state.latest_water_raw
    if not air or not water:
        return None

    now = _now_utc()
    air_ts = air.get("ts", now)
    water_ts = water.get("ts", now)
    if (now - air_ts).total_seconds() > 5 or (now - water_ts).total_seconds() > 5:
        return None

    air_voc_raw = float(air.get("air_voc_raw", 0.0))
    air_voc_index = min(500.0, air_voc_raw / 100.0)

    payload = {
        "ts": max(air_ts, water_ts).isoformat().replace("+00:00", "Z"),
        "building_id": DEFAULT_BUILDING_ID,
        "site_id": DEFAULT_SITE_ID,
        "building_zone": DEFAULT_ZONE,
        "air_node_id": DEFAULT_AIR_NODE,
        "water_node_id": DEFAULT_WATER_NODE,
        "air_temp_c": float(air.get("air_temp_c", 22.0)),
        "air_rh_pct": float(air.get("air_rh_pct", 45.0)),
        "air_surface_temp_c": float(air.get("air_temp_c", 22.0)),
        "air_co2_ppm": float(air.get("air_co2_ppm", 600.0)),
        "air_voc_index": air_voc_index,
        "water_turbidity_ntu": float(water.get("turbidity_raw", 0.0)) * TURB_SCALE,
        "water_tds_ppm": float(water.get("tds_raw", 0.0)) * TDS_SCALE,
        "water_temp_c": float(water.get("surface_temp_c", 18.0)),
        "water_free_chlorine_mgL": 1.0,
        "scenario": "NORMAL",
        "episode_id": "live_stream",
        "data_source": "LIVE",
        "seq_water": int(water.get("seq", 0)),
    }
    return payload


@router.post("/telemetry/air")
def ingest_air_raw(payload: dict):
    _ensure_summary_thread()
    ts = _now_utc()
    if "ts" in payload:
        try:
            ts = datetime.fromisoformat(str(payload["ts"]).replace("Z", "+00:00"))
        except Exception:
            ts = _now_utc()
    payload["ts"] = ts
    state.latest_air_raw = payload
    _update_live_nodes("air", payload, "/telemetry/air")
    merged = _merge_if_ready()
    if merged:
        return run_pipeline(merged, state, forecast_cfg, alert_cfg)
    return {"status": "ok", "detail": "air cached"}


@router.post("/telemetry/water")
def ingest_water_raw(payload: dict):
    _ensure_summary_thread()
    ts = _now_utc()
    if "ts" in payload:
        try:
            ts = datetime.fromisoformat(str(payload["ts"]).replace("Z", "+00:00"))
        except Exception:
            ts = _now_utc()
    payload["ts"] = ts
    state.latest_water_raw = payload
    _update_live_nodes("water", payload, "/telemetry/water")
    # Append to CSV log for training
    try:
        WATER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_header = not WATER_LOG_PATH.exists()
        with WATER_LOG_PATH.open("a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(
                    [
                        "ts",
                        "surface_temp_c",
                        "turbidity_raw",
                        "tds_raw",
                        "turbidity_v",
                        "tds_v",
                    ]
                )
            writer.writerow(
                [
                    ts.isoformat(),
                    payload.get("surface_temp_c"),
                    payload.get("turbidity_raw"),
                    payload.get("tds_raw"),
                    payload.get("turbidity_v"),
                    payload.get("tds_v"),
                ]
            )
    except Exception:
        pass
    merged = _merge_if_ready()
    if merged:
        return run_pipeline(merged, state, forecast_cfg, alert_cfg)
    return {"status": "ok", "detail": "water cached"}


# Backward-compatible paths from ESP firmware
@router.post("/telemetry/air/raw")
def ingest_air_raw_compat(payload: dict):
    return ingest_air_raw(payload)


@router.post("/telemetry/water/raw")
def ingest_water_raw_compat(payload: dict):
    return ingest_water_raw(payload)
latest_json_path = Path(os.getenv("LATEST_JSON_PATH", "data/latest_telemetry.json"))
live_nodes_json_path = Path(os.getenv("LIVE_NODES_JSON_PATH", "data/latest_live_nodes.json"))
demo_latest_json_path = Path(os.getenv("DEMO_LATEST_JSON_PATH", "data/demo_latest.json"))
demo_history_json_path = Path(os.getenv("DEMO_HISTORY_JSON_PATH", "data/demo_history.json"))
_live_nodes_lock = Lock()
_live_nodes_state: Dict[str, Any] = {
    "saved_ts": None,
    "live_sensor_data": {
        "air": None,
        "water": None,
    },
}

_summary_thread_started = False
_demo_thread: Thread | None = None
_demo_stop = Event()
_demo_running = False

DEMO_API_URL = os.getenv("DEMO_API_URL", "http://127.0.0.1:8001")


def _live_summary_loop(interval_s: int = 5) -> None:
    while True:
        air = state.latest_air_raw
        water = state.latest_water_raw
        air_msg = "none" if not air else f"T={air.get('air_temp_c')} RH={air.get('air_rh_pct')} VOCraw={air.get('air_voc_raw')}"
        water_msg = "none" if not water else f"T={water.get('surface_temp_c')} turb={water.get('turbidity_raw')} tds={water.get('tds_raw')}"
        print(f"[LIVE SUMMARY] air={air_msg} | water={water_msg}")
        time.sleep(interval_s)


def _ensure_summary_thread() -> None:
    global _summary_thread_started
    if _summary_thread_started:
        return
    _summary_thread_started = True
    t = Thread(target=_live_summary_loop, daemon=True)
    t.start()


def _run_demo_sequence(sequence: list[tuple[str, int]], rate_sec: float, seed: int, speed: float) -> None:
    global _demo_running
    _demo_running = True
    start_ts = utc_now_floor()
    clock = DemoClock(start_ts, speed=speed)
    step = 0
    for scenario, duration_s in sequence:
        episode_id = f"{scenario.lower()}_{int(time.time())}"
        steps = max(1, int(duration_s / rate_sec))
        for _ in range(steps):
            if _demo_stop.is_set():
                _demo_running = False
                return
            ts = clock.tick()
            payload = build_payload(
                ts,
                scenario,
                step,
                seed,
                episode_id,
                "SIM-001",
                "WATER-001",
                "RUTGERS-ENG-1",
                "RUTGERS",
                "ENG-1-BASEMENT",
            )
            try:
                requests.post(f"{DEMO_API_URL}/demo/telemetry", json=payload, timeout=3)
            except Exception:
                pass
            time.sleep(rate_sec)
            step += 1
    _demo_running = False


@router.post("/demo/start")
def demo_start(
    sequence: str = "NORMAL:30,MOLD_EPISODE:90",
    rate_sec: float = 1.0,
    seed: int = 42,
    speed: float = 60.0,
):
    global _demo_thread
    if _demo_running:
        return {"status": "already_running"}
    _demo_stop.clear()
    parts = []
    for chunk in sequence.split(","):
        name, dur = chunk.split(":")
        parts.append((name.upper(), int(dur)))
    _demo_thread = Thread(target=_run_demo_sequence, args=(parts, rate_sec, seed, speed), daemon=True)
    _demo_thread.start()
    return {"status": "started", "sequence": sequence}


@router.post("/demo/stop")
def demo_stop():
    _demo_stop.set()
    return {"status": "stopping"}


@router.get("/demo/status")
def demo_status():
    return {"running": _demo_running}


@router.post("/demo/telemetry", response_model=schemas.IngestResponse)
def ingest_demo_telemetry(payload: schemas.TelemetryIn):
    result = run_pipeline(payload.dict(), demo_state, demo_forecast_cfg, alert_cfg)
    # Persist latest + rolling demo history for tuning
    try:
        demo_latest_json_path.parent.mkdir(parents=True, exist_ok=True)
        demo_latest_json_path.write_text(json.dumps(result, indent=2, default=str))
        history_blob = []
        if demo_history_json_path.exists():
            try:
                history_blob = json.loads(demo_history_json_path.read_text())
            except Exception:
                history_blob = []
        history_blob.append(result)
        history_blob = history_blob[-500:]
        demo_history_json_path.write_text(json.dumps(history_blob, indent=2, default=str))
    except Exception:
        pass
    return result


@router.get("/demo/latest")
def demo_latest():
    if not demo_state.latest_response:
        return {"status": "empty"}
    return demo_state.latest_response


@router.get("/demo/history")
def demo_history(
    air_node_id: str = Query(default="SIM-001"),
    minutes: int = Query(default=30, ge=1, le=43200),
):
    if not demo_state.history:
        return {"rows": []}
    latest_ts = demo_state.history[-1]["normalized"]["ts"]
    cutoff = latest_ts - timedelta(minutes=minutes)
    rows: List[Dict[str, object]] = []
    for item in list(demo_state.history):
        ts = item["normalized"]["ts"]
        if ts >= cutoff and item["normalized"]["air_node_id"] == air_node_id:
            rows.append(
                {
                    "ts": ts,
                    "air_rh_pct": item["normalized"]["air_rh_pct"],
                    "idx_mold_now": item["features"]["idx_mold_now"],
                    "pred_idx_mold_h": item["prediction"]["yhat"],
                }
            )
    return {"rows": rows}


def _write_latest_json(endpoint: str, payload: Dict[str, Any], response: Dict[str, Any] | None = None) -> None:
    latest_json_path.parent.mkdir(parents=True, exist_ok=True)
    blob = {
        "saved_ts": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "payload": payload,
        "response": response,
    }
    latest_json_path.write_text(json.dumps(blob, indent=2, default=str))


def _update_live_nodes(section: str, payload: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
    with _live_nodes_lock:
        now = datetime.now(timezone.utc).isoformat()
        _live_nodes_state["saved_ts"] = now
        _live_nodes_state["last_endpoint"] = endpoint
        _live_nodes_state["live_sensor_data"][section] = {
            "ts": now,
            "payload": payload,
        }
        live_nodes_json_path.parent.mkdir(parents=True, exist_ok=True)
        live_nodes_json_path.write_text(json.dumps(_live_nodes_state, indent=2, default=str))
        return _live_nodes_state


@router.get("/health")
def health():
    return {
        "status": "ok",
        "server_ts": datetime.now(timezone.utc),
        "nodes_seen": len(state.nodes),
        "history_rows": len(state.history),
    }


@router.get("/telemetry/live")
def telemetry_live():
    with _live_nodes_lock:
        return _live_nodes_state


@router.post("/telemetry", response_model=schemas.IngestResponse)
def ingest_telemetry(payload: schemas.TelemetryIn):
    result = run_pipeline(payload.dict(), state, forecast_cfg, alert_cfg)
    _write_latest_json("/telemetry", payload.dict(), result)
    # Do not overwrite live sensor stream with EMULATED demo data
    if payload.data_source != schemas.DataSourceEnum.EMULATED and payload.air_node_id != "SIM-001":
        _update_live_nodes(
            "air",
            {
                "air_temp_c": payload.air_temp_c,
                "air_rh_pct": payload.air_rh_pct,
                "air_surface_temp_c": payload.air_surface_temp_c,
                "air_voc_index": payload.air_voc_index,
            },
            "/telemetry",
        )
        _update_live_nodes(
            "water",
            {
                "water_temp_c": payload.water_temp_c,
                "water_turbidity_ntu": payload.water_turbidity_ntu,
                "water_tds_ppm": payload.water_tds_ppm,
                "water_free_chlorine_mgL": payload.water_free_chlorine_mgL,
            },
            "/telemetry",
        )
    return result


@router.get("/latest")
def latest(air_node_id: str = ""):
    if not state.latest_response:
        return {"status": "empty"}
    if air_node_id:
        node_latest = state.get_latest_for_node(air_node_id)
        return node_latest or {"status": "empty"}
    return state.latest_response


@router.get("/history")
def history(
    air_node_id: str = Query(default="air_01"),
    minutes: int = Query(default=30, ge=1, le=43200),
):
    if not state.history:
        return {"rows": []}
    latest_ts = state.history[-1]["normalized"]["ts"]
    cutoff = latest_ts - timedelta(minutes=minutes)
    rows: List[Dict[str, object]] = []
    for item in list(state.history):
        ts = item["normalized"]["ts"]
        if ts >= cutoff and item["normalized"]["air_node_id"] == air_node_id:
            rows.append(
                {
                    "ts": ts,
                    "scenario": item["normalized"].get("scenario"),
                    "episode_id": item["normalized"].get("episode_id"),
                    "air_temp_c": item["normalized"].get("air_temp_c"),
                    "air_rh_pct": item["normalized"]["air_rh_pct"],
                    "air_surface_temp_c": item["normalized"].get("air_surface_temp_c"),
                    "air_co2_ppm": item["normalized"].get("air_co2_ppm"),
                    "air_voc_index": item["normalized"].get("air_voc_index"),
                    "air_pm25_ugm3": item["normalized"].get("air_pm25_ugm3"),
                    "air_tvoc": item["normalized"].get("air_tvoc"),
                    "air_material_moisture": item["normalized"].get("air_material_moisture"),
                    "outdoor_temp_c": item["normalized"].get("outdoor_temp_c"),
                    "outdoor_rh_pct": item["normalized"].get("outdoor_rh_pct"),
                    "outdoor_dew_point_c": item["normalized"].get("outdoor_dew_point_c"),
                    "tod_sin": item["normalized"].get("tod_sin"),
                    "tod_cos": item["normalized"].get("tod_cos"),
                    "dow_sin": item["normalized"].get("dow_sin"),
                    "dow_cos": item["normalized"].get("dow_cos"),
                    "water_temp_c": item["normalized"].get("water_temp_c"),
                    "water_turbidity_ntu": item["normalized"].get("water_turbidity_ntu"),
                    "water_tds_ppm": item["normalized"].get("water_tds_ppm"),
                    "water_free_chlorine_mgL": item["normalized"].get("water_free_chlorine_mgL"),
                    "dew_point_c": item["features"].get("dew_point_c"),
                    "dew_margin_c": item["features"].get("dew_margin_c"),
                    "rh_mean_w": item["features"].get("rh_mean_w"),
                    "rh_std_w": item["features"].get("rh_std_w"),
                    "rh_slope_w": item["features"].get("rh_slope_w"),
                    "temp_slope_w": item["features"].get("temp_slope_w"),
                    "dew_point_slope_w": item["features"].get("dew_point_slope_w"),
                    "dew_margin_slope_w": item["features"].get("dew_margin_slope_w"),
                    "rh_time_above_70_w": item["features"].get("rh_time_above_70_w"),
                    "dew_margin_time_below_0_w": item["features"].get("dew_margin_time_below_0_w"),
                    "idx_mold_now": item["features"]["idx_mold_now"],
                    "idx_water_event_now": item["features"].get("idx_water_event_now"),
                    "pred_idx_mold_h": item["prediction"]["yhat"],
                    "prediction_model": item["prediction"].get("model_name"),
                }
            )
    return {"rows": rows}
