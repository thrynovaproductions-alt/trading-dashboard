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
import yfinance as yf # Kept as secondary fallback

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="AI Trading Terminal", initial_sidebar_state="collapsed")

# --- 2. API & PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# API Management
st.sidebar.subheader("🔑 API Management")
twelve_key = st.sidebar.text_input("Twelve Data API Key:", type="password", help="Get at twelvedata.com")
ai_key = st.sidebar.text_input("Gemini API Key Override:", type="password")

active_twelve_key = twelve_key if twelve_key else st.secrets.get("TWELVE_DATA_API_KEY", "")
active_ai_key = ai_key if ai_key else st.secrets.get("GEMINI_API_KEY", "")

# --- 3. SIDEBAR: MONITOR & VITALS ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# Twelve Data Client Initialization
td = TDClient(apikey=active_twelve_key)

def get_vitals_twelve():
    try:
        # Fetching VIX and DXY via Twelve Data for lower lag
        vix = td.time_series(symbol="VIX", interval="1min", outputsize=1).as_pandas().iloc[0]['close']
        dxy = td.time_series(symbol="DXY", interval="1min", outputsize=1).as_pandas().iloc[0]['close']
        # Gold often requires yfinance fallback on free tiers
        gold = yf.download("GC=F", period="1d", interval="1m", progress=False, multi_level_index=False)['Close'].iloc[-1]
        return float(vix), float(dxy), float(gold)
    except:
        return 0.0, 0.0, 0.0

v_val, d_val, g_val = get_vitals_twelve()
st.sidebar.metric("VIX (Real-Time)", f"{v_val:.2f}")
st.sidebar.metric("Gold", f"${g_val:.2f}")
st.sidebar.metric("DXY", f"{d_val:.2f}")

# Trend Matrix (1H)
def get_trend_twelve(symbol):
    try:
        ts = td.time_series(symbol=symbol, interval="1h", outputsize=30).as_pandas()
        sma9 = ts['close'].rolling(9).mean().iloc[-1]
        sma21 = ts['close'].rolling(21).mean().iloc[-1]
        return "BULLISH" if sma9 > sma21 else "BEARISH"
    except: return "Neutral"

target = st.sidebar.selectbox("Market Asset", ["NQ", "ES"]) # Twelve Data uses symbols without =F
trend_1h = get_trend_twelve(target)
st.sidebar.write(f"1-Hour Trend: {trend_1h}")

# --- 4. THE MONITOR & HIGH-FIDELITY DATA ---
@st.fragment(run_every=60)
def monitor_market_twelve():
    if not active_twelve_key:
        st.warning("Please enter your Twelve Data API key to start live tracking.")
        return None
    
    try:
        # High-Fidelity 5m stream
        df = td.time_series(symbol=target, interval="5min", outputsize=50).as_pandas()
        df.index = pd.to_datetime(df.index)
        
        # Data Integrity Check
        last_candle_time = df.index[0].to_pydatetime().replace(tzinfo=pytz.utc)
        lag = (datetime.now(pytz.utc) - last_candle_time).total_seconds()
        st.caption(f"⚡ Twelve Data Integrity: {int(lag)}s lag")

        # Calculations
        last_price = df['close'].iloc[0]
        vwap_val = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        vwap_last = vwap_val.iloc[0]
        
        # Signal Logic
        chop_buffer = (df['high'].head(10) - df['low'].head(10)).mean() * 0.3
        if abs(last_price - vwap_last) < chop_buffer:
            sig_str = "WAIT ⏳"
        elif last_price > vwap_last:
            sig_str = "STRONG LONG 🚀" if trend_1h == "BULLISH" else "WEAK LONG ⚠️"
        else:
            sig_str = "STRONG SHORT 📉" if trend_1h == "BEARISH" else "WEAK SHORT ⚠️"

        # Risk Shield
        vol_range = (df['high'].head(10) - df['low'].head(10)).mean()
        sl_buffer = vol_range * 1.5
        sl_l = last_price - sl_buffer; tp_l = last_price + (sl_buffer * 3)
        sl_s = last_price + sl_buffer; tp_s = last_price - (sl_buffer * 3)

        st.subheader(f"🚀 {target} Live (12Data): {last_price:.2f} | {sig_str}")
        
        c1, c2 = st.columns(2)
        with c1: st.success(f"🟢 LONG: TP {tp_l:.2f} | SL {sl_l:.2f}")
        with c2: st.error(f"🔴 SHORT: TP {tp_s:.2f} | SL {sl_s:.2f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
        fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, df.head(10).to_string(), sig_str, lag
    except Exception as e:
        st.error(f"Data Connection Error: {e}")
        return None

# Execution
market_data = monitor_market_twelve()
if market_data:
    last_p, momentum_d, sig_str, lag = market_data

# --- 5. LOGGING & AI VERDICT (Maintains All Gains) ---
st.divider()
if st.button("🚀 Generate Instant AI Verdict", use_container_width=True):
    if active_ai_key:
        client = genai.Client(api_key=active_ai_key)
        prompt = f"FAST VERDICT: {target} at {last_p}. Lag: {lag}s. Signal: {sig_str}. Context: Powell Probe. Max 50 words."
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
        st.info(f"### 🤖 AI Verdict: {sig_str}")
        st.markdown(response.text)

# Performance Tracker Buttons (Maintains Gain)
res_col1, res_col2 = st.columns(2)
with res_col1:
    if st.button("✅ WIN", use_container_width=True): st.session_state.wins += 1; st.balloons()
with res_col2:
    if st.button("❌ LOSS", use_container_width=True): st.session_state.losses += 1
