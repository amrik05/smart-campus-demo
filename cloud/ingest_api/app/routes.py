from datetime import timedelta
from typing import Dict, List, Any

from fastapi import APIRouter, Query, HTTPException

from . import schemas
import os
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock

from .pipeline import AlertConfig, ForecastConfig, run_pipeline
from .state import GlobalState

router = APIRouter()
state = GlobalState()

forecast_cfg = ForecastConfig(
    horizon_min=int(os.getenv("FORECAST_HORIZON_MIN", "30")),
    model_mode=os.getenv("MODEL_MODE", "baseline"),
)
alert_cfg = AlertConfig(threshold=0.8, hysteresis=0.05, persistence_n=3, interval_s=10)
latest_json_path = Path(os.getenv("LATEST_JSON_PATH", "data/latest_telemetry.json"))
live_nodes_json_path = Path(os.getenv("LIVE_NODES_JSON_PATH", "data/latest_live_nodes.json"))
_live_nodes_lock = Lock()
_live_nodes_state: Dict[str, Any] = {
    "saved_ts": None,
    "live_sensor_data": {
        "air": None,
        "water": None,
    },
}


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


def _map_air_to_full_payload(payload: schemas.AirTelemetryIn) -> Dict[str, object]:
    # If only raw VOC is provided, map to index-style field for dashboard/model compatibility.
    air_voc_index = payload.air_voc_index
    if air_voc_index is None and payload.air_voc_raw is not None:
        air_voc_index = float(payload.air_voc_raw)

    return {
        "air_temp_c": payload.air_temp_c,
        "air_rh_pct": payload.air_rh_pct,
        "air_voc_index": air_voc_index
    }


@router.post("/telemetry/air", response_model=schemas.IngestResponse)
def ingest_air_telemetry(payload: Dict[str, Any]):
    # Flexible air endpoint:
    # accepts either full AirTelemetryIn payload or minimal raw sensor payload:
    # {"air_temp_c":..., "air_rh_pct":..., "air_voc_raw":...}
    if "air_temp_c" not in payload or "air_rh_pct" not in payload:
        raise HTTPException(
            status_code=422,
            detail="Expected at least: air_temp_c, air_rh_pct",
        )

    air_voc_index = payload.get("air_voc_index")
    if air_voc_index is None and payload.get("air_voc_raw") is not None:
        try:
            air_voc_index = float(payload["air_voc_raw"])
        except Exception:
            air_voc_index = None

    now_ts = datetime.now(timezone.utc)
    full_payload = {
        "ts": payload.get("ts", now_ts),
        "building_id": payload.get("building_id", "RUTGERS-ENG-1"),
        "air_node_id": payload.get("air_node_id", "LIVE-ESP32-001"),
        "water_node_id": payload.get("water_node_id", "WATER-UNKNOWN"),
        "air_temp_c": float(payload["air_temp_c"]),
        "air_rh_pct": float(payload["air_rh_pct"]),
        "air_surface_temp_c": payload.get("air_surface_temp_c"),
        "air_co2_ppm": payload.get("air_co2_ppm"),
        "air_pm25_ugm3": payload.get("air_pm25_ugm3"),
        "air_tvoc": payload.get("air_tvoc"),
        "air_voc_index": air_voc_index,
        "air_material_moisture": payload.get("air_material_moisture"),
        "water_turbidity_ntu": float(payload.get("water_turbidity_ntu", 0.8)),
        "water_tds_ppm": float(payload.get("water_tds_ppm", 350.0)),
        "water_temp_c": float(payload.get("water_temp_c", 18.5)),
        "water_free_chlorine_mgL": float(payload.get("water_free_chlorine_mgL", 1.0)),
        "scenario": payload.get("scenario", "NORMAL"),
        "episode_id": payload.get("episode_id"),
        "data_source": payload.get("data_source", "LIVE"),
        "seq_water": payload.get("seq_water"),
        "rssi_ble": payload.get("rssi_ble"),
        "battery_mv": payload.get("battery_mv"),
        "flags": payload.get("flags"),
        "site_id": payload.get("site_id"),
        "building_zone": payload.get("building_zone"),
        "outdoor_temp_c": payload.get("outdoor_temp_c"),
        "outdoor_rh_pct": payload.get("outdoor_rh_pct"),
        "outdoor_dew_point_c": payload.get("outdoor_dew_point_c"),
        "tod_sin": payload.get("tod_sin"),
        "tod_cos": payload.get("tod_cos"),
        "dow_sin": payload.get("dow_sin"),
        "dow_cos": payload.get("dow_cos"),
    }
    result = run_pipeline(full_payload, state, forecast_cfg, alert_cfg)
    _write_latest_json("/telemetry/air", payload, result)
    _update_live_nodes("air", payload, "/telemetry/air")
    return result


@router.post("/telemetry/air/raw")
def ingest_air_raw(payload: schemas.AirSensorRawIn):
    out = {
        "status": "ok",
        "ingest_ts": datetime.now(timezone.utc),
        "sensor_data": payload.dict(),
    }
    _write_latest_json("/telemetry/air/raw", payload.dict(), out)
    live = _update_live_nodes("air", payload.dict(), "/telemetry/air/raw")
    out["live_sensor_data"] = live["live_sensor_data"]
    return out


@router.post("/telemetry/water/raw")
def ingest_water_raw(payload: schemas.WaterSensorRawIn):
    out = {
        "status": "ok",
        "ingest_ts": datetime.now(timezone.utc),
        "sensor_data": payload.dict(),
    }
    _write_latest_json("/telemetry/water/raw", payload.dict(), out)
    live = _update_live_nodes("water", payload.dict(), "/telemetry/water/raw")
    out["live_sensor_data"] = live["live_sensor_data"]
    return out


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
