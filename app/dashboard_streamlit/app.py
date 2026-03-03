import os
import time

import pandas as pd
import requests
import streamlit as st
import altair as alt

API_URL = os.getenv("API_URL", "http://localhost:8000")
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "0.8"))

st.set_page_config(page_title="Smart Campus Demo", layout="wide")
st.title("Smart Campus Demo Dashboard")

st.sidebar.header("Refresh")
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
refresh_sec = st.sidebar.slider("Refresh interval (sec)", 1, 10, 2)


def fetch_latest(air_node_id: str = "") -> dict:
    try:
        url = f"{API_URL}/latest"
        if air_node_id:
            url = f"{API_URL}/latest?air_node_id={air_node_id}"
        return requests.get(url, timeout=3).json()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def fetch_history(air_node_id: str) -> dict:
    try:
        return requests.get(
            f"{API_URL}/history?air_node_id={air_node_id}&minutes=60",
            timeout=3,
        ).json()
    except Exception as exc:
        return {"rows": [], "error": str(exc)}


latest = fetch_latest()

def render_view(title: str, air_node_id: str) -> None:
    st.subheader(title)
    latest_local = fetch_latest(air_node_id)
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
    top_a.metric("RH %", f"{latest_local['normalized']['air_rh_pct']:.1f}")
    top_b.metric("Dew Margin C", f"{latest_local['features']['dew_margin_c']:.2f}")
    top_c.metric("Mold Risk Now", f"{idx_now:.3f}")
    horizon = latest_local["prediction"]["horizon_min"]
    top_d.metric(f"Predicted +{horizon}m", f"{pred:.3f}")
    top_e.metric("Health Score", f"{latest_local['health']['score']:.2f}")

    meta_a, meta_b, meta_c = st.columns(3)
    meta_a.caption(f"Scenario: {latest_local['normalized']['scenario']}")
    meta_b.caption(f"Model: {latest_local['prediction']['model_name']}")
    meta_c.caption(f"Updated: {latest_local['normalized']['ts']}")

    history = fetch_history(air_node_id)
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


tab_live, tab_demo = st.tabs(["Live Sensors", "Controlled Demo"])
with tab_live:
    if latest.get("status") in ("empty", "error"):
        st.info("Waiting for live sensor data...")
    else:
        live_id = latest["normalized"]["air_node_id"]
        render_view("Live Sensor Stream", live_id)

with tab_demo:
    render_view("Controlled Mold Episode (SIM-001)", "SIM-001")

st.caption("Run demo stream: `python scripts/run_demo.py --sequence NORMAL:60,MOLD_EPISODE:120 --model lgbm`")

if auto_refresh:
    time.sleep(float(refresh_sec))
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()
