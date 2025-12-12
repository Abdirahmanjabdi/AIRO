import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from data_processor import DataLoader
from ai_risk_officer import AIRiskOfficer
from ai_agent_v4 import ActiveAgent
from ai_ultimate import AIUltimate

# ==============================================================================
# MODULE: DASHBOARD (The "Face")
# PURPOSE: Visualizes the AI's decisions using a Web Interface (Streamlit).
# ==============================================================================

# 1. PAGE CONFIGURATION
# Set the browser title and layout
st.set_page_config(page_title="AIRO | VoidQuant", layout="wide", page_icon="🛡️")

# 2. CUSTOM CSS STYLING
# We inject HTML/CSS to override default styles (Dark Mode, Fonts)
st.markdown("""
<style>
    .metric-card {background-color: #0e1117; border: 1px solid #333; padding: 20px; border-radius: 10px; text-align: center;}
    .stApp {background-color: #000000;} /* Pure Black Background */
    h1, h2, h3 {font-family: 'Helvetica Neue', sans-serif; font-weight: 300; color: #E0E0E0;}
</style>
""", unsafe_allow_html=True)

# 3. CACHED DATA LOADING (The "Heavy Lifting")
# @st.cache_resource tells Streamlit: "Run this ONCE and save the result in memory."
# This prevents the AI from retraining every time you click a button.
@st.cache_resource
def get_data_and_models():
    filepath = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
    loader = DataLoader(filepath)
    loader.load_data()
    # Process Data
    df = loader.engineer_features()        # V1 features
    df = loader.engineer_context_features()# V2 features
    
    # Train Models (The separate "Entities")
    # Base: The standard model (V1/V2/V3)
    base_model = AIRiskOfficer(features=['Hour_Decimal', 'Losing_Streak', 'Drawdown_State', 'Lot_Deviation', 'Revenge_Timer', 'Lots', 'RR Ratio'])
    base_model.train(df)
    
    # Active: The Sizing model (V4)
    active_agent = ActiveAgent()
    active_agent.train(df)
    
    # Ultimate: The Combined model (V5)
    ultimate = AIUltimate()
    ultimate.train(df)
    
    return df, base_model, active_agent, ultimate

# Load the data (Try/Except handles potential file errors)
try:
    df_raw, base_model, active_agent, ultimate_agent = get_data_and_models()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# 4. SIDEBAR CONTROLS
st.sidebar.header("⚙️ Governance Parameters")

mode_options = {
    "V1: Baseline (Shadow Ledger)": "v1",
    "V2: Deep Context (Regime Aware)": "v2",
    "V3: Bayseian Optimizer (Tuned)": "v3",
    "V4: Active Agent (Sizing)": "v4",
    "V5: Ultimate Entity (All-in)": "v5"
}
selected_mode_label = st.sidebar.selectbox("Select Architecture", list(mode_options.keys()))
mode = mode_options[selected_mode_label]

# Dynamic Sliders
sensitivity = 1.0 # Default
risk_threshold = 0.70 # Default

if mode == "v4":
    # Let user play with sensitivity in V4
    sensitivity = st.sidebar.slider("Agent Sensitivity", 0.5, 3.0, 1.5)
else:
    if mode == "v5": risk_threshold = 0.6537 # Ultimate uses optimal
    if mode == "v3": risk_threshold = 0.6537 # V3 uses optimal
    if mode == "v1": risk_threshold = 0.70   # V1 uses standard

# 5. THE SIMULATION LOOP (Real-time calculation)
# We re-run the "Shadow Equity" calculation whenever the user changes a setting.
df = df_raw.copy()
initial_capital = 100000
shadow_curve = []
real_curve = []
curr_shadow = initial_capital
curr_real = initial_capital
interventions = []

for index, row in df.iterrows():
    pnl = row['PnL']
    
    # Track "Real" (Human) equity
    curr_real += pnl
    real_curve.append(curr_real)
    
    # Calculate "Shadow" (AI) equity
    multiplier = 1.0 # Default: Take full trade
    action = "ALLOWED"
    risk = 0.0
    
    # ROUTING LOGIC: Which brain do we use?
    if mode in ["v1", "v2", "v3"]:
        assessment = base_model.predict(row)
        risk = assessment['risk_prob']
        # Binary Rule: Block or Allow
        if risk > risk_threshold or assessment['is_anomaly']:
            multiplier = 0.0
            action = "BLOCKED"
    
    elif mode == "v4":
         mult, risk = active_agent.get_position_sizer(row)
         # Interactive override for slider
         if risk > 0.65: mult = max(0.0, 1.0 - (risk * sensitivity))
         else: mult = 1.0 - (risk * 0.4)
         multiplier = mult
         action = f"RESIZED ({multiplier:.2f}x)"

    elif mode == "v5":
        multiplier, risk = ultimate_agent.get_position_sizer(row)
        action = f"OPTIMIZED ({multiplier:.2f}x)"
        if multiplier == 0: action = "BLOCKED"

    # Apply Impact
    shadow_pnl = pnl * multiplier
    curr_shadow += shadow_pnl
    shadow_curve.append(curr_shadow)
    
    # LOG INTERVENTIONS (If AI changed the outcome)
    if multiplier < 1.0:
        # XAI: Ask the model "WHY?"
        explanation_obj = base_model
        if mode == "v4": explanation_obj = active_agent
        elif mode == "v5": explanation_obj = ultimate_agent
        
        shap_reasons = explanation_obj.get_explanation(row)
        top_reason = f"{shap_reasons[0][0]} ({shap_reasons[0][1]:+.2f})" if shap_reasons else "Anomaly"

        interventions.append({
            "Date": row['Open Time'],
            "Symbol": row['Symbol'],
            "Action": action,
            "Risk Score": f"{risk:.2f}",
            "Top Reason (XAI)": top_reason,
            "PnL Impact": f"${pnl:.2f}",
            "Shadow PnL": f"${shadow_pnl:.2f}"
        })

df['Real_Equity'] = real_curve
df['Shadow_Equity'] = shadow_curve

# 6. DISPLAY METRICS AND CHART
st.title("🛡️ AI Risk Officer (AIRO) | Governance Dashboard")
col1, col2, col3, col4 = st.columns(4)

r_ret = (curr_real - initial_capital) / initial_capital * 100
s_ret = (curr_shadow - initial_capital) / initial_capital * 100

col1.metric("Real Return", f"{r_ret:.2f}%")
col2.metric("AIRO Return", f"{s_ret:.2f}%", f"{s_ret - r_ret:+.2f}% Alpha")
col3.metric("Management Events", len(interventions))
col4.metric("Capital", f"${curr_shadow:,.0f}")

st.subheader(f"📈 Performance: Human vs {selected_mode_label}")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df['Open Time'], y=df['Real_Equity'], mode='lines', name='Human', line=dict(color='#00BFFF', width=2)))
fig.add_trace(go.Scatter(x=df['Open Time'], y=df['Shadow_Equity'], mode='lines', name='AIRO', line=dict(color='#FFD700', width=3)))
fig.update_layout(template="plotly_dark", height=500, margin=dict(l=0, r=0, t=30, b=0))
st.plotly_chart(fig, use_container_width=True)

# 7. INTERVENTION AUDIT LOG
st.subheader("📋 Intervention Ledger")
if interventions:
    st.dataframe(pd.DataFrame(interventions), use_container_width=True, height=300)
