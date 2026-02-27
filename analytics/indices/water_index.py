from typing import List, Tuple

from .physics import clamp


def water_event_index(
    turbidity_ntu: float,
    free_chlorine_mgL: float,
    conductivity_uScm: float,
    history: List[Tuple[float, float, float]],
) -> float:
    # history: list of (turbidity, free_chlorine, conductivity)
    if not history:
        history = [(turbidity_ntu, free_chlorine_mgL, conductivity_uScm)]

    turb_vals = [t for t, _, _ in history]
    chl_vals = [c for _, c, _ in history]
    cond_vals = [c for _, _, c in history]

    turb_mean = sum(turb_vals) / len(turb_vals)
    cond_mean = sum(cond_vals) / len(cond_vals)

    turb_anom = max(0.0, turbidity_ntu - turb_mean)
    turb_score = clamp(turb_anom / max(1.0, turb_mean + 5.0))

    chl_score = clamp((1.0 - free_chlorine_mgL) / 1.0)

    cond_shift = abs(conductivity_uScm - cond_mean)
    cond_score = clamp(cond_shift / max(50.0, cond_mean * 0.3))

    risk = 0.5 * turb_score + 0.3 * chl_score + 0.2 * cond_score
    return clamp(risk)
