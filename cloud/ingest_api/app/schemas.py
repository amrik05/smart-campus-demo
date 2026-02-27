from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ScenarioEnum(str, Enum):
    NORMAL = "NORMAL"
    MOLD_EPISODE = "MOLD_EPISODE"
    WATER_EVENT = "WATER_EVENT"
    SENSOR_FAULT = "SENSOR_FAULT"


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
    water_temp_c: float
    water_turbidity_ntu: float
    water_free_chlorine_mgL: float
    water_ph: float
    water_conductivity_uScm: float
    water_pressure_kpa: float

    scenario: ScenarioEnum
    data_source: DataSourceEnum

    air_co2_ppm: Optional[float] = None
    air_pm25_ugm3: Optional[float] = None
    air_tvoc: Optional[float] = None
    air_surface_temp_c: Optional[float] = None
    air_material_moisture: Optional[float] = None


class TelemetryOut(BaseModel):
    status: str = Field(default="ok")
    idx_mold_now: float
    pred_idx_mold_h: float
    idx_water_event_now: float
