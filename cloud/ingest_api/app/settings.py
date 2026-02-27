import os


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./data/smart_campus.db")
        self.forecast_horizon_minutes = int(os.getenv("FORECAST_HORIZON_MINUTES", "60"))
        self.alert_threshold = float(os.getenv("ALERT_THRESHOLD", "0.6"))
        self.alert_consecutive = int(os.getenv("ALERT_CONSECUTIVE", "3"))
        self.flatline_window = int(os.getenv("FLATLINE_WINDOW", "5"))
        self.qc_ranges = {
            "air_temp_c": (0.0, 50.0),
            "air_rh_pct": (0.0, 100.0),
            "water_temp_c": (0.0, 50.0),
            "water_turbidity_ntu": (0.0, 1000.0),
            "water_free_chlorine_mgL": (0.0, 5.0),
            "water_ph": (0.0, 14.0),
            "water_conductivity_uScm": (0.0, 5000.0),
            "water_pressure_kpa": (0.0, 1000.0),
        }


settings = Settings()
