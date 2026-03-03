import pytest

from cloud.ingest_api.app.schemas import TelemetryIn


def test_valid_payload():
    payload = {
        "ts": "2026-02-27T12:00:00Z",
        "building_id": "RUTGERS-ENG-1",
        "air_node_id": "AIR-001",
        "water_node_id": "WATER-001",
        "air_temp_c": 22.1,
        "air_rh_pct": 45.0,
        "water_temp_c": 18.5,
        "water_turbidity_ntu": 0.8,
        "water_free_chlorine_mgL": 1.2,
        "water_tds_ppm": 350.0,
        "scenario": "NORMAL",
        "data_source": "EMULATED",
    }
    model = TelemetryIn(**payload)
    assert model.air_node_id == "AIR-001"


def test_missing_field():
    payload = {
        "ts": "2026-02-27T12:00:00Z",
        "building_id": "RUTGERS-ENG-1",
        "air_node_id": "AIR-001",
        "water_node_id": "WATER-001",
        "air_temp_c": 22.1,
        "air_rh_pct": 45.0,
        "water_temp_c": 18.5,
        "water_turbidity_ntu": 0.8,
        "water_free_chlorine_mgL": 1.2,
        "water_tds_ppm": 350.0,
        "scenario": "NORMAL",
    }
    with pytest.raises(Exception):
        TelemetryIn(**payload)
