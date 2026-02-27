from typing import List

from .rolling import rolling_mean


def build_rh_persistence(rh_values: List[float]) -> float:
    return rolling_mean(rh_values)
