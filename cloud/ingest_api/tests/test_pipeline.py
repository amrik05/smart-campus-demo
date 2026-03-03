from datetime import datetime, timezone

from analytics.indices.physics import dew_point_c

from cloud.ingest_api.app.pipeline import AlertConfig, ForecastConfig, forecast_mold_index, update_alerts
from cloud.ingest_api.app.rolling import RollingWindow
from cloud.ingest_api.app.state import NodeCache


def test_dew_point_basic():
    dp = dew_point_c(30.0, 70.0)
    assert 23.0 <= dp <= 25.0
    dp2 = dew_point_c(20.0, 50.0)
    assert 8.5 <= dp2 <= 10.5


def test_rolling_stats_slope():
    window = RollingWindow(window_s=300)
    window.add(0.0, 0.0)
    window.add(60.0, 10.0)
    window.add(120.0, 20.0)
    assert abs(window.mean() - 10.0) < 1e-6
    assert abs(window.slope_per_min() - 10.0) < 1e-6


def test_forecast_trend_increases():
    node = NodeCache()
    # Seed a positive slope: 0.2 -> 0.4 over 2 minutes
    node.mold_idx_window.add(0.0, 0.2)
    node.mold_idx_window.add(60.0, 0.3)
    node.mold_idx_window.add(120.0, 0.4)
    pred = forecast_mold_index(node, 0.4, ForecastConfig(horizon_min=30))
    assert pred > 0.4


def test_alert_persistence_open_and_resolve():
    node = NodeCache()
    cfg = AlertConfig(threshold=0.8, hysteresis=0.05, persistence_n=3, interval_s=10)
    now = datetime.now(timezone.utc)

    # Trigger open
    event = None
    for _ in range(3):
        event = update_alerts(node, 0.9, cfg, now, "ep-1", 30)
    assert node.alert_open is True
    assert event is not None and event["status"] == "OPEN"

    # Trigger resolve
    event = None
    for _ in range(3):
        event = update_alerts(node, 0.6, cfg, now, "ep-1", 30)
    assert node.alert_open is False
    assert event is not None and event["status"] == "RESOLVED"
