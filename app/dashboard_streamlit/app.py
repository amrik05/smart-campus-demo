import os
import time
from datetime import datetime, timedelta

import pandas as pd
import sqlalchemy as sa
import streamlit as st

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/smart_campus.db")

engine = sa.create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})

st.set_page_config(page_title="Smart Campus Demo", layout="wide")

st.title("Smart Campus Demo Dashboard")

tab_live, tab_ml = st.tabs(["Live Pipeline", "ML Demo"])

with tab_live:
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

with tab_ml:
    st.subheader("ML Demo: Mold Forecasting (Predictive Maintenance)")
    st.caption("This view replays a trained model's predictions from synthetic episodes.")

    eval_path = "/home/amrik/code/smart-campus/data/mold_eval.csv"
    metrics_path = "/home/amrik/code/smart-campus/data/mold_metrics.json"

    if not os.path.exists(eval_path):
        st.warning("Run ./scripts/train_mold_demo.sh to generate ML demo outputs.")
        st.stop()

    df = pd.read_csv(eval_path, parse_dates=["ts"])
    scenarios = sorted(df["scenario"].unique().tolist())

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        scenario = st.selectbox("Scenario", scenarios, index=0)
    with col_b:
        window_minutes = st.slider("Window (minutes)", 60, 360, 300, step=30)
    with col_c:
        speed = st.slider("Playback speed (x)", 1, 10, 5)

    threshold = st.slider("Alert threshold", 0.4, 0.9, 0.6, step=0.05)

    if "demo_running" not in st.session_state:
        st.session_state.demo_running = False
    if "demo_idx" not in st.session_state:
        st.session_state.demo_idx = 0

    start_col, stop_col, reset_col = st.columns(3)
    with start_col:
        if st.button("Start"):
            st.session_state.demo_running = True
    with stop_col:
        if st.button("Stop"):
            st.session_state.demo_running = False
    with reset_col:
        if st.button("Reset"):
            st.session_state.demo_idx = 0

    def _rerun() -> None:
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

    if st.session_state.demo_running:
        time.sleep(1.0 / max(1, speed))
        _rerun()

    scenario_df = df[df["scenario"] == scenario].sort_values("ts").reset_index(drop=True)
    if scenario_df.empty:
        st.warning("No data for selected scenario.")
        st.stop()

    # Advance pointer
    st.session_state.demo_idx = min(st.session_state.demo_idx + (1 if st.session_state.demo_running else 0), len(scenario_df) - 1)

    current_ts = scenario_df.loc[st.session_state.demo_idx, "ts"]
    window_start = current_ts - timedelta(minutes=window_minutes)
    window_df = scenario_df[scenario_df["ts"] >= window_start]

    # Predictive maintenance cards
    latest_row = window_df.iloc[-1]
    latest_pred = latest_row["pred_idx_mold_h"]
    latest_actual = latest_row["target_idx_mold_h"]

    # Lead time estimate: first predicted vs actual threshold crossing within episode
    pred_cross = scenario_df[scenario_df["pred_idx_mold_h"] >= threshold]
    actual_cross = scenario_df[scenario_df["target_idx_mold_h"] >= threshold]
    if not pred_cross.empty and not actual_cross.empty:
        lead_min = (actual_cross.iloc[0]["ts"] - pred_cross.iloc[0]["ts"]).total_seconds() / 60.0
    else:
        lead_min = 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Latest Predicted Risk", f"{latest_pred:.2f}")
    c2.metric("Latest Actual Risk", f"{latest_actual:.2f}")
    c3.metric("Lead Time (min)", f"{lead_min:.1f}")

    st.divider()

    chart_df = window_df.set_index("ts")[["target_idx_mold_h", "pred_idx_mold_h"]]
    st.line_chart(chart_df)
    st.caption(f"Threshold = {threshold:.2f} | Window ending at {current_ts}")

    if os.path.exists(metrics_path):
        st.subheader("Model Metrics")
        with open(metrics_path, "r", encoding="utf-8") as f:
            st.json(f.read(), expanded=False)
