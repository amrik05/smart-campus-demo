from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel


class ScenarioEnum(str, Enum):
    NORMAL = "NORMAL"
    MOLD_EPISODE = "MOLD_EPISODE"
    WATER_EVENT = "WATER_EVENT"


class DataSourceEnum(str, Enum):
    LIVE = "LIVE"
    EMULATED = "EMULATED"


class TelemetryIn(BaseModel):
    ts: datetime
    building_id: str
    air_node_id: str
    water_node_id: str

    air_temp_c: float
    air_rh_pct: float
    air_surface_temp_c: Optional[float] = None
    air_co2_ppm: Optional[float] = None
    air_pm25_ugm3: Optional[float] = None
    air_tvoc: Optional[float] = None
    air_voc_index: Optional[float] = None
    air_material_moisture: Optional[float] = None

    water_turbidity_ntu: float
    water_tds_ppm: float
    water_temp_c: float
    water_free_chlorine_mgL: float

    scenario: ScenarioEnum
    episode_id: Optional[str] = None
    data_source: DataSourceEnum

    seq_water: Optional[int] = None
    rssi_ble: Optional[int] = None
    battery_mv: Optional[int] = None
    flags: Optional[int] = None

    site_id: Optional[str] = None
    building_zone: Optional[str] = None
    outdoor_temp_c: Optional[float] = None
    outdoor_rh_pct: Optional[float] = None
    outdoor_dew_point_c: Optional[float] = None
    tod_sin: Optional[float] = None
    tod_cos: Optional[float] = None
    dow_sin: Optional[float] = None
    dow_cos: Optional[float] = None


class AirTelemetryIn(BaseModel):
    ts: datetime
    building_id: str
    air_node_id: str
    water_node_id: Optional[str] = "WATER-UNKNOWN"

    air_temp_c: float
    air_rh_pct: float
    air_surface_temp_c: Optional[float] = None
    air_co2_ppm: Optional[float] = None
    air_pm25_ugm3: Optional[float] = None
    air_tvoc: Optional[float] = None
    air_voc_index: Optional[float] = None
    air_voc_raw: Optional[int] = None
    air_material_moisture: Optional[float] = None

    scenario: ScenarioEnum = ScenarioEnum.NORMAL
    episode_id: Optional[str] = None
    data_source: DataSourceEnum = DataSourceEnum.LIVE

    rssi_ble: Optional[int] = None
    battery_mv: Optional[int] = None
    flags: Optional[int] = None

    site_id: Optional[str] = None
    building_zone: Optional[str] = None
    outdoor_temp_c: Optional[float] = None
    outdoor_rh_pct: Optional[float] = None
    outdoor_dew_point_c: Optional[float] = None
    tod_sin: Optional[float] = None
    tod_cos: Optional[float] = None
    dow_sin: Optional[float] = None
    dow_cos: Optional[float] = None


class AirSensorRawIn(BaseModel):
    air_temp_c: float
    air_rh_pct: float
    air_voc_raw: int


class WaterSensorRawIn(BaseModel):
    surface_temp_c: float
    turbidity_raw: int
    tds_raw: int
    turbidity_v: float
    tds_v: float


class NormalizedOut(BaseModel):
    ts: datetime
    ingest_ts: datetime
    building_id: str
    air_node_id: str
    water_node_id: str
    scenario: ScenarioEnum
    episode_id: Optional[str]
    data_source: DataSourceEnum
    seq_water: Optional[int]
    rssi_ble: Optional[int]
    battery_mv: Optional[int]
    flags: Optional[int]
    site_id: Optional[str]
    building_zone: Optional[str]
    outdoor_temp_c: Optional[float]
    outdoor_rh_pct: Optional[float]
    outdoor_dew_point_c: Optional[float]
    tod_sin: Optional[float]
    tod_cos: Optional[float]
    dow_sin: Optional[float]
    dow_cos: Optional[float]

    air_temp_c: float
    air_rh_pct: float
    air_surface_temp_c: float
    air_co2_ppm: Optional[float]
    air_pm25_ugm3: Optional[float]
    air_tvoc: Optional[float]
    air_voc_index: Optional[float]
    air_material_moisture: Optional[float]

    water_turbidity_ntu: float
    water_tds_ppm: float
    water_temp_c: float
    water_free_chlorine_mgL: float


class FeaturesOut(BaseModel):
    dew_point_c: float
    dew_margin_c: float
    window_s: float
    rh_mean_w: float
    rh_std_w: float
    rh_slope_w: float
    temp_slope_w: float
    dew_point_slope_w: float
    dew_margin_slope_w: float
    rh_time_above_70_w: float
    dew_margin_time_below_0_w: float
    air_rh_pct_t_minus_1: float
    air_rh_pct_t_minus_5: float
    dew_margin_c_t_minus_5: float
    idx_mold_now_t_minus_5: float
    idx_mold_now: float
    idx_water_event_now: float


class PredictionOut(BaseModel):
    target: str
    horizon_min: int
    yhat: float
    model_name: str
    model_version: str


class AlertOut(BaseModel):
    status: str
    target: str
    threshold: float
    horizon_min: int
    persistence_n: int
    created_ts: datetime
    episode_id: Optional[str]
    message: str


class HealthOut(BaseModel):
    score: float
    warnings: Dict[str, str]
    data_trust_level: str


class AlertStateOut(BaseModel):
    open: bool
    threshold: float
    persistence_n: int


class EventTimesOut(BaseModel):
    pred_cross_ts: Optional[datetime]
    pred_resolve_ts: Optional[datetime]
    actual_cross_ts: Optional[datetime]
    actual_resolve_ts: Optional[datetime]


class IngestResponse(BaseModel):
    normalized: NormalizedOut
    features: FeaturesOut
    prediction: PredictionOut
    health: HealthOut
    alert_state: AlertStateOut
    event_times: EventTimesOut
    alert: Optional[AlertOut]
    warnings: Dict[str, str]
