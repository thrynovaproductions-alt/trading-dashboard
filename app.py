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

# --- 1. CORE CONFIGURATION (Restores Original Look) ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Workstation", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. SIDEBAR: RECOGNIZABLE COMMAND CENTER ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# API Health Section
st.sidebar.subheader("🔌 API Health")
twelve_key = st.sidebar.text_input("Twelve Data Key:", type="password")
gemini_key = st.sidebar.text_input("Gemini Key Override:", type="password")

active_twelve_key = twelve_key if twelve_key else st.secrets.get("TWELVE_DATA_API_KEY", "")
active_gemini_key = gemini_key if gemini_key else st.secrets.get("GEMINI_API_KEY", "")

def get_api_usage(key):
    try:
        if not key: return 0, "Unknown"
        url = f"https://api.twelvedata.com/api_usage?apikey={key}"
        res = requests.get(url).json()
        return res.get('credits_used', 0), res.get('credits_left', 'Unknown')
    except: return 0, "N/A"

used, left = get_api_usage(active_twelve_key)
st.sidebar.write(f"Credits Used: {used} | Left: {left}")

# Multi-Timeframe Trend (Matches Original Image)
st.sidebar.divider()
st.sidebar.subheader("Multi-Timeframe Trend")

asset_map = {"NQ=F": "QQQ", "ES=F": "SPY", "Nasdaq (QQQ)": "QQQ"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

def get_trend_status(symbol, interval):
    try:
        td = TDClient(apikey=active_twelve_key)
        ts = td.time_series(symbol=symbol, interval=interval, outputsize=30).as_pandas()
        sma9, sma21 = ts['close'].rolling(9).mean().iloc[-1], ts['close'].rolling(21).mean().iloc[-1]
        return "BULLISH 🟢" if sma9 > sma21 else "BEARISH 🔴"
    except: return "Neutral ⚪"

st.sidebar.write(f"1-Hour: {get_trend_status(target_symbol, '1h')}")
st.sidebar.write(f"Daily: {get_trend_status(target_symbol, '1day')}")

# Performance Logger
st.sidebar.divider()
total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0.0
st.sidebar.subheader(f"Win Rate: {win_rate:.1f}%")
st.sidebar.write(f"Total Trades: {total_trades}")

headline_sentiment = st.sidebar.select_slider("Headline Sentiment", options=["Cooling", "Neutral", "Heating Up", "Explosive"], value="Heating Up")

# --- 4. MAIN INTERFACE (Restores Original UI Flow) ---
st.title(f"🚀 {target_label} Quant Workstation")

# Systemic Alert Bar
if headline_sentiment in ["Heating Up", "Explosive"]:
    st.error(f"🚨 **SYSTEMIC RISK ALERT: FED INDEPENDENCE CRISIS** - Sentiment: {headline_sentiment}")

@st.fragment(run_every=60)
def monitor_market():
    if not active_twelve_key:
        st.info("💡 Please enter your Twelve Data Key in the sidebar to load the live chart.")
        return None
    
    try:
        td = TDClient(apikey=active_twelve_key)
        df = td.time_series(symbol=target_symbol, interval="5min", outputsize=100).as_pandas()
        df.index = pd.to_datetime(df.index)
        
        # Original Indicators
        last_price = df['close'].iloc[0]
        vwap = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        
        # 5-Tier Strength Logic
        vol = (df['high'].head(10) - df['low'].head(10)).mean()
        if abs(last_price - vwap.iloc[0]) < (vol * 0.3):
            sig_str = "WAIT ⏳"
        else:
            sig_str = "STRONG LONG 🚀" if last_price > vwap.iloc[0] else "STRONG SHORT 📉"

        # Signal Header
        st.subheader(f"Current Signal: {sig_str} | Price: {last_price:.2f}")

        # Main Workstation Chart
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=vwap, line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, sig_str
    except Exception as e:
        st.error(f"Data Error: {e}")
        return None

m_data = monitor_market()

# Analyze Button & Trade Logs (Matches UI positions)
st.divider()
if st.button("Analyze Current Setup", use_container_width=True):
    if active_gemini_key and m_data:
        client = genai.Client(api_key=active_gemini_key)
        prompt = f"VERDICT: {target_label} at {m_data[0]}. Signal: {m_data[1]}. Risk: {headline_sentiment}. Max 50 words."
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        st.info(f"### 🤖 AI Strategy Verdict")
        st.markdown(response.text)

c1, c2 = st.columns(2)
with c1:
    if st.button("✅ HIT TARGET", use_container_width=True): st.session_state.wins += 1; st.balloons()
with c2:
    if st.button("❌ HIT STOP-LOSS", use_container_width=True): st.session_state.losses += 1
