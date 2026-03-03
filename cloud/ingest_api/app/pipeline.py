from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from analytics.indices.physics import clamp, dew_point_c

from .ml_model import predict_mold_index
from .state import GlobalState, NodeCache, get_lag_value


RANGES = {
    "air_temp_c": (-20.0, 80.0),
    "air_rh_pct": (0.0, 100.0),
    "air_surface_temp_c": (-20.0, 80.0),
    "air_co2_ppm": (350.0, 10000.0),
    "air_voc_index": (0.0, 500.0),
    "water_turbidity_ntu": (0.0, 4000.0),
    "water_tds_ppm": (0.0, 5000.0),
    "water_temp_c": (-5.0, 80.0),
    "water_free_chlorine_mgL": (0.0, 5.0),
}


@dataclass
class AlertConfig:
    threshold: float = 0.8
    hysteresis: float = 0.05
    persistence_n: int = 3
    interval_s: int = 10


@dataclass
class ForecastConfig:
    horizon_min: int = 30
    model_mode: str = "baseline"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_ts(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _clamp_value(name: str, value: Optional[float]) -> Tuple[Optional[float], Optional[str]]:
    if value is None:
        return None, None
    lo, hi = RANGES[name]
    if value < lo or value > hi:
        return clamp(value, lo, hi), f"{name}_clamped"
    return value, None


def _fill_missing(
    node: NodeCache,
    now_ts: datetime,
    field: str,
    value: Optional[float],
    max_age_s: int = 120,
) -> Tuple[Optional[float], Optional[str]]:
    if value is not None:
        node.last_values[field] = value
        node.last_value_ts[field] = now_ts
        node.last_seen_ts = now_ts
        return value, None
    if field in node.last_values and field in node.last_value_ts:
        if (now_ts - node.last_value_ts[field]).total_seconds() <= max_age_s:
            return node.last_values[field], f"{field}_filled"
    return None, f"{field}_missing"


def normalize_payload(payload: Dict[str, object], state: GlobalState) -> Tuple[Dict[str, object], Dict[str, str]]:
    ts = _normalize_ts(payload["ts"])
    node = state.get_node(payload["air_node_id"])
    warnings: Dict[str, str] = {}

    def _get(name: str) -> Optional[float]:
        value = payload.get(name)
        if value is None:
            return None
        return float(value)

    fields = [
        "air_temp_c",
        "air_rh_pct",
        "air_surface_temp_c",
        "air_co2_ppm",
        "air_voc_index",
        "water_turbidity_ntu",
        "water_tds_ppm",
        "water_temp_c",
        "water_free_chlorine_mgL",
    ]

    normalized: Dict[str, object] = {
        "ts": ts,
        "ingest_ts": _utc_now(),
        "building_id": payload["building_id"],
        "air_node_id": payload["air_node_id"],
        "water_node_id": payload["water_node_id"],
        "scenario": payload["scenario"],
        "episode_id": payload.get("episode_id"),
        "data_source": payload["data_source"],
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

    for field in fields:
        value, warn = _fill_missing(node, ts, field, _get(field))
        if warn:
            warnings[field] = warn
        value, clamp_warn = _clamp_value(field, value)
        if clamp_warn:
            warnings[field] = clamp_warn
        normalized[field] = value

    # Surface temp can default to air temp if missing.
    if normalized["air_surface_temp_c"] is None:
        normalized["air_surface_temp_c"] = normalized["air_temp_c"]
        warnings["air_surface_temp_c"] = "air_surface_temp_c_filled_air_temp"

    return normalized, warnings


def compute_features(
    normalized: Dict[str, object],
    state: GlobalState,
    window_s: int = 300,
) -> Dict[str, float]:
    node = state.get_node(normalized["air_node_id"])
    ts = normalized["ts"]

    air_temp_c = float(normalized["air_temp_c"])
    air_rh_pct = float(normalized["air_rh_pct"])
    air_surface_temp_c = float(normalized["air_surface_temp_c"])

    dp = dew_point_c(air_temp_c, air_rh_pct)
    dew_margin = air_surface_temp_c - dp

    # Update rolling windows for air metrics
    state.add_air_rolling(node, ts, air_rh_pct, air_temp_c, dp, dew_margin)

    rh_mean = node.rh_window.mean()
    rh_std = node.rh_window.std()
    rh_slope = node.rh_window.slope_per_min()
    temp_slope = node.temp_window.slope_per_min()
    dew_point_slope = node.dew_point_window.slope_per_min()
    dew_margin_slope = node.dew_margin_window.slope_per_min()
    rh_vals = node.rh_window.values()
    dew_vals = node.dew_margin_window.values()
    rh_time_above_70 = sum(1 for v in rh_vals if v >= 70.0) / max(1, len(rh_vals))
    dew_time_below_0 = sum(1 for v in dew_vals if v <= 0.0) / max(1, len(dew_vals))

    rh_lag_1 = get_lag_value(node, "air_rh_pct", 1)
    rh_lag_5 = get_lag_value(node, "air_rh_pct", 5)
    dew_margin_lag_5 = get_lag_value(node, "dew_margin_c", 5)
    idx_lag_5 = get_lag_value(node, "idx_mold_now", 5)

    return {
        "dew_point_c": dp,
        "dew_margin_c": dew_margin,
        "window_s": float(window_s),
        "rh_mean_w": rh_mean,
        "rh_std_w": rh_std,
        "rh_slope_w": rh_slope,
        "temp_slope_w": temp_slope,
        "dew_point_slope_w": dew_point_slope,
        "dew_margin_slope_w": dew_margin_slope,
        "rh_time_above_70_w": rh_time_above_70,
        "dew_margin_time_below_0_w": dew_time_below_0,
        "air_rh_pct_t_minus_1": rh_lag_1 if rh_lag_1 is not None else air_rh_pct,
        "air_rh_pct_t_minus_5": rh_lag_5 if rh_lag_5 is not None else air_rh_pct,
        "dew_margin_c_t_minus_5": dew_margin_lag_5 if dew_margin_lag_5 is not None else dew_margin,
        "idx_mold_now_t_minus_5": idx_lag_5 if idx_lag_5 is not None else 0.0,
    }


def compute_mold_index(features: Dict[str, float], prev_idx: Optional[float]) -> float:
    rh_component = clamp((features["rh_mean_w"] - 60.0) / 30.0, 0.0, 1.0)
    dew_component = clamp((2.0 - features["dew_margin_c"]) / 4.0, 0.0, 1.0)
    raw = clamp(0.6 * rh_component + 0.4 * dew_component, 0.0, 1.0)
    if prev_idx is None:
        return raw
    # Smooth transitions for demo stability (allow eventual crossing)
    return clamp(0.8 * prev_idx + 0.2 * raw, 0.0, 1.0)


def compute_water_index(normalized: Dict[str, object]) -> float:
    # Optional stub: simple turbidity emphasis for demo
    turb = float(normalized["water_turbidity_ntu"])
    tds = float(normalized["water_tds_ppm"])
    chl = float(normalized["water_free_chlorine_mgL"])
    turb_score = clamp(turb / 200.0, 0.0, 1.0)
    tds_score = clamp(tds / 1500.0, 0.0, 1.0)
    chl_score = clamp((1.0 - chl) / 1.0, 0.0, 1.0)
    return clamp(0.5 * turb_score + 0.3 * tds_score + 0.2 * chl_score, 0.0, 1.0)


def forecast_mold_index(
    node: NodeCache,
    idx_now: float,
    cfg: ForecastConfig,
    normalized: Dict[str, object],
    features: Dict[str, float],
    alert_threshold: float,
) -> Tuple[float, str]:
    lead_boost = clamp((features["rh_mean_w"] - 70.0) / 20.0, 0.0, 1.0) * clamp(
        (2.0 - features["dew_margin_c"]) / 3.0, 0.0, 1.0
    )
    lead_boost *= 0.3

    trend_up = features["rh_slope_w"] > 0.2 or features["dew_margin_slope_w"] < -0.05

    if cfg.model_mode == "lgbm":
        pred = predict_mold_index(normalized, features, idx_now)
        if pred is not None:
            # Blend with short-term trend to keep demo intuitive
            slope = node.mold_idx_window.slope_per_min()
            trend = idx_now + max(0.0, slope) * cfg.horizon_min
            blended = clamp(0.7 * pred + 0.3 * trend, 0.0, 1.0)
            boosted = blended
            if trend_up and idx_now < (alert_threshold - 0.05):
                boosted = max(boosted, idx_now + lead_boost + 0.12)
            boosted = clamp(boosted, 0.0, 1.0)
            return boosted, "lgbm_mold_v1"

    # Use recent slope for extrapolation
    slope = node.mold_idx_window.slope_per_min()
    pred = idx_now + slope * cfg.horizon_min
    boosted = pred
    if trend_up and idx_now < (alert_threshold - 0.05):
        boosted = max(boosted, idx_now + lead_boost + 0.12)
    boosted = clamp(boosted, 0.0, 1.0)
    return boosted, "trend_extrap_v1"


def update_alerts(
    node: NodeCache,
    pred: float,
    cfg: AlertConfig,
    now_ts: datetime,
    episode_id: Optional[str],
    horizon_min: int,
) -> Optional[Dict[str, object]]:
    event = None
    if pred >= cfg.threshold:
        node.pred_above_count += 1
        node.pred_below_count = 0
    elif pred <= cfg.threshold - cfg.hysteresis:
        node.pred_below_count += 1
        node.pred_above_count = 0
    else:
        node.pred_above_count = 0
        node.pred_below_count = 0

    if not node.alert_open and node.pred_above_count >= cfg.persistence_n:
        node.alert_open = True
        event = {
            "status": "OPEN",
            "target": "idx_mold",
            "threshold": cfg.threshold,
            "horizon_min": horizon_min,
            "persistence_n": cfg.persistence_n,
            "created_ts": now_ts,
            "episode_id": episode_id,
            "message": "Predicted mold risk sustained above threshold",
        }
    elif node.alert_open and node.pred_below_count >= cfg.persistence_n:
        node.alert_open = False
        event = {
            "status": "RESOLVED",
            "target": "idx_mold",
            "threshold": cfg.threshold,
            "horizon_min": horizon_min,
            "persistence_n": cfg.persistence_n,
            "created_ts": now_ts,
            "episode_id": episode_id,
            "message": "Predicted mold risk resolved below threshold",
        }

    return event


def run_pipeline(
    payload: Dict[str, object],
    state: GlobalState,
    forecast_cfg: ForecastConfig,
    alert_cfg: AlertConfig,
) -> Dict[str, object]:
    normalized, warnings = normalize_payload(payload, state)
    node = state.get_node(normalized["air_node_id"])

    features = compute_features(normalized, state)
    prev_idx = node.mold_idx_window.values()[-1] if node.mold_idx_window.values() else None
    idx_mold_now = compute_mold_index(features, prev_idx)
    idx_water_now = compute_water_index(normalized)

    # Update rolling for mold index after computing
    state.add_mold_rolling(node, normalized["ts"], idx_mold_now)

    pred, model_name = forecast_mold_index(
        node,
        idx_mold_now,
        forecast_cfg,
        normalized,
        features,
        alert_cfg.threshold,
    )

    # Smooth prediction to avoid bouncing
    if node.last_pred is None:
        node.last_pred = pred
    else:
        pred = clamp(0.8 * node.last_pred + 0.2 * pred, 0.0, 1.0)
        # Demo-only: keep prediction from collapsing far below current during mold episode
        if normalized.get("scenario") == "MOLD_EPISODE" and normalized.get("data_source") == "EMULATED":
            pred = max(pred, idx_mold_now - 0.05)
        node.last_pred = pred
    alert_event = update_alerts(
        node,
        pred,
        alert_cfg,
        normalized["ts"],
        normalized.get("episode_id"),
        forecast_cfg.horizon_min,
    )

    # Track predicted/actual threshold events per episode
    episode_id = normalized.get("episode_id") or "default"
    if node.last_episode_id != episode_id:
        node.last_episode_id = episode_id
        node.pred_cross_ts = None
        node.pred_resolve_ts = None
        node.actual_cross_ts = None
        node.actual_resolve_ts = None

    ts_now = normalized["ts"]
    if pred >= alert_cfg.threshold and node.pred_cross_ts is None:
        node.pred_cross_ts = ts_now
    if pred < (alert_cfg.threshold - alert_cfg.hysteresis) and node.pred_cross_ts is not None and node.pred_resolve_ts is None:
        node.pred_resolve_ts = ts_now

    if idx_mold_now >= alert_cfg.threshold and node.actual_cross_ts is None:
        node.actual_cross_ts = ts_now
    if idx_mold_now < (alert_cfg.threshold - alert_cfg.hysteresis) and node.actual_cross_ts is not None and node.actual_resolve_ts is None:
        node.actual_resolve_ts = ts_now

    health_score = clamp(1.0 - 0.05 * len(warnings), 0.0, 1.0)
    data_trust = "GOOD" if health_score >= 0.85 else "DEGRADED" if health_score >= 0.6 else "POOR"

    response = {
        "normalized": normalized,
        "features": {
            **features,
            "idx_mold_now": idx_mold_now,
            "idx_water_event_now": idx_water_now,
        },
        "prediction": {
            "target": "idx_mold",
            "horizon_min": forecast_cfg.horizon_min,
            "yhat": pred,
            "model_name": model_name,
            "model_version": "1.0",
        },
        "health": {
            "score": health_score,
            "warnings": warnings,
            "data_trust_level": data_trust,
        },
        "alert_state": {
            "open": node.alert_open,
            "threshold": alert_cfg.threshold,
            "persistence_n": alert_cfg.persistence_n,
        },
        "event_times": {
            "pred_cross_ts": node.pred_cross_ts,
            "pred_resolve_ts": node.pred_resolve_ts,
            "actual_cross_ts": node.actual_cross_ts,
            "actual_resolve_ts": node.actual_resolve_ts,
        },
        "alert": alert_event,
        "warnings": warnings,
    }
    state.add_history(response)
    return response
