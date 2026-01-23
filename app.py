import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from google import genai
from google.genai import types
from datetime import datetime
import yfinance as yf

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="NQ & ES Global Sentinel", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. SIDEBAR: GLOBAL SENTINEL & SECTOR BREADTH ---
st.sidebar.title("⚠️ Systemic Risk Monitor")
active_google_key = st.secrets.get("GEMINI_API_KEY", "")

# Sector Breadth Tracker
st.sidebar.subheader("Sector Breadth (Real-Time)")
def get_sector_data():
    sectors = {
        "Tech (XLK)": "XLK",
        "Finance (XLF)": "XLF",
        "Energy (XLE)": "XLE",
        "Defensive (XLU)": "XLU"
    }
    results = {}
    for name, ticker in sectors.items():
        try:
            d = yf.download(ticker, period="1d", interval="5m", progress=False)
            change = ((d['Close'].iloc[-1] - d['Close'].iloc[0]) / d['Close'].iloc[0]) * 100
            results[name] = change
        except: results[name] = 0.0
    return results

sector_perf = get_sector_data()
for name, perf in sector_perf.items():
    st.sidebar.metric(name, f"{perf:.2f}%", delta=f"{perf:.2f}%")

# Global Macro Sentinel
st.sidebar.divider()
st.sidebar.subheader("🌍 Global Macro Sentinel")
def get_macro_data():
    tickers = ["^TNX", "CL=F", "GC=F", "DX=F"]
    data = yf.download(tickers, period="1d", interval="15m", progress=False)['Close']
    latest = data.iloc[-1]
    return latest["^TNX"], latest["CL=F"], latest["GC=F"], latest["DX=F"]

tnx_p, oil_p, gold_p, dxy_p = get_macro_data()
st.sidebar.metric("10Y Yield", f"{tnx_p:.2f}%")
st.sidebar.metric("US Dollar", f"{dxy_p:.2f}")

# Asset Selection
asset_map = {"NQ=F (Nasdaq)": "NQ=F", "ES=F (S&P 500)": "ES=F"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

# --- 4. PREDICTIVE HEADER (SHADOW + BREADTH) ---
st.title(f"🚀 {target_label} Global Sentinel")

def get_realtime_metrics(target):
    shadow_ticker = "QQQ" if "NQ" in target else "SPY"
    s_data = yf.download(shadow_ticker, period="1d", interval="1m", progress=False)
    vix_p = yf.download("^VIX", period="1d", interval="1m", progress=False)['Close'].iloc[-1]
    s_price = s_data['Close'].iloc[-1]
    speed = (s_data['Close'].iloc[-1] - s_data['Close'].iloc[-5])
    return s_price, shadow_ticker, vix_p, speed

shadow_p, shadow_n, vix_p, mkt_speed = get_realtime_metrics(target_symbol)

c1, c2, c3 = st.columns(3)
with c1: st.metric(f"Shadow {shadow_n}", f"${shadow_p:.2f}", delta=f"{mkt_speed:.2f}")
with c2: st.metric("VIX", f"{vix_p:.2f}", delta_color="inverse")
with c3:
    # Logic: If Tech is leading, it's Risk-On. If Defensive is leading, it's Risk-Off
    internal_bias = "RISK-ON 🚀" if sector_perf["Tech (XLK)"] > sector_perf["Defensive (XLU)"] else "DEFENSIVE 🛡️"
    st.subheader(f"Internal Bias: {internal_bias}")

# --- 5. THE MONITOR & SIGNAL ENGINE ---
@st.fragment(run_every=60)
def monitor_market():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        last_price = df['Close'].iloc[-1]
        df['VWAP'] = ((df['High'] + df['Low'] + df['Close'])/3 * df['Volume']).cumsum() / df['Volume'].cumsum()
        vwap_v = df['VWAP'].iloc[-1]
        
        sig_s = "STRONG LONG 🚀" if last_price > vwap_v else "STRONG SHORT 📉"
        st.subheader(f"Signal: {sig_s} | Price: {last_price:.2f}")
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        return {"price": last_price, "signal": sig_s, "vwap": vwap_v}
    except: return None

market_d = monitor_market()

# --- 6. THE DEEP BREADTH VERDICT ---
st.divider()
if st.button("Analyze Global Macro Verdict", use_container_width=True):
    if not active_google_key: st.warning("Enter Google AI Key.")
    elif market_d:
        client = genai.Client(api_key=active_google_key)
        prompt = f"""
        Analyze {target_label}:
        - Technical: {market_d['signal']} @ {market_d['price']}
        - Sector Breadth: {sector_perf}
        - Macro Sentinel: Yields {tnx_p}%, DXY {dxy_p}, Oil ${oil_p}
        - Real-Time Shadow: {shadow_p} | VIX {vix_p} | Speed {mkt_speed}
        
        Verdict Criteria:
        1. Sector Quality: Is this move led by Tech or Defensive rotation?
        2. Macro Alignment: Do Yields/DXY support the signal?
        3. Predictive Lag: Is the real-time Shadow ETF confirming the delayed Signal?
        """
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        st.info("🤖 Deep Breadth AI Verdict"); st.markdown(response.text)

c1, c2 = st.columns(2)
with c1:
    if st.button("✅ HIT TARGET", use_container_width=True): st.session_state.wins += 1; st.balloons()
with c2:
    if st.button("❌ HIT STOP-LOSS", use_container_width=True): st.session_state.losses += 1
