import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, time
import pytz
from google import genai

# --- 1. CORE CONFIGURATION & CACHING ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Pro", initial_sidebar_state="expanded")

@st.cache_data(ttl=300)
def get_market_pulse():
    """Fetch macro data with nan-protection"""
    try:
        tickers = ["XLK", "XLU", "XLF", "^TNX", "^VIX", "NQ=F", "ES=F"]
        data = yf.download(tickers, period="2d", interval="5m", progress=False, multi_level_index=False)['Close']
        
        # Sector Performance Calculation
        perf = {k: ((data[v].iloc[-1] - data[v].iloc[0]) / data[v].iloc[0]) * 100 
                if not data[v].isnull().values.any() else 0.0 
                for k, v in {"Tech": "XLK", "Def": "XLU", "Fin": "XLF"}.items()}
        
        # Nan-Safe Extractions
        vix = data["^VIX"].iloc[-1]
        tnx = data["^TNX"].iloc[-1]
        
        # RS Ratio Calculation
        rs_ratio = data["NQ=F"] / data["ES=F"]
        rs_change = ((rs_ratio.iloc[-1] - rs_ratio.iloc[0]) / rs_ratio.iloc[0]) * 100
        
        # Integrity Check: Are there any NaNs in the final metrics?
        is_clean = not (np.isnan(vix) or np.isnan(tnx) or np.isnan(rs_change))
        
        return perf, (vix if not np.isnan(vix) else 0.0), (tnx if not np.isnan(tnx) else 0.0), (rs_change if not np.isnan(rs_change) else 0.0), is_clean
    except: return {}, 0.0, 0.0, 0.0, False

# --- 2. PERSISTENT STATE ---
defaults = {'wins': 0, 'losses': 0, 'trade_log': [], 'total_pnl': 0.0}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 3. SIDEBAR: HEATMAP & INTEGRITY ---
st.sidebar.title("🛡️ Risk Management")
active_google_key = st.secrets.get("GEMINI_API_KEY", "")

sectors, vix, tnx, rs_lead, data_is_clean = get_market_pulse()

# Data Health Badge
if data_is_clean:
    st.sidebar.success("✅ Data Integrity: 100%")
else:
    st.sidebar.error("⚠️ Data Integrity: POOR (AI Disabled)")

account_size = st.sidebar.number_input("Account Balance ($)", value=50000)
risk_pct = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0) / 100

st.sidebar.divider()
st.sidebar.subheader("🔥 Multi-Timeframe Heatmap")
asset_map = {"NQ=F (Nasdaq)": "NQ=F", "ES=F (S&P 500)": "ES=F"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

def get_tf_trend(symbol, interval):
    try:
        data = yf.download(symbol, period="2d", interval=interval, progress=False, multi_level_index=False)['Close']
        return "🟢" if data.rolling(9).mean().iloc[-1] > data.rolling(21).mean().iloc[-1] else "🔴"
    except: return "⚪"

c1, c2, c3 = st.sidebar.columns(3)
c1.metric("1m", get_tf_trend(target_symbol, "1m"))
c2.metric("5m", get_tf_trend(target_symbol, "5m"))
c3.metric("15m", get_tf_trend(target_symbol, "15m"))

# --- 4. MAIN INTERFACE ---
st.title("🚀 NQ & ES Quantitative Trading Platform")
st.metric("Alpha RS Lead (NQ/ES)", f"{rs_lead:+.2f}%", delta_color="normal" if rs_lead > 0 else "inverse")

@st.fragment(run_every=60)
def main_monitor():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        # Technical Indicator Calculations
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
        df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
        last_p = df['Close'].iloc[-1]
        dev = ((last_p - df['VWAP'].iloc[-1]) / df['VWAP'].iloc[-1]) * 100
        
        m1, m2 = st.columns(2)
        m1.metric("Price", f"${last_p:.2f}", f"{dev:+.2f}% VWAP")
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- SHIELDED AI VERDICT ---
        st.divider()
        if data_is_clean:
            if st.button("🧠 Generate AI Prediction Verdict", use_container_width=True, type="primary"):
                client = genai.Client(api_key=active_google_key)
                prompt = f"Analyze {target_label}: Price {last_p}, Dev {dev:.2f}%, RS {rs_lead:+.2f}%. Verdict/Confidence."
                resp = client.models.generate_content(model='gemini-2.0-flash-exp', contents=prompt)
                st.info(f"### 🎯 AI Verdict\n{resp.text}")
        else:
            st.warning("🤖 AI Engine Suspended: Market data synchronization required.")

    except Exception as e: st.error(f"⚠️ System Sync Error: {str(e)}")

main_monitor()
