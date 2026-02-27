from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from .db import Base


class RawTelemetry(Base):
    __tablename__ = "raw_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, index=True, nullable=False)
    building_id = Column(String, index=True, nullable=False)
    air_node_id = Column(String, index=True, nullable=False)
    water_node_id = Column(String, index=True, nullable=False)

    air_temp_c = Column(Float, nullable=False)
    air_rh_pct = Column(Float, nullable=False)
    water_temp_c = Column(Float, nullable=False)
    water_turbidity_ntu = Column(Float, nullable=False)
    water_free_chlorine_mgL = Column(Float, nullable=False)
    water_ph = Column(Float, nullable=False)
    water_conductivity_uScm = Column(Float, nullable=False)
    water_pressure_kpa = Column(Float, nullable=False)

    air_co2_ppm = Column(Float, nullable=True)
    air_pm25_ugm3 = Column(Float, nullable=True)
    air_tvoc = Column(Float, nullable=True)
    air_surface_temp_c = Column(Float, nullable=True)
    air_material_moisture = Column(Float, nullable=True)

    scenario = Column(String, index=True, nullable=False)
    data_source = Column(String, index=True, nullable=False)


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, index=True, nullable=False)
    air_node_id = Column(String, index=True, nullable=False)
    water_node_id = Column(String, index=True, nullable=False)

    qc_flags_json = Column(Text, nullable=False)
    sensor_health_score = Column(Float, nullable=False)

    idx_mold_now = Column(Float, nullable=False)
    idx_water_event_now = Column(Float, nullable=False)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, index=True, nullable=False)
    ts_target = Column(DateTime, index=True, nullable=False)
    air_node_id = Column(String, index=True, nullable=False)

    horizon_min = Column(Integer, nullable=False)
    pred_idx_mold_h = Column(Float, nullable=False)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime, index=True, nullable=False)
    air_node_id = Column(String, index=True, nullable=False)
    severity = Column(String, nullable=False)
    message = Column(String, nullable=False)
    reason_codes_json = Column(Text, nullable=False)
