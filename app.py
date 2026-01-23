import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from google import genai
from datetime import datetime

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="NQ & ES Global Sentinel", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0
if 'trade_log' not in st.session_state: st.session_state.trade_log = []

# --- 3. SIDEBAR: SENTINEL & REPORTING ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# Report Generator
st.sidebar.subheader("📊 Performance Reporting")
if st.sidebar.button("Generate EOD Report", use_container_width=True):
    if st.session_state.trade_log:
        df_log = pd.DataFrame(st.session_state.trade_log)
        csv = df_log.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button("📥 Download CSV", data=csv, file_name=f"EOD_Report_{datetime.now().date()}.csv")
    else:
        st.sidebar.warning("No trades logged yet.")

if st.sidebar.button("Reset Session", use_container_width=True):
    st.session_state.wins = 0; st.session_state.losses = 0; st.session_state.trade_log = []

# Sector Breadth Tracker
st.sidebar.divider()
st.sidebar.subheader("Sector Breadth")
def get_sector_data():
    sectors = {"Tech (XLK)": "XLK", "Defensive (XLU)": "XLU"}
    results = {}
    for name, ticker in sectors.items():
        try:
            d = yf.download(ticker, period="1d", interval="5m", progress=False, multi_level_index=False)
            results[name] = ((d['Close'].iloc[-1] - d['Close'].iloc[0]) / d['Close'].iloc[0]) * 100
        except: results[name] = 0.0
    return results

sector_perf = get_sector_data()
st.sidebar.metric("Tech (XLK)", f"{sector_perf.get('Tech (XLK)', 0):.2f}%")
st.sidebar.metric("Defensive (XLU)", f"{sector_perf.get('Defensive (XLU)', 0):.2f}%")

# Asset Selection
asset_map = {"NQ=F (Nasdaq)": "NQ=F", "ES=F (S&P 500)": "ES=F"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

# --- 4. PREDICTIVE HEADER & REAL-TIME METRICS ---
st.title(f"🚀 {target_label} Global Sentinel")

def get_realtime_metrics(target):
    shadow_ticker = "QQQ" if "NQ" in target else "SPY"
    try:
        s_data = yf.download(shadow_ticker, period="1d", interval="1m", progress=False, multi_level_index=False)
        vix_data = yf.download("^VIX", period="1d", interval="1m", progress=False, multi_level_index=False)
        tnx_data = yf.download("^TNX", period="1d", interval="1m", progress=False, multi_level_index=False)
        
        s_price = float(s_data['Close'].iloc[-1])
        vix_price = float(vix_data['Close'].iloc[-1])
        tnx_price = float(tnx_data['Close'].iloc[-1])
        speed = float(s_data['Close'].iloc[-1] - s_data['Close'].iloc[-5])
        return s_price, shadow_ticker, vix_price, tnx_price, speed
    except: return 0.0, shadow_ticker, 0.0, 0.0, 0.0

shadow_p, shadow_n, vix_p, tnx_p, mkt_speed = get_realtime_metrics(target_symbol)

c1, c2, c3 = st.columns(3)
with c1: st.metric(f"Shadow {shadow_n}", f"${shadow_p:.2f}", delta=f"{mkt_speed:.2f}")
with c2: st.metric("VIX", f"{vix_p:.2f}", delta="Risk Filter", delta_color="inverse")
with c3: st.metric("10Y Yield", f"{tnx_p:.2f}%")

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

# --- 6. LOGGING & PERFORMANCE ---
st.divider()
c1, c2 = st.columns(2)

def log_trade(result):
    if market_d:
        st.session_state.trade_log.append({
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Asset": target_label,
            "Price": market_d['price'],
            "Signal": market_d['signal'],
            "Result": result,
            "VIX": vix_p,
            "Yield": tnx_p,
            "Tech_Bias": sector_perf.get("Tech (XLK)", 0)
        })

with c1:
    if st.button("✅ HIT TARGET", use_container_width=True):
        st.session_state.wins += 1
        log_trade("WIN")
        st.balloons()
with c2:
    if st.button("❌ HIT STOP-LOSS", use_container_width=True):
        st.session_state.losses += 1
        log_trade("LOSS")

st.sidebar.metric("Win Rate", f"{(st.session_state.wins/(st.session_state.wins+st.session_state.losses)*100 if (st.session_state.wins+st.session_state.losses)>0 else 0):.1f}%")
