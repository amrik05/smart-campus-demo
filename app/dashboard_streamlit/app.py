import os
import time

import pandas as pd
import requests
import streamlit as st
import altair as alt
from collections import deque
from analytics.indices.physics import dew_point_c
from analytics.indices.mold_index import mold_risk_index
from analytics.indices.water_index import water_event_index
import math

API_URL = os.getenv("API_URL", "http://localhost:8000")
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "0.8"))

st.set_page_config(page_title="Smart Campus Demo", layout="wide")
st.title("Smart Campus Maintenance Overview")

st.sidebar.header("Refresh")
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
refresh_sec = st.sidebar.slider("Refresh interval (sec)", 1, 5, 1)


def fetch_latest(air_node_id: str = "", base: str = "") -> dict:
    try:
        root = base or API_URL
        url = f"{root}/latest"
        if air_node_id:
            url = f"{root}/latest?air_node_id={air_node_id}"
        return requests.get(url, timeout=3).json()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def fetch_history(air_node_id: str, base: str = "") -> dict:
    try:
        root = base or API_URL
        return requests.get(
            f"{root}/history?air_node_id={air_node_id}&minutes=60",
            timeout=3,
        ).json()
    except Exception as exc:
        return {"rows": [], "error": str(exc)}


def fetch_live_nodes() -> dict:
    try:
        return requests.get(f"{API_URL}/telemetry/live", timeout=3).json()
    except Exception as exc:
        return {"live_sensor_data": {"air": None, "water": None}, "error": str(exc)}


latest = fetch_latest()

def render_view(title: str, air_node_id: str, base: str = "") -> None:
    st.subheader(title)
    latest_local = fetch_latest(air_node_id, base=base)
    if latest_local.get("status") == "empty":
        st.info("No data yet for this stream.")
        return
    if latest_local.get("status") == "error":
        st.error(f"API error: {latest_local.get('error')}")
        return

    alert_state = latest_local.get("alert_state") or {}
    idx_now = latest_local["features"]["idx_mold_now"]
    pred = latest_local["prediction"]["yhat"]
    alert_open = alert_state.get("open") or idx_now >= ALERT_THRESHOLD or pred >= ALERT_THRESHOLD
    banner_text = "ALERT OPEN: Predicted mold risk above threshold" if alert_open else "System nominal"
    banner_color = "#B00020" if alert_open else "#0B6E4F"
    st.markdown(
        f"""
        <div style="
            position: sticky;
            top: 0;
            z-index: 999;
            padding: 10px 14px;
            border-radius: 6px;
            color: white;
            background: {banner_color};
            font-weight: 600;
        ">
            {banner_text}
        </div>
        """,
        unsafe_allow_html=True,
    )

    top_a, top_b, top_c, top_d, top_e = st.columns(5)
    rh_val = latest_local["normalized"]["air_rh_pct"]
    dew_margin = latest_local["features"]["dew_margin_c"]
    top_a.metric("RH %", f"{rh_val:.1f}")
    top_b.metric("Dew Margin C", f"{dew_margin:.2f}")
    top_c.metric("Mold Risk (Now)", f"{idx_now:.3f}")
    horizon = latest_local["prediction"]["horizon_min"]
    top_d.metric(f"Predicted +{horizon}m", f"{pred:.3f}")
    top_e.metric("Health Score", f"{latest_local['health']['score']:.2f}")

    meta_a, meta_b, meta_c = st.columns(3)
    meta_a.caption(f"Scenario: {latest_local['normalized']['scenario']}")
    meta_b.caption(f"Model: {latest_local['prediction']['model_name']}")
    meta_c.caption(f"Updated: {latest_local['normalized']['ts']}")

    history = fetch_history(air_node_id, base=base)
    plot_df = pd.DataFrame(history.get("rows", []))
    st.markdown("**Live Trends**")
    if plot_df.empty:
        st.info("Waiting for data stream...")
    else:
        plot_df["ts"] = pd.to_datetime(plot_df["ts"])
        plot_df = plot_df.set_index("ts")
        plot_df["threshold"] = ALERT_THRESHOLD

        risk_df = plot_df.reset_index()[["ts", "idx_mold_now", "pred_idx_mold_h", "threshold"]]
        risk_long = risk_df.melt("ts", var_name="series", value_name="value")
        color_scale = alt.Scale(
            domain=["idx_mold_now", "pred_idx_mold_h", "threshold"],
            range=["#1f77b4", "#ff7f0e", "#d62728"],
        )
        risk_chart = (
            alt.Chart(risk_long)
            .mark_line()
            .encode(
                x="ts:T",
                y=alt.Y("value:Q", scale=alt.Scale(domain=[0, 1])),
                color=alt.Color("series:N", scale=color_scale),
            )
            .properties(height=280)
        )
        st.altair_chart(risk_chart, use_container_width=True)

        rh_df = plot_df.reset_index()[["ts", "air_rh_pct"]]
        rh_chart = (
            alt.Chart(rh_df)
            .mark_line(color="#2ca02c")
            .encode(x="ts:T", y=alt.Y("air_rh_pct:Q", scale=alt.Scale(domain=[0, 100])))
            .properties(height=200)
        )
        st.altair_chart(rh_chart, use_container_width=True)

        if len(plot_df) >= 3:
            tail = plot_df.tail(5)
            dt_min = max(0.1, (tail.index[-1] - tail.index[0]).total_seconds() / 60.0)
            slope = (tail["pred_idx_mold_h"].iloc[-1] - tail["pred_idx_mold_h"].iloc[0]) / dt_min
            eta_min = None
            last = plot_df.iloc[-1]
            if last["pred_idx_mold_h"] >= ALERT_THRESHOLD:
                eta_min = 0.0
            elif slope > 1e-6:
                eta_min = (ALERT_THRESHOLD - last["pred_idx_mold_h"]) / slope
            eta_label = f"{eta_min:.1f} min" if eta_min is not None else "n/a"
            st.caption(f"ETA to predicted threshold ({ALERT_THRESHOLD:.2f}): {eta_label}")

            gauge_left, gauge_right = st.columns([1, 2])
            with gauge_left:
                st.metric("ETA to Alert", eta_label)
            with gauge_right:
                progress = min(1.0, max(0.0, last["pred_idx_mold_h"] / ALERT_THRESHOLD))
                st.progress(progress, text=f"Predicted risk vs threshold ({last['pred_idx_mold_h']:.2f} / {ALERT_THRESHOLD:.2f})")
        else:
            st.caption("ETA to predicted threshold: n/a")

    st.divider()

    left, right = st.columns([2, 1])
    with left:
        st.subheader("Telemetry Snapshot")
        st.dataframe(pd.DataFrame([latest_local["normalized"]]), use_container_width=True)
    with right:
        st.subheader("Health Flags")
        if latest_local.get("warnings"):
            st.json(latest_local["warnings"], expanded=False)
        else:
            st.success("All sensors nominal")
        st.caption(f"Data trust: {latest_local['health'].get('data_trust_level')}")

        st.subheader("Event Times")
        events = latest_local.get("event_times", {})
        st.write(f"Pred cross: {events.get('pred_cross_ts')}")
        st.write(f"Pred resolve: {events.get('pred_resolve_ts')}")
        st.write(f"Actual cross: {events.get('actual_cross_ts')}")
        st.write(f"Actual resolve: {events.get('actual_resolve_ts')}")


tab_mold, tab_air, tab_water = st.tabs(["Mold Risk Demo", "Live Air", "Live Water"])

with tab_mold:
    st.subheader("Predictive Mold Risk")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Start 1‑min Demo (30‑min lead)"):
            try:
                requests.post(
                    f"{API_URL}/demo/start",
                    params={"sequence": "NORMAL:10,MOLD_EPISODE:50", "rate_sec": 1.0, "speed": 120.0},
                )
            except Exception:
                pass
    with col_b:
        if st.button("Start 4‑min Demo"):
            try:
                requests.post(
                    f"{API_URL}/demo/start",
                    params={"sequence": "NORMAL:60,MOLD_EPISODE:180", "rate_sec": 1.0, "speed": 60.0},
                )
            except Exception:
                pass
    with col_c:
        if st.button("Stop Demo"):
            try:
                requests.post(f"{API_URL}/demo/stop")
            except Exception:
                pass
    render_view("Demo Stream (SIM-001)", "SIM-001", base=f"{API_URL}/demo")
    st.caption("Synthetic stream designed to show predictive alerts ahead of risk.")

with tab_air:
    live = fetch_live_nodes()
    if live.get("error"):
        st.error(f"API error: {live.get('error')}")
    air = (live.get("live_sensor_data") or {}).get("air")
    if not air:
        st.info("Waiting for live air sensor data...")
    else:
        payload = air.get("payload", {})
        ts = air.get("ts")
        st.subheader("Air Quality (Live)")
        st.caption(f"Last update: {ts}")

        if "air_series" not in st.session_state:
            st.session_state.air_series = deque(maxlen=300)
        st.session_state.air_series.append(
            {
                "ts": pd.to_datetime(ts),
                "Temp (C)": payload.get("air_temp_c"),
                "Humidity (%)": payload.get("air_rh_pct"),
                "VOC (raw)": payload.get("air_voc_raw"),
            }
        )

        df = pd.DataFrame(list(st.session_state.air_series))
        if not df.empty:
            df = df.set_index("ts")
            metric_cols = st.columns(3)
            metric_cols[0].metric("Temp (C)", f"{payload.get('air_temp_c', 0):.2f}")
            metric_cols[1].metric("Humidity (%)", f"{payload.get('air_rh_pct', 0):.2f}")
            metric_cols[2].metric("VOC (raw)", f"{payload.get('air_voc_raw', 0):.0f}")

            # Compute mold risk from rolling history
            hist = [(row["Temp (C)"], row["Humidity (%)"]) for _, row in df.iterrows()]
            idx_mold = mold_risk_index(
                payload.get("air_temp_c", 0),
                payload.get("air_rh_pct", 0),
                hist[-60:],
            )
            dp = dew_point_c(payload.get("air_temp_c", 0), payload.get("air_rh_pct", 0))
            dew_margin = payload.get("air_temp_c", 0) - dp
            risk_cols = st.columns(3)
            risk_cols[0].metric("Mold Risk (Now)", f"{idx_mold:.2f}")
            risk_cols[1].metric("Dew Point (C)", f"{dp:.2f}")
            risk_cols[2].metric("Dew Margin (C)", f"{dew_margin:.2f}")
            if idx_mold >= ALERT_THRESHOLD:
                st.error("Mold risk above threshold")

            # Risk trend
            df_risk = df.copy()
            df_risk["Mold Risk"] = [
                mold_risk_index(row["Temp (C)"], row["Humidity (%)"], hist[max(0, i - 60) : i + 1])
                for i, (_, row) in enumerate(df.iterrows())
            ]
            # Scale chart to recent range for readability
            risk_chart = (
                alt.Chart(df_risk.reset_index())
                .mark_line(color="#B00020")
                .encode(
                    x="ts:T",
                    y=alt.Y("Mold Risk:Q", scale=alt.Scale(domain=[0, 1])),
                )
                .properties(height=120)
            )
            st.altair_chart(risk_chart, use_container_width=True)

            st.markdown("**Trends (last 5 min)**")
            t_min = df["Temp (C)"].min()
            t_max = df["Temp (C)"].max()
            t_pad = max(0.5, (t_max - t_min) * 0.1)
            h_min = df["Humidity (%)"].min()
            h_max = df["Humidity (%)"].max()
            h_pad = max(1.0, (h_max - h_min) * 0.1)

            air_chart = (
                alt.Chart(df.reset_index())
                .transform_fold(["Temp (C)", "Humidity (%)"], as_=["metric", "value"])
                .mark_line()
                .encode(
                    x="ts:T",
                    y=alt.Y(
                        "value:Q",
                        scale=alt.Scale(domain=[min(t_min - t_pad, h_min - h_pad), max(t_max + t_pad, h_max + h_pad)]),
                    ),
                    color="metric:N",
                )
                .properties(height=140)
            )
            st.altair_chart(air_chart, use_container_width=True)

            voc_chart = (
                alt.Chart(df.reset_index())
                .mark_line(color="#ff7f0e")
                .encode(x="ts:T", y=alt.Y("VOC (raw):Q"))
                .properties(height=100)
            )
            st.altair_chart(voc_chart, use_container_width=True)
        st.markdown("**Latest Reading**")
        st.json(payload, expanded=False)

with tab_water:
    live = fetch_live_nodes()
    if live.get("error"):
        st.error(f"API error: {live.get('error')}")
    water = (live.get("live_sensor_data") or {}).get("water")
    if not water:
        st.info("Waiting for live water sensor data...")
    else:
        payload = water.get("payload", {})
        ts = water.get("ts")
        st.subheader("Water Quality (Live)")
        st.caption(f"Last update: {ts}")

        if "water_series" not in st.session_state:
            st.session_state.water_series = deque(maxlen=300)
        st.session_state.water_series.append(
            {
                "ts": pd.to_datetime(ts),
                "Surface Temp (C)": payload.get("surface_temp_c"),
                "Turbidity (raw)": payload.get("turbidity_raw"),
                "TDS (raw)": payload.get("tds_raw"),
                "Turbidity (V)": payload.get("turbidity_v"),
                "TDS (V)": payload.get("tds_v"),
            }
        )

        df = pd.DataFrame(list(st.session_state.water_series))
        if not df.empty:
            df = df.set_index("ts")
            metric_cols = st.columns(3)
            metric_cols[0].metric("Surface Temp (C)", f"{payload.get('surface_temp_c', 0):.2f}")
            metric_cols[1].metric("Turbidity (raw)", f"{payload.get('turbidity_raw', 0):.0f}")
            metric_cols[2].metric("TDS (raw)", f"{payload.get('tds_raw', 0):.0f}")

            dial_cols = st.columns(3)
            # Temperature dial (circular gauge)
            temp_val = float(payload.get("surface_temp_c", 0) or 0.0)
            temp_min, temp_max = 10.0, 40.0
            temp_norm = max(0.0, min(1.0, (temp_val - temp_min) / (temp_max - temp_min)))
            dial_data = pd.DataFrame(
                [
                    {"label": "Temp", "value": temp_norm, "color": "Temp"},
                    {"label": "Temp", "value": 1.0 - temp_norm, "color": "Remaining"},
                ]
            )
            dial = (
                alt.Chart(dial_data)
                .mark_arc(innerRadius=45, outerRadius=70)
                .encode(
                    theta=alt.Theta("value:Q", stack=True),
                    color=alt.Color(
                        "color:N",
                        scale=alt.Scale(domain=["Temp", "Remaining"], range=["#1f77b4", "#e0e0e0"]),
                        legend=None,
                    ),
                )
                .properties(width=160, height=160)
            )
            with dial_cols[0]:
                st.metric("Water Temp (C)", f"{temp_val:.1f}")
                st.altair_chart(dial, use_container_width=False)

            # Turbidity dial (0-3000)
            turb_val = float(payload.get("turbidity_raw", 0) or 0.0)
            turb_norm = max(0.0, min(1.0, turb_val / 3000.0))
            turb_data = pd.DataFrame(
                [
                    {"label": "Turbidity", "value": turb_norm, "color": "Turbidity"},
                    {"label": "Turbidity", "value": 1.0 - turb_norm, "color": "Remaining"},
                ]
            )
            turb_dial = (
                alt.Chart(turb_data)
                .mark_arc(innerRadius=45, outerRadius=70)
                .encode(
                    theta=alt.Theta("value:Q", stack=True),
                    color=alt.Color(
                        "color:N",
                        scale=alt.Scale(domain=["Turbidity", "Remaining"], range=["#ff7f0e", "#e0e0e0"]),
                        legend=None,
                    ),
                )
                .properties(width=160, height=160)
            )
            with dial_cols[1]:
                st.metric("Turbidity (raw)", f"{turb_val:.0f}")
                st.altair_chart(turb_dial, use_container_width=False)

            # TDS dial (0-3000)
            tds_val = float(payload.get("tds_raw", 0) or 0.0)
            tds_norm = max(0.0, min(1.0, tds_val / 3000.0))
            tds_data = pd.DataFrame(
                [
                    {"label": "TDS", "value": tds_norm, "color": "TDS"},
                    {"label": "TDS", "value": 1.0 - tds_norm, "color": "Remaining"},
                ]
            )
            tds_dial = (
                alt.Chart(tds_data)
                .mark_arc(innerRadius=45, outerRadius=70)
                .encode(
                    theta=alt.Theta("value:Q", stack=True),
                    color=alt.Color(
                        "color:N",
                        scale=alt.Scale(domain=["TDS", "Remaining"], range=["#9467bd", "#e0e0e0"]),
                        legend=None,
                    ),
                )
                .properties(width=160, height=160)
            )
            with dial_cols[2]:
                st.metric("TDS (raw)", f"{tds_val:.0f}")
                st.altair_chart(tds_dial, use_container_width=False)

            # Demo logic: turbidity_raw >= 2700 = clean water, < 2700 = risk after 3s
            turb_raw = float(payload.get("turbidity_raw", 0) or 0)
            now_ts = pd.to_datetime(ts)
            if "water_risk_start" not in st.session_state:
                st.session_state.water_risk_start = None
            if "water_clear_start" not in st.session_state:
                st.session_state.water_clear_start = None
            if turb_raw < 2700:
                if st.session_state.water_risk_start is None:
                    st.session_state.water_risk_start = now_ts
                st.session_state.water_clear_start = None
            else:
                if st.session_state.water_clear_start is None:
                    st.session_state.water_clear_start = now_ts

            risk_active = False
            if st.session_state.water_risk_start is not None:
                if (now_ts - st.session_state.water_risk_start).total_seconds() >= 1.5:
                    risk_active = True
            if st.session_state.water_clear_start is not None:
                if (now_ts - st.session_state.water_clear_start).total_seconds() >= 3.0:
                    st.session_state.water_risk_start = None
                    risk_active = False

            # Use risk score only (no separate turbidity alert)

            # Normalize raw values to demo-friendly units
            turb_v = payload.get("turbidity_v", 0.0) or 0.0
            tds_v = payload.get("tds_v", 0.0) or 0.0
            turb_ntu = max(0.0, (turb_v - 0.1) * 500.0)  # demo scaling
            tds_ppm = max(0.0, tds_v * 1000.0)

            # Water risk: ratio-based vs clean baseline (coffee -> higher risk)
            TURB_BASELINE = 2650.0
            TDS_BASELINE = 1000.0
            turb_ratio = TURB_BASELINE / max(1.0, float(payload.get("turbidity_raw", 0) or 1.0))
            tds_ratio = float(payload.get("tds_raw", 0) or 0.0) / TDS_BASELINE
            # Aggressive scaling for demo: small drops in turbidity + 2x TDS -> high risk
            turb_score = max(0.0, min(1.0, (turb_ratio - 1.0) / 0.10))  # 10% drop -> high
            tds_score = max(0.0, min(1.0, (tds_ratio - 1.0) / 0.50))    # 1.5x -> high
            base_risk = max(0.0, min(1.0, 0.7 * turb_score + 0.3 * tds_score))
            idx_water = max(0.0, min(1.0, 0.85 * base_risk + 0.05))
            risk_cols = st.columns(2)
            risk_cols[0].metric("Water Risk (Now)", f"{idx_water:.2f}")
            risk_cols[1].metric("Sensor Temp (C)", f"{payload.get('surface_temp_c', 0):.2f}")
            if idx_water >= 0.6:
                st.error("Water risk elevated")

            # Risk trend (rolling)
            df_risk = df.copy()
            water_risk_vals = []
            for _, row in df_risk.iterrows():
                t_raw = float(row["Turbidity (raw)"] or 1.0)
                d_raw = float(row["TDS (raw)"] or 0.0)
                t_ratio = TURB_BASELINE / max(1.0, t_raw)
                d_ratio = d_raw / TDS_BASELINE
                t_score = max(0.0, min(1.0, (t_ratio - 1.0) / 0.10))
                d_score = max(0.0, min(1.0, (d_ratio - 1.0) / 0.50))
                base_risk = max(0.0, min(1.0, 0.7 * t_score + 0.3 * d_score))
                water_risk_vals.append(max(0.0, min(1.0, 0.85 * base_risk + 0.05)))
            df_risk["Water Risk"] = water_risk_vals
            risk_chart = (
                alt.Chart(df_risk.reset_index())
                .mark_line(color="#B00020")
                .encode(x="ts:T", y=alt.Y("Water Risk:Q", scale=alt.Scale(domain=[0, 1])))
                .properties(height=120)
            )
            st.altair_chart(risk_chart, use_container_width=True)

            st.markdown("**Trends (last 5 min)**")
            # Zoom charts to recent range
            temp_min = df["Surface Temp (C)"].min()
            temp_max = df["Surface Temp (C)"].max()
            temp_pad = max(0.5, (temp_max - temp_min) * 0.1)
            temp_chart = (
                alt.Chart(df.reset_index())
                .mark_line(color="#1f77b4")
                .encode(
                    x="ts:T",
                    y=alt.Y("Surface Temp (C):Q", scale=alt.Scale(domain=[temp_min - temp_pad, temp_max + temp_pad])),
                )
                .properties(height=120)
            )
            st.altair_chart(temp_chart, use_container_width=True)

            y_min = min(df["Turbidity (raw)"].min(), df["TDS (raw)"].min())
            y_max = max(df["Turbidity (raw)"].max(), df["TDS (raw)"].max())
            y_pad = max(50.0, (y_max - y_min) * 0.3)
            turb_chart = (
                alt.Chart(df.reset_index())
                .transform_fold(["Turbidity (raw)", "TDS (raw)"], as_=["metric", "value"])
                .mark_line()
                .encode(
                    x="ts:T",
                    y=alt.Y("value:Q", scale=alt.Scale(domain=[y_min - y_pad, y_max + y_pad])),
                    color="metric:N",
                )
                .properties(height=160)
            )
            st.altair_chart(turb_chart, use_container_width=True)

            v_min = min(df["Turbidity (V)"].min(), df["TDS (V)"].min())
            v_max = max(df["Turbidity (V)"].max(), df["TDS (V)"].max())
            v_pad = max(0.1, (v_max - v_min) * 0.3)
            volt_chart = (
                alt.Chart(df.reset_index())
                .transform_fold(["Turbidity (V)", "TDS (V)"], as_=["metric", "value"])
                .mark_line()
                .encode(
                    x="ts:T",
                    y=alt.Y("value:Q", scale=alt.Scale(domain=[v_min - v_pad, v_max + v_pad])),
                    color="metric:N",
                )
                .properties(height=120)
            )
            st.altair_chart(volt_chart, use_container_width=True)
            # Distributions
            st.markdown("**Distributions (last 5 min)**")
            hist_df = df.reset_index()
            turb_hist = (
                alt.Chart(hist_df)
                .mark_bar(opacity=0.6, color="#1f77b4")
                .encode(x=alt.X("Turbidity (raw):Q", bin=True), y="count()")
                .properties(height=100)
            )
            tds_hist = (
                alt.Chart(hist_df)
                .mark_bar(opacity=0.6, color="#ff7f0e")
                .encode(x=alt.X("TDS (raw):Q", bin=True), y="count()")
                .properties(height=100)
            )
            st.altair_chart(turb_hist, use_container_width=True)
            st.altair_chart(tds_hist, use_container_width=True)
        st.markdown("**Latest Reading**")
        st.json(payload, expanded=False)

if auto_refresh:
    time.sleep(float(refresh_sec))
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()
