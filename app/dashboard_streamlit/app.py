import os
from datetime import datetime

import pandas as pd
import sqlalchemy as sa
import streamlit as st

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/smart_campus.db")

engine = sa.create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})

st.set_page_config(page_title="Smart Campus Demo", layout="wide")

st.title("Smart Campus Demo Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Latest Telemetry")
    latest = pd.read_sql_query(
        "SELECT * FROM raw_telemetry ORDER BY ts DESC LIMIT 1",
        engine,
    )
    st.dataframe(latest, use_container_width=True)

with col2:
    st.subheader("Latest Indices")
    features = pd.read_sql_query(
        "SELECT * FROM features ORDER BY ts DESC LIMIT 1",
        engine,
    )
    st.dataframe(features, use_container_width=True)

with col3:
    st.subheader("Latest Prediction")
    preds = pd.read_sql_query(
        "SELECT * FROM predictions ORDER BY ts DESC LIMIT 1",
        engine,
    )
    st.dataframe(preds, use_container_width=True)

st.divider()

st.subheader("Mold Risk Over Time")
plot_df = pd.read_sql_query(
    """
    SELECT r.ts, r.air_rh_pct, f.idx_mold_now, p.pred_idx_mold_h
    FROM raw_telemetry r
    LEFT JOIN features f ON r.ts = f.ts
    LEFT JOIN predictions p ON r.ts = p.ts
    ORDER BY r.ts ASC
    LIMIT 500
    """,
    engine,
)

if not plot_df.empty:
    plot_df["ts"] = pd.to_datetime(plot_df["ts"])
    plot_df = plot_df.set_index("ts")
    st.line_chart(plot_df[["air_rh_pct", "idx_mold_now", "pred_idx_mold_h"]])

st.divider()

st.subheader("Alerts Feed")
alerts = pd.read_sql_query(
    "SELECT * FROM alerts ORDER BY ts DESC LIMIT 50",
    engine,
)
st.dataframe(alerts, use_container_width=True)

st.divider()

st.subheader("Controls")
st.caption("Use the synthetic generator CLI to switch scenarios or start/stop accelerated demo.")
st.code(
    "python -m analytics.synthetic.scenario_generator --api-url http://localhost:8000 --scenario MOLD_EPISODE --rate-sec 1",
    language="bash",
)
