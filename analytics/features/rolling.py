from typing import List


def rolling_mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def rolling_slope(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return values[-1] - values[0]
