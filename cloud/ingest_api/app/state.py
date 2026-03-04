from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, Optional, Tuple

from collections import deque

from .rolling import RollingWindow


def _utc_ts_s(ts: datetime) -> float:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.timestamp()


@dataclass
class NodeCache:
    last_seen_ts: Optional[datetime] = None
    last_values: Dict[str, float] = field(default_factory=dict)
    last_value_ts: Dict[str, datetime] = field(default_factory=dict)

    rh_window: RollingWindow = field(default_factory=lambda: RollingWindow(window_s=300))
    temp_window: RollingWindow = field(default_factory=lambda: RollingWindow(window_s=300))
    dew_point_window: RollingWindow = field(default_factory=lambda: RollingWindow(window_s=300))
    dew_margin_window: RollingWindow = field(default_factory=lambda: RollingWindow(window_s=300))
    mold_idx_window: RollingWindow = field(default_factory=lambda: RollingWindow(window_s=300))
    lag_buffers: Dict[str, Deque[Tuple[float, float]]] = field(default_factory=dict)

    pred_above_count: int = 0
    pred_below_count: int = 0
    alert_open: bool = False
    last_pred: Optional[float] = None
    last_episode_id: Optional[str] = None
    pred_cross_ts: Optional[datetime] = None
    pred_resolve_ts: Optional[datetime] = None
    actual_cross_ts: Optional[datetime] = None
    actual_resolve_ts: Optional[datetime] = None


@dataclass
class GlobalState:
    nodes: Dict[str, NodeCache] = field(default_factory=dict)
    latest_response: Optional[dict] = None
    history: Deque[dict] = field(default_factory=lambda: deque(maxlen=2000))
    latest_air_raw: Optional[dict] = None
    latest_water_raw: Optional[dict] = None
    latest_live_path: Optional[str] = None

    def get_node(self, air_node_id: str) -> NodeCache:
        if air_node_id not in self.nodes:
            self.nodes[air_node_id] = NodeCache()
        return self.nodes[air_node_id]

    def add_history(self, payload: dict) -> None:
        self.latest_response = payload
        self.history.append(payload)
        if self.latest_live_path:
            try:
                import json
                from pathlib import Path

                Path(self.latest_live_path).parent.mkdir(parents=True, exist_ok=True)
                Path(self.latest_live_path).write_text(json.dumps(payload, default=str, indent=2))
            except Exception:
                pass

    def get_latest_for_node(self, air_node_id: str) -> Optional[dict]:
        if not self.history:
            return None
        for item in reversed(self.history):
            if item["normalized"]["air_node_id"] == air_node_id:
                return item
        return None

    def add_air_rolling(
        self,
        node: NodeCache,
        ts: datetime,
        air_rh_pct: float,
        air_temp_c: float,
        dew_point_c: float,
        dew_margin_c: float,
    ) -> None:
        ts_s = _utc_ts_s(ts)
        node.rh_window.add(ts_s, air_rh_pct)
        node.temp_window.add(ts_s, air_temp_c)
        node.dew_point_window.add(ts_s, dew_point_c)
        node.dew_margin_window.add(ts_s, dew_margin_c)
        _add_lag(node, "air_rh_pct", ts_s, air_rh_pct)
        _add_lag(node, "air_temp_c", ts_s, air_temp_c)
        _add_lag(node, "dew_margin_c", ts_s, dew_margin_c)

    def add_mold_rolling(self, node: NodeCache, ts: datetime, idx_mold_now: float) -> None:
        ts_s = _utc_ts_s(ts)
        node.mold_idx_window.add(ts_s, idx_mold_now)
        _add_lag(node, "idx_mold_now", ts_s, idx_mold_now)


def _add_lag(node: NodeCache, key: str, ts_s: float, value: float) -> None:
    if key not in node.lag_buffers:
        node.lag_buffers[key] = deque(maxlen=800)
    node.lag_buffers[key].append((ts_s, value))


def get_lag_value(node: NodeCache, key: str, lag_min: int) -> Optional[float]:
    if key not in node.lag_buffers:
        return None
    buf = node.lag_buffers[key]
    if not buf:
        return None
    target = buf[-1][0] - lag_min * 60.0
    # Find closest value at or before target
    for ts_s, val in reversed(buf):
        if ts_s <= target:
            return val
    return None
