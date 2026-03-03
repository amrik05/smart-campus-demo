from datetime import timedelta
from typing import Dict, List

from fastapi import APIRouter, Query

from . import schemas
import os

from .pipeline import AlertConfig, ForecastConfig, run_pipeline
from .state import GlobalState

router = APIRouter()
state = GlobalState()

forecast_cfg = ForecastConfig(
    horizon_min=int(os.getenv("FORECAST_HORIZON_MIN", "30")),
    model_mode=os.getenv("MODEL_MODE", "baseline"),
)
alert_cfg = AlertConfig(threshold=0.8, hysteresis=0.05, persistence_n=3, interval_s=10)


@router.post("/telemetry", response_model=schemas.IngestResponse)
def ingest_telemetry(payload: schemas.TelemetryIn):
    result = run_pipeline(payload.dict(), state, forecast_cfg, alert_cfg)
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
    minutes: int = Query(default=30, ge=1, le=360),
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
                    "air_rh_pct": item["normalized"]["air_rh_pct"],
                    "idx_mold_now": item["features"]["idx_mold_now"],
                    "pred_idx_mold_h": item["prediction"]["yhat"],
                }
            )
    return {"rows": rows}
