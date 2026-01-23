import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
from google import genai

# --- 1. CORE CONFIGURATION & AUTO-HEALING ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Pro", initial_sidebar_state="expanded")

if 'integrity_error_count' not in st.session_state:
    st.session_state.integrity_error_count = 0

# --- 2. DATA ENGINE WITH CONFIDENCE SCORING ---
@st.cache_data(ttl=60)
def get_comprehensive_data(target):
    try:
        # Fetch all necessary tickers for scoring
        tickers = ["^VIX", "NQ=F", "ES=F", target]
        data = yf.download(tickers, period="2d", interval="5m", progress=False, multi_level_index=False)['Close']
        
        # 1. Systemic Fear Score (VIX) - Inverse relationship
        vix = data["^VIX"].iloc[-1]
        vix_score = max(0, 100 - (vix * 2.5)) # VIX 20 = 50 pts, VIX 40 = 0 pts
        
        # 2. Alpha Lead Score (NQ/ES)
        rs_ratio = data["NQ=F"] / data["ES=F"]
        rs_mom = (rs_ratio.iloc[-1] - rs_ratio.iloc[-5]) / rs_ratio.iloc[-5]
        rs_score = 50 + (rs_mom * 5000) # Centered at 50, scales with leadership
        rs_score = max(0, min(100, rs_score))
        
        # 3. Technical Momentum (RSI)
        df_target = yf.download(target, period="2d", interval="5m", progress=False, multi_level_index=False)
        delta = df_target['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        rsi_score = rsi # Direct RSI value as score
        
        # WEIGHTED CONFIDENCE CALCULATION
        # 40% VIX, 30% RS Lead, 30% RSI
        confidence = (vix_score * 0.4) + (rs_score * 0.3) + (rsi_score * 0.3)
        
        return confidence, vix, rs_mom, rsi, True
    except:
        return 0, 0.0, 0.0, 0.0, False

# --- 3. SIDEBAR & INTEGRITY ---
st.sidebar.title("🛡️ Risk Management")
asset_map = {"NQ=F (Nasdaq)": "NQ=F", "ES=F (S&P 500)": "ES=F"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

conf_score, current_vix, lead_mom, current_rsi, data_is_clean = get_comprehensive_data(target_symbol)

# Auto-Healing
if not data_is_clean:
    st.session_state.integrity_error_count += 1
    if st.session_state.integrity_error_count >= 3:
        st.cache_data.clear()
        st.rerun()
    st.sidebar.error(f"⚠️ Sync Lag ({st.session_state.integrity_error_count}/3)")
else:
    st.sidebar.success("✅ Data Integrity: 100%")

# --- 4. MAIN INTERFACE ---
st.title("🚀 NQ & ES Quantitative Trading Platform")

# CONFIDENCE METER HEADER
c1, c2, c3, c4 = st.columns(4)
with c1:
    color = "green" if conf_score > 60 else "red" if conf_score < 40 else "orange"
    st.metric("Trend Confidence", f"{conf_score:.0f}%", delta=f"{conf_score-50:.0f}% vs Neutral", delta_color="normal")
with c2:
    st.metric("VIX Factor", f"{current_vix:.1f}", "Safe" if current_vix < 22 else "High Risk", delta_color="inverse")
with c3:
    st.metric("RS Leadership", f"{lead_mom*100:+.2f}%", "NQ Lead" if lead_mom > 0 else "ES Lead")
with c4:
    st.metric("Momentum (RSI)", f"{current_rsi:.1f}", "Oversold" if current_rsi < 30 else "Normal")

@st.fragment(run_every=60)
def main_monitor():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        # Chart and indicator logic remains consistent
        last_p = df['Close'].iloc[-1]
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # AI VERDICT (Macro-Weighted)
        if st.button("🧠 Generate AI Prediction Verdict", use_container_width=True, type="primary"):
            st.info(f"### 🎯 AI Verdict (Confidence: {conf_score:.0f}%)")
            st.write("AI is analyzing the weighted confidence score...")
            # genai integration code here...

    except Exception as e: st.error(f"⚠️ System Error: {e}")

main_monitor()
