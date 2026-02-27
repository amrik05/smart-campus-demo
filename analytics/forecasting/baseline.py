from analytics.indices.physics import clamp


def forecast_mold_index(
    idx_now: float,
    idx_prev: float,
    dt_minutes: float,
    horizon_minutes: float,
    persistence: float = 0.8,
) -> float:
    if dt_minutes <= 0:
        dt_minutes = 1.0
    slope = (idx_now - idx_prev) / dt_minutes
    pred = idx_now + slope * horizon_minutes * 0.5 + (idx_now * persistence - idx_prev * (1 - persistence)) * 0.1
    return clamp(pred)
