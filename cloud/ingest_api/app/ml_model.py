from __future__ import annotations

import os
from typing import Dict, List, Optional

from analytics.indices.physics import clamp

try:
    import lightgbm as lgb
except Exception:
    lgb = None  # type: ignore


_MODEL = None


def _episode_id_to_num(episode_id: Optional[str]) -> float:
    if not episode_id:
        return 0.0
    return float(abs(hash(episode_id)) % 1000)


def load_model(model_path: str) -> Optional["lgb.Booster"]:
    if lgb is None:
        return None
    if not os.path.exists(model_path):
        return None
    return lgb.Booster(model_file=model_path)


def get_model() -> Optional["lgb.Booster"]:
    global _MODEL
    if _MODEL is None:
        model_path = os.getenv("MODEL_PATH", "models/mold_lgbm.txt")
        _MODEL = load_model(model_path)
    return _MODEL


def build_feature_vector(
    model: "lgb.Booster",
    normalized: Dict[str, object],
    features: Dict[str, float],
    idx_mold_now: float,
) -> List[float]:
    # Map current schema to model feature names
    values = {
        "air_temp_c": float(normalized["air_temp_c"]),
        "air_rh_pct": float(normalized["air_rh_pct"]),
        "air_co2_ppm": float(normalized.get("air_co2_ppm") or 600.0),
        "air_pm25_ugm3": 8.0,
        "air_tvoc": float(normalized.get("air_voc_index") or 150.0) * 1.0,
        "air_surface_temp_c": float(normalized["air_surface_temp_c"]),
        "air_material_moisture": 0.08 + (float(normalized["air_rh_pct"]) - 45.0) / 500.0,
        "dew_point_c": float(features["dew_point_c"]),
        "dew_margin_c": float(features["dew_margin_c"]),
        "idx_mold_now": float(idx_mold_now),
        "rh_mean_w": float(features["rh_mean_w"]),
        "rh_std_w": float(features["rh_std_w"]),
        "rh_slope_w": float(features["rh_slope_w"]),
        "temp_slope_w": float(features["temp_slope_w"]),
        "dew_point_slope_w": float(features["dew_point_slope_w"]),
        "dew_margin_slope_w": float(features["dew_margin_slope_w"]),
        "rh_time_above_70_w": float(features["rh_time_above_70_w"]),
        "dew_margin_time_below_0_w": float(features["dew_margin_time_below_0_w"]),
        "air_rh_pct_t_minus_1": float(features["air_rh_pct_t_minus_1"]),
        "air_rh_pct_t_minus_5": float(features["air_rh_pct_t_minus_5"]),
        "dew_margin_c_t_minus_5": float(features["dew_margin_c_t_minus_5"]),
        "idx_mold_now_t_minus_5": float(features["idx_mold_now_t_minus_5"]),
        "outdoor_temp_c": float(normalized.get("outdoor_temp_c") or 10.0),
        "outdoor_rh_pct": float(normalized.get("outdoor_rh_pct") or 60.0),
        "outdoor_dew_point_c": float(normalized.get("outdoor_dew_point_c") or 5.0),
        "tod_sin": float(normalized.get("tod_sin") or 0.0),
        "tod_cos": float(normalized.get("tod_cos") or 1.0),
        "dow_sin": float(normalized.get("dow_sin") or 0.0),
        "dow_cos": float(normalized.get("dow_cos") or 1.0),
        "episode_id": _episode_id_to_num(normalized.get("episode_id")),
    }

    order = model.feature_name()
    return [float(values.get(name, 0.0)) for name in order]


def predict_mold_index(
    normalized: Dict[str, object],
    features: Dict[str, float],
    idx_mold_now: float,
) -> Optional[float]:
    model = get_model()
    if model is None:
        return None
    vec = build_feature_vector(model, normalized, features, idx_mold_now)
    pred = float(model.predict([vec])[0])
    return clamp(pred, 0.0, 1.0)
