from __future__ import annotations

import os

import requests
import streamlit as st

from airflow_client import AirflowClient


AIRFLOW_URL = os.getenv("AIRFLOW_API_URL", "http://airflow-api:8080")
DAG_ID = os.getenv("AIRFLOW_DAG_ID", "retail_lakehouse_pipeline")
AIRFLOW_USERNAME = os.environ["AIRFLOW_SERVICE_USERNAME"]
AIRFLOW_PASSWORD = os.environ["AIRFLOW_SERVICE_PASSWORD"]
ACTIVE_STATES = {"queued", "running"}

st.set_page_config(
    page_title="Lakehouse Control Panel",
    page_icon="🏔️",
    layout="wide",
)


def api_error(error: requests.RequestException) -> str:
    response = error.response
    if response is None:
        return "Airflow is unavailable. Check the platform status and try again."
    if response.status_code == 401:
        return "The internal Airflow session expired. Refresh the page and try again."
    if response.status_code == 403:
        return "The control-panel Airflow role does not allow this operation."
    try:
        detail = response.json().get("detail")
    except requests.JSONDecodeError:
        detail = None
    return detail or f"Airflow returned HTTP {response.status_code}."


def clear_token() -> None:
    st.session_state.pop("access_token", None)


client = AirflowClient(AIRFLOW_URL, DAG_ID)

st.title("Lakehouse Control Panel")
st.caption("Trigger and monitor the governed retail lakehouse pipeline.")

# Keep only the short-lived Airflow token in the browser session.
if "access_token" not in st.session_state:
    try:
        st.session_state["access_token"] = client.authenticate(
            AIRFLOW_USERNAME,
            AIRFLOW_PASSWORD,
        )
    except requests.RequestException as error:
        st.error(api_error(error))
        st.stop()
    except KeyError:
        st.error("Airflow returned an invalid authentication response.")
        st.stop()

token = st.session_state["access_token"]

with st.sidebar:
    st.info("Local operator mode")
    st.link_button("Open Airflow", "http://127.0.0.1:8080", width="stretch")
    st.link_button("Open Spark", "http://127.0.0.1:8081", width="stretch")

st.subheader("Trigger Pipeline")
with st.form("trigger"):
    automatic_volume = st.toggle(
        "Automatic demo volume",
        value=True,
        help="Generates 25,000 orders for the first two-year history and 3,000 for later monthly periods.",
    )
    first_column, second_column = st.columns(2)
    rows = first_column.number_input(
        "Order rows",
        min_value=1,
        max_value=100_000,
        value=25_000,
        step=500,
        disabled=automatic_volume,
    )
    seed = second_column.number_input(
        "Random seed",
        min_value=0,
        max_value=2_147_483_647,
        value=42,
        step=1,
    )
    trigger_submitted = st.form_submit_button("Run pipeline", type="primary")

if trigger_submitted:
    try:
        run = client.trigger(token, None if automatic_volume else int(rows), int(seed))
    except requests.RequestException as error:
        st.error(api_error(error))
        if error.response is not None and error.response.status_code == 401:
            clear_token()
    else:
        st.success(f"Triggered `{run['dag_run_id']}`.")

st.divider()
status_header, refresh_settings = st.columns([2, 1])
status_header.subheader("Pipeline Status")
auto_refresh = refresh_settings.toggle("Auto-refresh active runs", value=True)
refresh_seconds = refresh_settings.selectbox(
    "Refresh interval",
    options=(5, 10, 30),
    format_func=lambda value: f"{value} seconds",
    disabled=not auto_refresh,
)


@st.fragment(run_every=f"{refresh_seconds}s" if auto_refresh else None)
def run_status() -> None:
    if st.button("Refresh now"):
        pass
    try:
        runs = client.list_runs(token)
    except requests.RequestException as error:
        st.error(api_error(error))
        if error.response is not None and error.response.status_code == 401:
            clear_token()
        return

    if not runs:
        st.info("No pipeline runs are available yet.")
        return

    running_count = sum(run.get("state") in ACTIVE_STATES for run in runs)
    success_count = sum(run.get("state") == "success" for run in runs)
    failed_count = sum(run.get("state") == "failed" for run in runs)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Recent runs", len(runs))
    metric_columns[1].metric("Active", running_count)
    metric_columns[2].metric("Successful", success_count)
    metric_columns[3].metric("Failed", failed_count)

    run_rows = [
        {
            "Run ID": run["dag_run_id"],
            "State": run.get("state"),
            "Rows": (run.get("conf") or {}).get("rows") or "automatic",
            "Seed": (run.get("conf") or {}).get("seed"),
            "Triggered by": run.get("triggering_user_name"),
            "Queued": run.get("queued_at"),
            "Started": run.get("start_date"),
            "Ended": run.get("end_date"),
            "Duration (s)": run.get("duration"),
        }
        for run in runs
    ]
    st.dataframe(run_rows, hide_index=True, width="stretch")

    selected_run_id = st.selectbox(
        "Task details",
        options=[run["dag_run_id"] for run in runs],
    )
    try:
        tasks = client.list_tasks(token, selected_run_id)
    except requests.RequestException as error:
        st.error(api_error(error))
        return
    task_rows = [
        {
            "Task": task["task_id"],
            "State": task.get("state"),
            "Try": task.get("try_number"),
            "Started": task.get("start_date"),
            "Ended": task.get("end_date"),
            "Duration (s)": task.get("duration"),
        }
        for task in tasks
    ]
    st.dataframe(task_rows, hide_index=True, width="stretch")


run_status()
