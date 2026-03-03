from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Tuple


@dataclass
class RollingWindow:
    window_s: int
    _points: Deque[Tuple[float, float]] = field(default_factory=deque)

    def add(self, ts_s: float, value: float) -> None:
        self._points.append((ts_s, value))
        self._trim(ts_s)

    def _trim(self, now_s: float) -> None:
        cutoff = now_s - self.window_s
        while self._points and self._points[0][0] < cutoff:
            self._points.popleft()

    def values(self) -> List[float]:
        return [v for _, v in self._points]

    def mean(self) -> float:
        vals = self.values()
        if not vals:
            return 0.0
        return sum(vals) / len(vals)

    def std(self) -> float:
        vals = self.values()
        if len(vals) < 2:
            return 0.0
        mu = sum(vals) / len(vals)
        var = sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)
        return var**0.5

    def slope_per_min(self) -> float:
        # Simple linear regression slope vs time (minutes).
        if len(self._points) < 2:
            return 0.0
        xs = [(t - self._points[0][0]) / 60.0 for t, _ in self._points]
        ys = [v for _, v in self._points]
        x_mean = sum(xs) / len(xs)
        y_mean = sum(ys) / len(ys)
        denom = sum((x - x_mean) ** 2 for x in xs)
        if denom <= 1e-9:
            return 0.0
        numer = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        return numer / denom
