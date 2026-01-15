import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import databento as db
from google import genai
from google.genai import types
from datetime import datetime, timedelta
import pytz

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Workstation", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. SIDEBAR: COMMAND CENTER ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# API Management
st.sidebar.subheader("🔌 API Health")
# Your Databento Key integrated as default
db_key = st.sidebar.text_input("Databento Key:", value="db-q97NCEbRyn7cLkWg6qPyjaWbpEfRn", type="password")
gemini_key = st.sidebar.text_input("Gemini Key Override:", type="password")

active_db_key = db_key if db_key else st.secrets.get("DATABENTO_API_KEY", "")
active_gemini_key = gemini_key if gemini_key else st.secrets.get("GEMINI_API_KEY", "")

# Multi-Timeframe Trend (Historical API Calls)
st.sidebar.divider()
st.sidebar.subheader("Multi-Timeframe Trend")

asset_map = {"NQ Futures": "NASD.NQ", "ES Futures": "CME.ES"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

def get_trend_status(symbol, key):
    try:
        client = db.Historical(key)
        # Fetching last hour of data to determine trend
        data = client.timeseries.get_range(dataset='GLBX.MDP3', symbols=symbol, schema='ohlcv-1h', start=(datetime.now() - timedelta(hours=24)))
        df = data.to_df()
        if len(df) < 2: return "Neutral ⚪"
        return "BULLISH 🟢" if df['close'].iloc[-1] > df['close'].iloc[-2] else "BEARISH 🔴"
    except: return "Connection ⚪"

st.sidebar.write(f"Trend Status: {get_trend_status(target_symbol, active_db_key)}")

# Backtest Lab & Performance
st.sidebar.divider()
st.sidebar.subheader("📊 Backtest & Optimizer Lab")
st.sidebar.button("Run Optimizer + Backtest", use_container_width=True)

total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0.0
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total: {total_trades}")

# --- 4. MAIN INTERFACE ---
st.title(f"🚀 {target_label} Quant Workstation")

headline_sentiment = st.sidebar.select_slider("Headline Sentiment", options=["Cooling", "Neutral", "Heating Up", "Explosive"], value="Heating Up")
if headline_sentiment in ["Heating Up", "Explosive"]:
    st.error(f"🚨 **SYSTEMIC RISK ALERT: FED INDEPENDENCE CRISIS** - Sentiment: {headline_sentiment}")

# Databento Market Monitoring
@st.fragment(run_every=60)
def monitor_market():
    if not active_db_key:
        st.info("💡 Enter Databento API Key to activate live stream.")
        return None, None
    
    try:
        client = db.Historical(active_db_key)
        # Fetching latest 5-minute bars
        end = datetime.now()
        start = end - timedelta(hours=4)
        data = client.timeseries.get_range(dataset='GLBX.MDP3', symbols=target_symbol, schema='ohlcv-5m', start=start, end=end)
        df = data.to_df()
        
        last_price = df['close'].iloc[-1]
        # Calculate VWAP
        df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        vwap_val = df['vwap'].iloc[-1]
        
        # 5-Tier Signal
        vol = (df['high'] - df['low']).tail(10).mean()
        if abs(last_price - vwap_val) < (vol * 0.3):
            sig_str = "WAIT ⏳"
        else:
            sig_str = "STRONG LONG 🚀" if last_price > vwap_val else "STRONG SHORT 📉"

        st.subheader(f"Current Signal: {sig_str} | Price: {last_price:.2f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['vwap'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, sig_str
    except Exception as e:
        st.error(f"Databento Connection Issue: {e}")
        return None, None

current_price, current_signal = monitor_market()

# --- 5. THE VERDICT & LOGGING ---
st.divider()
if st.button("Analyze Current Setup", use_container_width=True):
    if active_gemini_key and current_price:
        client = genai.Client(api_key=active_gemini_key)
        prompt = f"VERDICT: {target_label} at {current_price}. Signal: {current_signal}. Risk: {headline_sentiment}. Max 50 words."
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        st.info(f"### 🤖 AI Strategy Verdict")
        st.markdown(response.text)

c1, c2 = st.columns(2)
with c1:
    if st.button("✅ HIT TARGET", use_container_width=True): st.session_state.wins += 1; st.balloons()
with c2:
    if st.button("❌ HIT STOP-LOSS", use_container_width=True): st.session_state.losses += 1
