
import streamlit as st
import pandas as pd
import time
import os
from dotenv import load_dotenv
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

load_dotenv()

st.set_page_config(page_title="Dev Carbon Estimator", layout="wide")

# ------------------------
# CONFIG
# ------------------------

REGIONS = {
    "AWS": {
        "eu-west-2 (London)": "GB",
        "eu-west-1 (Ireland)": "IE",
        "eu-central-1 (Frankfurt)": "DE",
        "us-east-1 (N. Virginia)": "US-NEISO"
    },
    "GCP": {
        "europe-west2 (London)": "GB",
        "europe-west1 (Belgium)": "BE"
    },
    "Azure": {
        "UK South": "GB"
    }
}

CARBON_INTENSITY = {
    "GB": 0.2,
    "IE": 0.35,
    "BE": 0.18,
    "DE": 0.4,
    "US-NEISO": 0.35
}

WORKLOAD_KWH = {
    "Light (chat only)": 0.0003,
    "Medium (LLM + APIs)": 0.001,
    "Heavy (LLM + audio/image)": 0.003
}

GPU_POWER_KW = 0.6
PUE = 1.2
COST_PER_KWH = 0.12

# ------------------------
# STATE
# ------------------------

if "step" not in st.session_state:
    st.session_state.step = 1

# ------------------------
# MODEL
# ------------------------

def estimate_gpu_hours(product_type, engineers):
    base = 400 if product_type == "AI / LLM" else 50
    return int(base * (engineers / 10))


def carbon_model(data, status=None):
    if status:
        status.write("⚡ Calculating GPU energy from workload...")
        time.sleep(0.4)

    gpu_kwh = data["gpu_hours"] * GPU_POWER_KW * PUE

    if status:
        status.write("🌍 Fetching regional carbon intensity data...")
        time.sleep(0.4)

    zone = REGIONS[data["cloud"]][data["region"]]
    intensity = CARBON_INTENSITY.get(zone, 0.3)

    if status:
        status.write("🧠 Estimating per-request AI energy usage...")
        time.sleep(0.4)

    per_request_kwh = WORKLOAD_KWH[data["workload"]]
    daily_requests = data["frontend_users"] * 20 + data["api_users"] * 50
    yearly_requests = daily_requests * 365

    usage_kwh = yearly_requests * per_request_kwh

    if status:
        status.write("🏢 Calculating team operational footprint...")
        time.sleep(0.4)

    infra_kwh = gpu_kwh + usage_kwh

    infra_emissions = infra_kwh * intensity / 1000
    people_emissions = data["headcount"] * 0.3

    total = infra_emissions + people_emissions

    return total, infra_emissions, people_emissions, gpu_kwh, usage_kwh

# ------------------------
# UI
# ------------------------

st.title("🌱 Dev Carbon Estimator")

# STEP 1
if st.session_state.step == 1:
    with st.form("step1"):
        st.header("1️⃣ Profile")

        cloud = st.selectbox("Cloud", ["AWS", "GCP", "Azure"])
        region = st.selectbox("Region", list(REGIONS[cloud].keys()))

        headcount = st.number_input("Headcount", 1, 1000, 20)
        engineers = st.number_input("Engineers", 1, 500, 10)

        product_type = st.selectbox("Product Type", ["AI / LLM", "SaaS", "Marketplace"])

        if st.form_submit_button("Next →"):
            st.session_state.profile = {
                "cloud": cloud,
                "region": region,
                "headcount": headcount,
                "engineers": engineers,
                "product_type": product_type
            }
            st.session_state.step = 2

# STEP 2
elif st.session_state.step == 2:
    with st.form("step2"):
        st.header("2️⃣ Usage")

        workload = st.selectbox("AI Workload", list(WORKLOAD_KWH.keys()))
        gpu_input = st.number_input("GPU Hours (optional)", 0, 5000, 0)

        frontend_users = st.number_input("Daily Frontend Users", 0, 1_000_000, 1000)
        api_users = st.number_input("Daily API Users", 0, 1_000_000, 500)

        col1, col2 = st.columns(2)
        back = col1.form_submit_button("← Back")
        next_btn = col2.form_submit_button("Next →")

        if back:
            st.session_state.step = 1

        if next_btn:
            profile = st.session_state.profile
            gpu_hours = gpu_input or estimate_gpu_hours(profile["product_type"], profile["engineers"])

            st.session_state.data = {
                **profile,
                "gpu_hours": gpu_hours,
                "frontend_users": frontend_users,
                "api_users": api_users,
                "workload": workload
            }
            st.session_state.step = 3

# STEP 3
elif st.session_state.step == 3:
    st.header("3️⃣ Results & Scenario Modelling")

    data = st.session_state.data

    status = st.empty()

    with st.spinner("Running carbon model..."):
        total, infra, people, gpu_kwh, usage_kwh = carbon_model(data, status)

    st.success("✅ Model complete")

    st.metric("Total Emissions", f"{round(total,2)} tCO₂/year")

    # Scenario state
    if "sim" not in st.session_state:
        st.session_state.sim = {
            "region": data["region"],
            "workload": data["workload"],
            "gpu_reduction": 0,
            "remote": 50
        }

    st.subheader("🔬 Scenario Simulator")

    st.session_state.sim["region"] = st.selectbox(
        "Region",
        list(REGIONS[data["cloud"]].keys()),
        index=list(REGIONS[data["cloud"]].keys()).index(st.session_state.sim["region"])
    )

    st.session_state.sim["workload"] = st.selectbox(
        "Workload",
        list(WORKLOAD_KWH.keys()),
        index=list(WORKLOAD_KWH.keys()).index(st.session_state.sim["workload"])
    )

    st.session_state.sim["gpu_reduction"] = st.slider("Reduce GPU (%)", 0, 50, st.session_state.sim["gpu_reduction"])
    st.session_state.sim["remote"] = st.slider("Remote Work (%)", 0, 100, st.session_state.sim["remote"])

    def run_sim(base, sim):
        status.write("🔧 Applying optimisation scenario...")
        time.sleep(0.3)

        sim_data = base.copy()
        sim_data["region"] = sim["region"]
        sim_data["workload"] = sim["workload"]
        sim_data["gpu_hours"] *= (1 - sim["gpu_reduction"] / 100)

        return carbon_model(sim_data, status)

    with st.spinner("Simulating changes..."):
        sim_total, sim_infra, sim_people, _, _ = run_sim(data, st.session_state.sim)

    sim_people *= (1 - st.session_state.sim["remote"] / 100)
    sim_total = sim_infra + sim_people

    # Savings
    reduction = total - sim_total
    percent = reduction / total * 100 if total else 0
    cost = (gpu_kwh + usage_kwh) * COST_PER_KWH * (percent / 100)

    st.metric("CO₂ Saved", f"{round(reduction,2)} t/year")
    st.metric("Cost Saved", f"${round(cost,0)}/year")

    if abs(reduction) < 0.01:
        st.warning("No meaningful changes yet — adjust the scenario.")

    # Monthly rollout
    st.subheader("Projected Emissions (Gradual Rollout)")
    st.info("Changes are phased in over 3 months.")

    months = list(range(1, 13))
    infra_series, people_series = [], []

    for m in months:
        factor = 0 if m == 1 else 0.4 if m == 2 else 0.7 if m == 3 else 1

        infra_series.append((infra + (sim_infra - infra) * factor) / 12)
        people_series.append((people + (sim_people - people) * factor) / 12)

    df = pd.DataFrame({
        "Month": months,
        "Infrastructure": infra_series,
        "People": people_series
    }).set_index("Month")

    st.bar_chart(df)

    # Explainability
    st.subheader("🔍 What’s driving the reduction?")

    st.markdown("""
- 🌍 Region: lower carbon electricity reduces emissions per kWh  
- ⚡ GPU: fewer compute hours reduce energy usage  
- 🧠 Workload: more efficient inference lowers per-request energy  
- 🏠 Remote: reduces office-related emissions  
""")

    if st.button("← Back"):
        st.session_state.step = 2
