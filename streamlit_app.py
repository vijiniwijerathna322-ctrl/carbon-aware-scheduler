"""Local dashboard for the existing Carbon Scheduler HTTP API."""

import os
from datetime import timedelta

import httpx
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Carbon Scheduler", page_icon="🌿", layout="wide")
st.title("Carbon Scheduler")
st.caption("Explore grid forecasts. Find a lower-carbon window for flexible work.")
st.warning(
    "Research demo · Historical demo timestamps are not live forecasts. "
    "Carbon intervals missed coverage validation; savings use an average generation proxy."
)

with st.sidebar:
    st.header("Connection")
    api_url = st.text_input("FastAPI URL", os.getenv("CARBON_API_URL", "http://127.0.0.1:8000"))
    st.button("Refresh data")
    st.caption("Start the API in demo mode first. No EIA key is needed for the frozen demo.")
    st.link_button("API reference", api_url.rstrip("/") + "/docs")


def request(path: str, payload: dict | None = None) -> tuple[int, dict]:
    """Requests stay server-side; credentials and local environment are never displayed."""
    try:
        with httpx.Client(base_url=api_url.rstrip("/"), timeout=60) as client:
            response = client.get(path) if payload is None else client.post(path, json=payload)
        return response.status_code, response.json()
    except (httpx.HTTPError, ValueError):
        st.error("Cannot read the API. Check that the backend is running and the URL is correct.")
        st.stop()


status, health = request("/healthz")
if status != httpx.codes.OK:
    st.error(f"API unavailable: {health.get('reason', 'check backend logs')}")
    st.stop()

status, forecast = request("/v1/forecast?horizon=48")
if status != httpx.codes.OK:
    st.error("Forecast unavailable. Check the backend's data and model configuration.")
    st.stop()

points = pd.DataFrame(forecast["points"])
points["target_time"] = pd.to_datetime(points.target_time, utc=True)
first = points.target_time.iloc[0]
region = forecast["region"]
left, middle, right = st.columns(3)
left.metric("Served region", region)
middle.metric(
    "Forecast issued (UTC)", pd.Timestamp(forecast["issue_time"]).strftime("%b %d, %H:%M")
)
right.metric("Data as of (UTC)", pd.Timestamp(forecast["data_as_of"]).strftime("%b %d, %H:%M"))

forecast_tab, schedule_tab, monitor_tab = st.tabs(["Forecasts", "Plan a job", "Monitoring"])
with forecast_tab:
    st.subheader("Grid outlook")
    target = st.selectbox("Target", ["Carbon intensity", "Demand"])
    horizon = st.slider("Hours ahead", min_value=1, max_value=48, value=24)
    selected = forecast
    if target == "Demand":
        code, selected = request("/v1/forecast?target=demand_mwh&horizon=48")
        if code != httpx.codes.OK:
            st.error("Demand forecast unavailable.")
            st.stop()
    frame = pd.DataFrame(selected["points"]).iloc[:horizon].copy()
    frame["target_time"] = pd.to_datetime(frame.target_time, utc=True)
    units = "gCO2e/kWh" if target == "Carbon intensity" else "MWh"
    st.line_chart(
        frame.set_index("target_time")[["lower", "median", "upper"]],
        x_label="Target time (UTC)",
        y_label=units,
    )
    st.caption("Nominal 80% pointwise interval endpoints; actual coverage can differ under drift.")
    for note in selected.get("notes", []):
        st.info(note)
    st.dataframe(frame, hide_index=True)
    st.download_button(
        "Download forecast CSV", frame.to_csv(index=False), "forecast.csv", "text/csv"
    )

with schedule_tab:
    st.subheader("Choose when your job should run")
    st.caption(f"Times are relative to the forecast, starting {first.isoformat()} (UTC).")
    with st.form("schedule_job"):
        a, b = st.columns(2)
        duration = a.number_input("Duration (whole hours)", min_value=1, max_value=48, value=2)
        power = b.number_input("Power (kW)", min_value=0.1, value=7.0)
        deadline_hours = st.slider("Finish within hours of first forecast slot", 1, 48, 24)
        strategy = st.selectbox("Objective", ["median", "upper"])
        interruptible = st.checkbox("Job may run in separate whole-hour slots")
        submitted = st.form_submit_button("Find a window", type="primary")
    st.caption("Upper minimizes summed endpoints; it is not a calibrated job-level guarantee.")
    if submitted:
        deadline = first + timedelta(hours=deadline_hours)
        if duration > deadline_hours:
            st.error("Duration must fit before the selected deadline.")
        else:
            code, result = request(
                "/v1/schedule",
                {
                    "region": region,
                    "duration_hours": int(duration),
                    "power_kw": float(power),
                    "deadline": deadline.isoformat(),
                    "strategy": strategy,
                    "interruptible": interruptible,
                },
            )
            if code != httpx.codes.OK:
                st.error("No valid window was returned. Try a shorter job or a later deadline.")
            else:
                recommendation = result["recommendation"]
                x, y = st.columns(2)
                x.metric("Expected proxy savings", f"{recommendation['expected_savings_pct']:.1f}%")
                y.metric(
                    "Expected emissions (gCO2e)", f"{recommendation['emissions_gco2_median']:.1f}"
                )
                st.write("**Start (UTC):**", recommendation["start"])
                st.write("**End (UTC):**", recommendation["end"])
                if recommendation.get("hours"):
                    st.write("Selected hourly slots", recommendation["hours"])
                for note in result.get("notes", []):
                    st.info(note)
                with st.expander("Full recommendation"):
                    st.json(result)

with monitor_tab:
    st.subheader("Observed model health")
    code, report = request("/v1/monitoring/status")
    if code == httpx.codes.NOT_FOUND:
        st.info(
            "No monitoring report is available for this API. The frozen demo ships without one."
        )
    elif code != httpx.codes.OK:
        st.error("Monitoring report could not be read. This does not indicate a healthy model.")
    else:
        st.metric("Recorded status", report.get("status", "unknown"))
        st.caption(
            f"Report generated: {report.get('generated_at', 'unknown')}. It may be historical."
        )
        for reason in report.get("reasons", []):
            st.warning(reason)
        st.json(report)

with st.expander("Model and interpretation"):
    st.write("Model version:", forecast["model_version"])
    st.write(
        "This estimates average generation-mix emissions, "
        "not marginal or certified avoided emissions. "
        "The dashboard reads the API and does not retrain or promote models."
    )
