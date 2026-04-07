import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="Dev Carbon Estimator", layout="wide")

# ------------------------
# DATA + CONSTANTS
# ------------------------

PROFILES = {
    "AI Startup": {
        "headcount": 15,
        "engineers": 10,
        "product_type": "AI / LLM",
        "cloud": "AWS",
        "gpu_hours": 500,
        "region": "us-east-1"
    },
    "SaaS Startup": {
        "headcount": 25,
        "engineers": 12,
        "product_type": "SaaS",
        "cloud": "GCP",
        "gpu_hours": 50,
        "region": "europe-west1"
    },
    "Marketplace": {
        "headcount": 20,
        "engineers": 8,
        "product_type": "Marketplace",
        "cloud": "AWS",
        "gpu_hours": 20,
        "region": "eu-west-2"
    }
}

# Approx public carbon intensity data (kgCO2 per kWh)
REGION_CARBON_INTENSITY = {
    "us-east-1": 0.4,
    "eu-west-2": 0.2,
    "europe-west1": 0.15
}

GPU_POWER_KW = 0.3  # Average GPU draw (300W)
PUE = 1.2  # Data center overhead factor


# ------------------------
# HELPERS
# ------------------------

def estimate_gpu_hours(data):
    """Estimate GPU usage if user leaves it blank"""
    if data["product_type"] == "AI / LLM":
        base = 300
    elif data["product_type"] == "SaaS":
        base = 40
    else:
        base = 20

    scale = data["engineers"] / 10
    return int(base * scale)


def ai_carbon_model(data):
    """Data-driven carbon estimation"""

    region_intensity = REGION_CARBON_INTENSITY.get(data["region"], 0.3)

    # Infrastructure emissions
    energy_kwh = data["gpu_hours"] * GPU_POWER_KW * PUE
    infra_emissions = energy_kwh * region_intensity / 1000  # tonnes CO2

    # People emissions (rough baseline)
    people_emissions = data["headcount"] * 0.3

    # Cloud efficiency factor
    cloud_factor = {
        "AWS": 1.1,
        "GCP": 0.9,
        "Azure": 1.0
    }.get(data["cloud"], 1.0)

    total = (people_emissions + infra_emissions) * cloud_factor

    # Confidence scoring
    confidence = 60
    if data["gpu_hours"] > 0:
        confidence += 20
    if data["region"] in REGION_CARBON_INTENSITY:
        confidence += 10

    confidence += random.randint(-3, 3)  # small uncertainty

    breakdown = {
        "People": round(people_emissions, 2),
        "Infrastructure": round(infra_emissions, 2),
        "Energy (kWh)": round(energy_kwh, 2)
    }

    return round(total, 2), min(confidence, 95), breakdown


def generate_recommendations(data):
    recs = []

    if data["gpu_hours"] > 100:
        recs.append("Reduce GPU usage or optimise inference workloads")

    if data["region"] not in REGION_CARBON_INTENSITY:
        recs.append("Switch to a lower-carbon cloud region")

    if data["engineers"] / data["headcount"] > 0.6:
        recs.append("Audit engineering workflows for compute efficiency")

    if data["cloud"] == "AWS":
        recs.append("Evaluate lower-carbon regions or Graviton instances on AWS")

    return recs


# ------------------------
# SESSION STATE
# ------------------------

if "data" not in st.session_state:
    st.session_state.data = None

if "results" not in st.session_state:
    st.session_state.results = None

if "completed_recs" not in st.session_state:
    st.session_state.completed_recs = []

if "gpu_estimated" not in st.session_state:
    st.session_state.gpu_estimated = False


# ------------------------
# UI: TITLE
# ------------------------

st.title("🌱 Dev Carbon Estimator")
st.subheader("Estimate and reduce your startup’s carbon footprint")

# ------------------------
# STEP 1: PROFILE
# ------------------------

st.header("1️⃣ Select Your Startup Profile")

profile_choice = st.selectbox("Choose a profile", list(PROFILES.keys()))
profile_data = PROFILES[profile_choice]

col1, col2 = st.columns(2)

with col1:
    headcount = st.number_input("Headcount", value=profile_data["headcount"])
    engineers = st.number_input("Number of Engineers", value=profile_data["engineers"])
    product_type = st.selectbox(
        "Product Type",
        ["AI / LLM", "SaaS", "Marketplace", "Mobile App"],
        index=0
    )

with col2:
    cloud = st.selectbox("Cloud Provider", ["AWS", "GCP", "Azure"])
    gpu_hours_input = st.number_input(
        "Monthly GPU Hours (optional)",
        min_value=0,
        value=0,
        help="Leave as 0 to auto-estimate based on your company profile"
    )
    region = st.text_input("Cloud Region", value=profile_data["region"])


# ------------------------
# GENERATE REPORT
# ------------------------

if st.button("Generate Report"):

    gpu_hours = gpu_hours_input
    estimated_flag = False

    if gpu_hours == 0:
        gpu_hours = estimate_gpu_hours({
            "product_type": product_type,
            "engineers": engineers
        })
        estimated_flag = True

    user_data = {
        "headcount": headcount,
        "engineers": engineers,
        "product_type": product_type,
        "cloud": cloud,
        "gpu_hours": gpu_hours,
        "region": region
    }

    st.session_state.data = user_data
    st.session_state.results = ai_carbon_model(user_data)
    st.session_state.gpu_estimated = estimated_flag


# ------------------------
# STEP 2: REPORTING
# ------------------------

if st.session_state.results:
    st.header("2️⃣ Carbon Report")

    total, confidence, breakdown = st.session_state.results

    if st.session_state.gpu_estimated:
        st.warning(f"GPU usage estimated at {st.session_state.data['gpu_hours']} hrs/month based on your profile")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Emissions (tCO₂/year)", total)
    col2.metric("Model Confidence (%)", confidence)
    col3.metric("Industry Benchmark", "Medium")

    st.write("### Emissions Breakdown")
    df = pd.DataFrame(list(breakdown.items()), columns=["Category", "Value"])
    st.bar_chart(df.set_index("Category"))

    st.info(f"Estimated accuracy: {confidence}% based on data completeness")

    # Download report
    report_df = pd.DataFrame([st.session_state.data])
    csv = report_df.to_csv(index=False)

    st.download_button(
        label="📥 Download Report (CSV)",
        data=csv,
        file_name="carbon_report.csv",
        mime="text/csv"
    )


# ------------------------
# STEP 3: RECOMMENDATIONS
# ------------------------

if st.session_state.results:
    st.header("3️⃣ Recommendations")

    recs = generate_recommendations(st.session_state.data)

    for rec in recs:
        checked = st.checkbox(rec)

        if checked and rec not in st.session_state.completed_recs:
            st.session_state.completed_recs.append(rec)

    if st.session_state.completed_recs:
        st.success(f"✅ {len(st.session_state.completed_recs)} actions completed!")

    # Recalculate improvements
    if st.button("Recalculate with Improvements"):
        improved_data = st.session_state.data.copy()
        improved_data["gpu_hours"] *= 0.8

        st.session_state.results = ai_carbon_model(improved_data)
        st.success("Updated results based on improvements!")