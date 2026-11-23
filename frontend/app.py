"""Streamlit front-end for the Kickstarter Launch Checker (task T14).

Collects a campaign's launch-day details, sends them to the deployed API, and
shows the success probability plus a what-if chart of probability vs. goal.

Run locally (from the repo root):
    pip install -r frontend/requirements.txt
    streamlit run frontend/app.py

The API URL comes from the API_URL environment variable or Streamlit secrets,
falling back to the deployed Cloud Run service.
"""

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import plotly.graph_objects as go
import requests
import streamlit as st

sys.path.append(str(Path(__file__).parent))  # so `helpers` imports on Streamlit Cloud
from helpers import (  # noqa: E402
    MAX_DURATION_DAYS,
    MIN_GOAL_USD,
    build_instance,
    goal_grid,
    odds_label,
    subcategories,
)

DEFAULT_API_URL = "https://kickstarter-api-zcqiii5fia-ue.a.run.app"
REPO_URL = "https://github.com/gitnic-duke/aipi-510-kickstarter-launch-checker"
TIMEOUT_SECONDS = 30  # long enough for a Cloud Run cold start
CATEGORY_FILE = Path(__file__).parent / "category_values.json"


def api_url() -> str:
    if os.getenv("API_URL"):
        return os.environ["API_URL"].rstrip("/")
    try:
        return st.secrets["API_URL"].rstrip("/")
    except Exception:  # no secrets file, or no API_URL key in it
        return DEFAULT_API_URL


@st.cache_data
def load_category_values() -> dict:
    return json.loads(CATEGORY_FILE.read_text())


@st.cache_data(ttl=60, show_spinner=False)
def check_health(url: str) -> dict | None:
    try:
        response = requests.get(f"{url}/health", timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


# Identical requests are served from cache for 10 minutes: no repeat API calls.
@st.cache_data(ttl=600, show_spinner=False)
def predict(url: str, instances: list[dict]) -> dict:
    response = requests.post(
        f"{url}/predict", json={"instances": instances}, timeout=TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return response.json()


def pick(options: list[str], preferred: str) -> int:
    return options.index(preferred) if preferred in options else 0


def what_if_chart(goals: list[float], probabilities: list[float], goal: float) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=goals,
            y=probabilities,
            mode="lines",
            name="Predicted chance",
            hovertemplate="Goal $%{x:,.0f}<br>Chance %{y:.0%}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[goal],
            y=[probabilities[goals.index(round(goal, 2))]],
            mode="markers",
            marker={"size": 12},
            name="Your goal",
            hovertemplate="Your goal $%{x:,.0f}<br>Chance %{y:.0%}<extra></extra>",
        )
    )
    figure.update_layout(
        title="How your funding goal changes your odds",
        xaxis={"title": "Funding goal (USD, log scale)", "type": "log", "tickprefix": "$"},
        yaxis={"title": "Chance of reaching the goal", "range": [0, 1], "tickformat": ".0%"},
        height=380,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        legend={"orientation": "h", "y": -0.25},
    )
    return figure


st.set_page_config(page_title="Kickstarter Launch Checker", page_icon="🚀", layout="centered")
url = api_url()
values = load_category_values()

with st.sidebar:
    st.header("About")
    st.write(
        "Predicts whether a Kickstarter campaign will reach its goal, using only "
        "what you know on launch day."
    )
    health = check_health(url)
    if health:
        st.success(f"API connected · model `{health['model_version']}`")
    else:
        st.warning("API is waking up or unreachable. Try again in a few seconds.")
    st.markdown(f"[API docs]({url}/docs) · [Source code]({REPO_URL})")

st.title("🚀 Kickstarter Launch Checker")
st.caption("Enter your campaign's launch-day details to see its chance of getting funded.")

name = st.text_input("Campaign title", value="Dungeon Crawl: The Board Game", max_chars=200)
col1, col2 = st.columns(2)
main_options = values["main_category"]
main_category = col1.selectbox("Main category", main_options, index=pick(main_options, "Games"))
sub_options = subcategories(values, main_category)
category = col2.selectbox("Subcategory", sub_options, index=pick(sub_options, "Tabletop Games"))

col3, col4 = st.columns(2)
goal = col3.number_input(
    "Funding goal (USD)", min_value=float(MIN_GOAL_USD), value=5000.0, step=500.0, format="%.0f"
)
country = col4.selectbox("Country", values["country"], index=pick(values["country"], "US"))

col5, col6 = st.columns(2)
duration = col5.slider("Campaign length (days)", 1, MAX_DURATION_DAYS, 30)
launch_date = col6.date_input("Launch date", value=date.today() + timedelta(days=7))

inputs = {
    "name": name,
    "main_category": main_category,
    "category": category,
    "country": country,
    "duration_days": duration,
    "launch_date": launch_date,
}

if st.button("Check my odds", type="primary", disabled=not name.strip()):
    goals = goal_grid(goal)
    instances = [build_instance(**inputs, goal_usd=g) for g in goals]
    try:
        with st.spinner("Asking the model..."):
            result = predict(url, instances)
        st.session_state["result"] = {
            "inputs": {**inputs, "goal_usd": goal},
            "goals": goals,
            "goal": goal,
            "probabilities": result["probabilities"],
            "model_version": result["model_version"],
        }
    except (requests.ConnectionError, requests.Timeout):
        st.warning("The API is waking up (it scales to zero when idle). Try again in a moment.")
    except requests.HTTPError as error:
        if error.response is not None and error.response.status_code == 422:
            st.error(f"The API rejected those inputs: {error.response.json().get('detail')}")
        else:
            st.error("Something went wrong calling the API. Please try again.")

result = st.session_state.get("result")
if result:
    goals, chosen = result["goals"], result["goal"]
    probability = result["probabilities"][goals.index(round(chosen, 2))]
    if result["inputs"] != {**inputs, "goal_usd": goal}:
        st.info("You've changed the inputs. Click **Check my odds** to update.")
    st.metric("Chance of reaching the goal", f"{probability:.0%}", odds_label(probability))
    st.plotly_chart(what_if_chart(goals, result["probabilities"], chosen))
    st.caption(
        f"Model `{result['model_version']}`, trained on Kickstarter campaigns from 2009 to "
        "2018. It only sees launch-day details, not your video, marketing or audience, so "
        "treat this as a rough guide, not a guarantee."
    )
