import math


def clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))


def dew_point_c(air_temp_c: float, air_rh_pct: float) -> float:
    # Magnus formula
    a = 17.62
    b = 243.12
    rh = max(1e-6, min(100.0, air_rh_pct))
    gamma = (a * air_temp_c) / (b + air_temp_c) + math.log(rh / 100.0)
    return (b * gamma) / (a - gamma)
