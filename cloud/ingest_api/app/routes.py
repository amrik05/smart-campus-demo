import json
from datetime import timedelta
from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analytics.forecasting.baseline import forecast_mold_index
from analytics.indices.mold_index import mold_risk_index
from analytics.indices.water_index import water_event_index
from analytics.indices.physics import clamp

from . import models, schemas
from .db import SessionLocal
from .settings import settings

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _qc_flags(
    payload: schemas.TelemetryIn,
    history: List[models.RawTelemetry],
) -> Tuple[Dict[str, Dict[str, bool]], float]:
    flags = {"range": {}, "missing": {}, "flatline": {}}
    score = 1.0

    required_fields = [
        "air_temp_c",
        "air_rh_pct",
        "water_temp_c",
        "water_turbidity_ntu",
        "water_free_chlorine_mgL",
        "water_ph",
        "water_conductivity_uScm",
        "water_pressure_kpa",
    ]

    for field in required_fields:
        value = getattr(payload, field)
        flags["missing"][field] = value is None
        if value is None:
            score -= 0.1
            continue
        lo, hi = settings.qc_ranges[field]
        out_of_range = value < lo or value > hi
        flags["range"][field] = out_of_range
        if out_of_range:
            score -= 0.1

    window = settings.flatline_window
    if history and window > 2:
        recent = history[-(window - 1) :]
        for field in required_fields:
            values = [getattr(r, field) for r in recent] + [getattr(payload, field)]
            is_flat = max(values) - min(values) < 0.01
            flags["flatline"][field] = is_flat
            if is_flat:
                score -= 0.05
    else:
        for field in required_fields:
            flags["flatline"][field] = False

    score = clamp(score, 0.0, 1.0)
    return flags, score


def _get_history(
    db: Session,
    air_node_id: str,
    minutes: int,
) -> List[models.RawTelemetry]:
    # Get latest N minutes for the given air node
    latest = (
        db.query(models.RawTelemetry)
        .filter(models.RawTelemetry.air_node_id == air_node_id)
        .order_by(models.RawTelemetry.ts.desc())
        .first()
    )
    if not latest:
        return []
    start_ts = latest.ts - timedelta(minutes=minutes)
    rows = (
        db.query(models.RawTelemetry)
        .filter(models.RawTelemetry.air_node_id == air_node_id)
        .filter(models.RawTelemetry.ts >= start_ts)
        .order_by(models.RawTelemetry.ts.asc())
        .all()
    )
    return rows


def _extract_mold_history(rows: List[models.RawTelemetry]) -> List[Tuple[float, float]]:
    return [(r.air_temp_c, r.air_rh_pct) for r in rows]


def _extract_water_history(rows: List[models.RawTelemetry]) -> List[Tuple[float, float, float]]:
    return [(r.water_turbidity_ntu, r.water_free_chlorine_mgL, r.water_conductivity_uScm) for r in rows]


@router.post("/telemetry", response_model=schemas.TelemetryOut)
def ingest_telemetry(payload: schemas.TelemetryIn, db: Session = Depends(get_db)):
    raw = models.RawTelemetry(**payload.dict())
    db.add(raw)
    db.flush()

    history_60 = _get_history(db, payload.air_node_id, 60)
    history_120 = _get_history(db, payload.air_node_id, 120)

    qc_flags, health_score = _qc_flags(payload, history_60)

    mold_idx = mold_risk_index(
        payload.air_temp_c,
        payload.air_rh_pct,
        _extract_mold_history(history_60),
    )
    water_idx = water_event_index(
        payload.water_turbidity_ntu,
        payload.water_free_chlorine_mgL,
        payload.water_conductivity_uScm,
        _extract_water_history(history_120),
    )

    prev_feature = (
        db.query(models.Feature)
        .filter(models.Feature.air_node_id == payload.air_node_id)
        .order_by(models.Feature.ts.desc())
        .first()
    )
    if prev_feature:
        dt_min = max(1.0, (payload.ts - prev_feature.ts).total_seconds() / 60.0)
        pred = forecast_mold_index(mold_idx, prev_feature.idx_mold_now, dt_min, settings.forecast_horizon_minutes)
    else:
        pred = mold_idx

    feature = models.Feature(
        ts=payload.ts,
        air_node_id=payload.air_node_id,
        water_node_id=payload.water_node_id,
        qc_flags_json=json.dumps(qc_flags),
        sensor_health_score=health_score,
        idx_mold_now=mold_idx,
        idx_water_event_now=water_idx,
    )
    db.add(feature)

    pred_row = models.Prediction(
        ts=payload.ts,
        ts_target=payload.ts + timedelta(minutes=settings.forecast_horizon_minutes),
        air_node_id=payload.air_node_id,
        horizon_min=settings.forecast_horizon_minutes,
        pred_idx_mold_h=pred,
    )
    db.add(pred_row)

    # Alerting logic
    recent_preds = (
        db.query(models.Prediction)
        .filter(models.Prediction.air_node_id == payload.air_node_id)
        .order_by(models.Prediction.ts.desc())
        .limit(settings.alert_consecutive)
        .all()
    )
    if len(recent_preds) == settings.alert_consecutive:
        if all(p.pred_idx_mold_h > settings.alert_threshold for p in recent_preds):
            reason_codes = ["PRED_MOLD_THRESHOLD", f"CONSEC_{settings.alert_consecutive}"]
            alert = models.Alert(
                ts=payload.ts,
                air_node_id=payload.air_node_id,
                severity="MEDIUM",
                message="Predicted mold risk sustained above threshold",
                reason_codes_json=json.dumps(reason_codes),
            )
            db.add(alert)

    db.commit()

    return schemas.TelemetryOut(
        idx_mold_now=mold_idx,
        pred_idx_mold_h=pred,
        idx_water_event_now=water_idx,
    )
