from typing import List, Tuple

from .physics import clamp, dew_point_c


def mold_risk_index(
    air_temp_c: float,
    air_rh_pct: float,
    history: List[Tuple[float, float]],
) -> float:
    # history: list of (air_temp_c, air_rh_pct)
    if not history:
        history = [(air_temp_c, air_rh_pct)]

    rh_vals = [rh for _, rh in history]
    rh_mean = sum(rh_vals) / len(rh_vals)

    rh_persist = clamp((rh_mean - 60.0) / 40.0)

    dp = dew_point_c(air_temp_c, air_rh_pct)
    gap = air_temp_c - dp
    proximity = clamp((2.0 - gap) / 2.0)

    recovery = 0.0
    if air_rh_pct < 70.0 and rh_mean > 75.0:
        recovery = clamp((75.0 - air_rh_pct) / 20.0)

    risk = 0.55 * rh_persist + 0.35 * proximity - 0.2 * recovery
    return clamp(risk)
