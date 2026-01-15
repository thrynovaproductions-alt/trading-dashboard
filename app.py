import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from twelvedata import TDClient
from google import genai
from google.genai import types
import streamlit.components.v1 as components
from datetime import datetime
import pytz
import requests
import yfinance as yf

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="AI Quant Workstation", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0
if 'journal' not in st.session_state: st.session_state.journal = []

# --- 3. SIDEBAR: COMMAND CENTER ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# A. API MANAGEMENT & CREDIT GUARD
st.sidebar.subheader("🔌 API Health")
twelve_key = st.sidebar.text_input("Twelve Data Key:", type="password")
active_twelve_key = twelve_key if twelve_key else st.secrets.get("TWELVE_DATA_API_KEY", "")
active_ai_key = st.sidebar.text_input("Gemini Key Override:", type="password") or st.secrets.get("GEMINI_API_KEY", "")

def get_api_usage(key):
    try:
        url = f"https://api.twelvedata.com/api_usage?apikey={key}"
        res = requests.get(url).json()
        return res.get('credits_used', 0), res.get('credits_left', 'Unknown')
    except: return 0, "N/A"

used, left = get_api_usage(active_twelve_key)
st.sidebar.write(f"Credits Used: {used} | Credits Left: {left}")

# B. GLOBAL HEATMAP & DRIVERS
st.sidebar.divider()
st.sidebar.subheader("🌍 Global Market Drivers")
st.sidebar.markdown("[🔥 View Real-Time Global Heatmap](https://www.tradingview.com/heatmap/stock/)")

# Top Weights for Contextual Analysis
top_drivers = {
    "QQQ": ["AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA", "GOOG", "AVGO", "COST"],
    "SPY": ["MSFT", "AAPL", "NVDA", "AMZN", "META", "GOOGL", "BRK.B", "GOOG", "AVGO", "JPM"]
}

# C. RELATIVE STRENGTH & PERFORMANCE
def get_relative_strength():
    try:
        data = yf.download(["QQQ", "SPY"], period="5d", interval="1h", progress=False)['Close']
        returns = data.pct_change().dropna()
        rs_line = (1 + returns['QQQ']).cumprod() / (1 + returns['SPY']).cumprod()
        current_rs = rs_line.iloc[-1]
        status = "Nasdaq Stronger" if current_rs > 1 else "S&P Stronger"
        return current_rs, status
    except: return 1.0, "Neutral"

rs_val, rs_status = get_relative_strength()
st.sidebar.metric("Relative Strength (QQQ/SPY)", f"{rs_val:.4f}", rs_status)

total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total: {total_trades}")

# --- 4. THE MONITOR & 5-TIER SIGNAL ENGINE ---
asset_map = {"Nasdaq (QQQ)": "QQQ", "S&P 500 (SPY)": "SPY"}
target_label = st.sidebar.selectbox("Active Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

@st.fragment(run_every=60)
def monitor_market():
    if not active_twelve_key:
        st.warning("Enter Twelve Data API Key.")
        return None
    
    try:
        td = TDClient(apikey=active_twelve_key)
        df = td.time_series(symbol=target_symbol, interval="5min", outputsize=50).as_pandas()
        df.index = pd.to_datetime(df.index)
        
        # Trend Matrix
        ts_1h = td.time_series(symbol=target_symbol, interval="1h", outputsize=20).as_pandas()
        trend = "BULLISH" if ts_1h['close'].iloc[0] > ts_1h['close'].iloc[-1] else "BEARISH"
        
        last_price = df['close'].iloc[0]
        vwap_last = (df['close'] * df['volume']).cumsum().iloc[0] / df['volume'].cumsum().iloc[0]
        
        # 5-Tier Signal Strength
        vol_ref = (df['high'].head(10) - df['low'].head(10)).mean()
        chop_buffer = vol_ref * 0.3
        
        if abs(last_price - vwap_last) < chop_buffer:
            sig_str = "WAIT ⏳"
        elif last_price > vwap_last:
            sig_str = "STRONG LONG 🚀" if trend == "BULLISH" else "WEAK LONG ⚠️"
        else:
            sig_str = "STRONG SHORT 📉" if trend == "BEARISH" else "WEAK SHORT ⚠️"

        # Risk Shield
        sl_buffer = vol_ref * 1.5
        sl_l = last_price - sl_buffer; tp_l = last_price + (sl_buffer * 3)
        sl_s = last_price + sl_buffer; tp_s = last_price - (sl_buffer * 3)

        st.subheader(f"🚀 {target_symbol} Live: {last_price:.2f} | {sig_str}")
        
        c1, c2 = st.columns(2)
        with c1: st.success(f"🟢 LONG: TP {tp_l:.2f} | SL {sl_l:.2f}")
        with c2: st.error(f"🔴 SHORT: TP {tp_s:.2f} | SL {sl_s:.2f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['vwap'] if 'vwap' in df.columns else vwap_last, line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, sig_str, trend
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

m_data = monitor_market()

# --- 5. TOP STOCKS & AI STRATEGY ---
st.divider()
col_j1, col_j2 = st.columns([1, 2])

with col_j1:
    st.write(f"### 🏢 {target_symbol} Top Weights")
    st.write(", ".join(top_drivers[target_symbol]))
    
    st.write("### 🏁 Log Trade")
    res_col1, res_col2 = st.columns(2)
    with res_col1:
        if st.button("✅ WIN", use_container_width=True): 
            st.session_state.wins += 1
            st.session_state.journal.append(f"{datetime.now()}: WIN on {target_symbol}")
    with res_col2:
        if st.button("❌ LOSS", use_container_width=True): 
            st.session_state.losses += 1
            st.session_state.journal.append(f"{datetime.now()}: LOSS on {target_symbol}")

with col_j2:
    if st.button("🚀 AI Strategy Verdict", use_container_width=True):
        if active_ai_key and m_data:
            client = genai.Client(api_key=active_ai_key)
            prompt = f"VERDICT: {target_symbol}. Signal: {m_data[1]}. Trend: {m_data[2]}. RS Status: {rs_status}. Context: Powell Probe. Max 50 words."
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            st.info(f"### 🤖 AI Verdict: {m_data[1]}")
            st.markdown(response.text)
