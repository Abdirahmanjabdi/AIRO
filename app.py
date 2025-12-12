import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
from data_processor import DataLoader
from ai_risk_officer import AIRiskOfficer
from ai_agent_v4 import ActiveAgent
from ai_ultimate import AIUltimate

# ==============================================================================
# MODULE: DASHBOARD (Optimized & Robust)
# ==============================================================================

st.set_page_config(page_title="AIRO | VoidQuant", layout="wide", page_icon="🛡️")

st.markdown("""
<style>
    .metric-card {background-color: #0e1117; border: 1px solid #333; padding: 20px; border-radius: 10px; text-align: center;}
    .stApp {background-color: #000000;}
    h1, h2, h3 {font-family: 'Helvetica Neue', sans-serif; font-weight: 300; color: #E0E0E0;}
</style>
""", unsafe_allow_html=True)

# --- 1. OPTIMIZED DATA LOADING & PREDICTION ---
@st.cache_resource
def load_system():
    # Relative path for GitHub compatibility
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(base_dir, "Abdirahman Jama Abdi - REmodal.csv")
    
    loader = DataLoader(filepath)
    loader.load_data()
    df = loader.engineer_features()
    df = loader.engineer_context_features()
    
    # --- MODEL 1: BASELINE (Behavior Only) ---
    v1_features = ['Hour_Decimal', 'Losing_Streak', 'Drawdown_State', 'Lot_Deviation', 'Revenge_Timer', 'Lots', 'RR Ratio']
    model_v1 = AIRiskOfficer(features=v1_features)
    model_v1.train(df)
    
    # --- MODEL 2: CONTEXT AWARE (Behavior + Regime) ---
    v2_features = v1_features + ['Realized_Vol_20', 'Trend_Momentum']
    model_v2 = AIRiskOfficer(features=v2_features)
    model_v2.train(df)
    
    # --- MODEL 4/5: AGENTS ---
    agent_v4 = ActiveAgent() # Uses default features but different logic
    agent_v4.train(df)
    
    agent_v5 = AIUltimate() # Uses V2 features + Optimized Params
    agent_v5.train(df)
    
    # --- VECTORIZED PREDICTIONS (THE SPEED FIX) ---
    # We predict ONCE for the whole dataframe here, not in the loop.
    
    # V1 Predictions
    df['Risk_V1'] = [x['risk_prob'] for x in [model_v1.predict(row) for _, row in df.iterrows()]]
    df['Anomaly_V1'] = [x['is_anomaly'] for x in [model_v1.predict(row) for _, row in df.iterrows()]]
    
    # V2 Predictions (Different Feature Set)
    df['Risk_V2'] = [x['risk_prob'] for x in [model_v2.predict(row) for _, row in df.iterrows()]]
    df['Anomaly_V2'] = [x['is_anomaly'] for x in [model_v2.predict(row) for _, row in df.iterrows()]]
    
    # V5 (Ultimate) Predictions
    df['Risk_V5'] = [x['risk_prob'] for x in [agent_v5.predict(row) for _, row in df.iterrows()]]
    df['Anomaly_V5'] = [x['is_anomaly'] for x in [agent_v5.predict(row) for _, row in df.iterrows()]]

    return df, model_v1, model_v2, agent_v4, agent_v5

try:
    df_cached, model_v1, model_v2, agent_v4, agent_v5 = load_system()
except Exception as e:
    st.error(f"System Error: {e}")
    st.stop()

# --- 2. UI CONTROLS ---
st.title("🛡️ AI Risk Officer (AIRO) | Governance Dashboard")

st.sidebar.header("⚙️ Architecture")
mode_options = {
    "V1: Baseline (Shadow Ledger)": "v1",
    "V2: Deep Context (Regime Aware)": "v2",
    "V3: Bayseian Optimizer (Tuned)": "v3",
    "V4: Active Agent (Sizing)": "v4",
    "V5: Ultimate Entity (All-in)": "v5"
}

# Use index to maintain state if needed
mode_keys = list(mode_options.keys())
selected_label = st.sidebar.selectbox("Select Version", mode_keys)
mode = mode_options[selected_label]

# Initialize Params
risk_threshold = 0.70
sensitivity = 1.0

# Dynamic Config
if mode == "v1":
    st.sidebar.info("V1: Fixed Threshold (0.70)")
    risk_threshold = 0.70
elif mode == "v2":
    st.sidebar.info("V2: Context Aware (0.70)")
    risk_threshold = 0.70
elif mode == "v3":
    st.sidebar.success("V3: Optimized (0.6537)")
    risk_threshold = 0.6537
elif mode == "v4":
    sensitivity = st.sidebar.slider("Sensitivity (Gamma)", 0.5, 3.0, 1.5)
elif mode == "v5":
    st.sidebar.warning("V5: Full Autonomy")
    risk_threshold = 0.6537
    sensitivity = 1.5

# --- 3. FAST SIMULATION ENGINE ---
# Uses pre-calculated risk columns where possible

df = df_cached.copy()
initial = 100000
real_curve = []
shadow_curve = []
curr_real = initial
curr_shadow = initial
interventions = []

for index, row in df.iterrows():
    pnl = row['PnL']
    curr_real += pnl
    real_curve.append(curr_real)
    
    multiplier = 1.0
    action = "ALLOWED"
    risk_val = 0.0
    
    # LOGIC SWITCH
    if mode == "v1":
        risk_val = row['Risk_V1']
        is_anomaly = row['Anomaly_V1']
        if risk_val > risk_threshold or is_anomaly:
            multiplier = 0.0
            action = "BLOCKED (V1)"
            
    elif mode == "v2":
        risk_val = row['Risk_V2'] # Uses Context Features
        is_anomaly = row['Anomaly_V2']
        if risk_val > risk_threshold or is_anomaly:
            multiplier = 0.0
            action = "BLOCKED (Ctx)"
            
    elif mode == "v3":
        # V3 uses V2 features but V3 threshold
        risk_val = row['Risk_V2'] 
        is_anomaly = row['Anomaly_V2']
        if risk_val > risk_threshold: # Optimized Threshold
            multiplier = 0.0
            action = "BLOCKED (Opt)"
            
    elif mode == "v4":
        # V4 Logic (Active Sizing)
        # We calculate sizing dynamiclly based on slider
        # Use V1 risk for V4 standard, or V2? Typically V4 used V1 features in report.
        risk_val = row['Risk_V1']
        if risk_val > 0.65:
             mult = max(0.0, 1.0 - (risk_val * sensitivity))
        else:
             mult = 1.0 - (risk_val * 0.4)
        multiplier = mult
        action = f"RESIZED {multiplier:.2f}x"
        
    elif mode == "v5":
        # V5 Logic (Ultimate)
        risk_val = row['Risk_V5'] # Uses V2 Features + Opt Params
        is_anomaly = row['Anomaly_V5']
        
        if is_anomaly:
            multiplier = 0.0
        elif risk_val > risk_threshold:
            multiplier = max(0.0, 1.0 - (risk_val * sensitivity))
        else:
             multiplier = 1.0 - (risk_val * 0.4)
        
        action = f"AUTO {multiplier:.2f}x"

    # Execution
    shadow_pnl = pnl * multiplier
    curr_shadow += shadow_pnl
    shadow_curve.append(curr_shadow)
    
    # Logging
    # Logging
    trigger = (multiplier < 1.0)
    if trigger:
        # XAI: Get Explanation (Why?)
        # Route to correct model
        explanation_obj = model_v1
        if mode == "v2": explanation_obj = model_v2
        elif mode == "v3": explanation_obj = model_v2 # V3 uses V2 features
        elif mode == "v4": explanation_obj = agent_v4
        elif mode == "v5": explanation_obj = agent_v5
        
        shap_reasons = explanation_obj.get_explanation(row)
        top_reason = f"{shap_reasons[0][0]} ({shap_reasons[0][1]:+.2f})" if shap_reasons else "Anomaly"

        interventions.append({
            "Date": row['Open Time'],
            "Symbol": row['Symbol'],
            "Action": action,
            "Risk": f"{risk_val:.2f}",
            "Top Reason (XAI)": top_reason,
            "PnL Impact": f"${pnl:.2f}",
            "Shadow PnL": f"${shadow_pnl:.2f}"
        })

df['Real_Equity'] = real_curve
df['Shadow_Equity'] = shadow_curve

# --- 4. VISUALIZATION ---
r_ret = (curr_real - initial) / initial * 100
s_ret = (curr_shadow - initial) / initial * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("Real Return", f"{r_ret:.2f}%")
col2.metric("AIRO Return", f"{s_ret:.2f}%", f"{s_ret - r_ret:+.2f}% Alpha")
col3.metric("Interventions", len(interventions))
col4.metric("Capital", f"${curr_shadow:,.0f}")

st.subheader(f"📈 Performance: Human vs {selected_label}")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df['Open Time'], y=df['Real_Equity'], mode='lines', name='Human', line=dict(color='#00BFFF', width=2)))
fig.add_trace(go.Scatter(x=df['Open Time'], y=df['Shadow_Equity'], mode='lines', name='AIRO', line=dict(color='#FFD700', width=3)))
fig.update_layout(template="plotly_dark", height=500, margin=dict(t=30, l=0, r=0, b=0), legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
st.plotly_chart(fig, use_container_width=True)

if interventions:
    st.subheader("📋 Intervention Ledger")
    st.dataframe(pd.DataFrame(interventions), use_container_width=True)
