import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from google import genai
from google.genai import types
from datetime import datetime
import yfinance as yf

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Workstation", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. SIDEBAR: RECOGNIZABLE COMMAND CENTER ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# AI Authentication: Auto-load from Secrets
active_google_key = st.secrets.get("GEMINI_API_KEY", "")
if not active_google_key:
    st.sidebar.subheader("🔌 AI Authentication")
    google_key_input = st.sidebar.text_input("Paste Google AI Key:", type="password")
    active_google_key = google_key_input
else:
    st.sidebar.success("✅ AI Engine Authenticated")

# Multi-Timeframe Trend
st.sidebar.divider()
st.sidebar.subheader("Multi-Timeframe Trend")
asset_map = {"NQ=F (Nasdaq)": "NQ=F", "ES=F (S&P 500)": "ES=F"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

def get_trend_status(symbol, period, interval):
    try:
        data = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
        if data.empty: return "Neutral ⚪"
        sma9, sma21 = data['Close'].rolling(9).mean().iloc[-1], data['Close'].rolling(21).mean().iloc[-1]
        return "BULLISH 🟢" if sma9 > sma21 else "BEARISH 🔴"
    except: return "Neutral ⚪"

st.sidebar.write(f"1-Hour: {get_trend_status(target_symbol, '5d', '1h')}")
st.sidebar.write(f"Daily: {get_trend_status(target_symbol, '1mo', '1d')}")

# Performance Logger
st.sidebar.divider()
total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0.0
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total: {total_trades}")

# --- 4. PREDICTIVE SHADOW HEADER ---
st.title(f"🚀 {target_label} Quant Workstation")

def get_shadow_data(target):
    # Map Futures to their ETF "Shadows"
    shadow_map = {"NQ=F": "QQQ", "ES=F": "SPY"}
    shadow_ticker = shadow_map.get(target, "QQQ")
    try:
        # Pull 1-minute real-time data for the shadow
        s_data = yf.download(shadow_ticker, period="1d", interval="1m", progress=False, multi_level_index=False)
        return s_data['Close'].iloc[-1], shadow_ticker
    except: return 0.0, "N/A"

shadow_price, shadow_name = get_shadow_data(target_symbol)

# Mitigation Dashboard
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    st.metric(f"Real-Time {shadow_name} (Shadow)", f"${shadow_price:.2f}", help="ETFs often update faster than free Futures data.")
with c2:
    st.write("📊 **Mitigation Strategy:**")
    st.caption("If Shadow moves while Chart is flat, anticipate a Catch-Up move.")

# --- 5. THE MONITOR & 5-TIER SIGNAL ENGINE ---
@st.fragment(run_every=60)
def monitor_market():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        if df.empty: return None
        
        # 5-Tier Signal Logic
        last_price = df['Close'].iloc[-1]
        sma9 = df['Close'].rolling(9).mean().iloc[-1]
        sma21 = df['Close'].rolling(21).mean().iloc[-1]
        df['VWAP'] = ((df['High'] + df['Low'] + df['Close'])/3 * df['Volume']).cumsum() / df['Volume'].cumsum()
        vwap_val = df['VWAP'].iloc[-1]
        
        vol = (df['High'].tail(10) - df['Low'].tail(10)).mean()
        trend = "BULLISH" if sma9 > sma21 else "BEARISH"
        
        if abs(last_price - vwap_val) < (vol * 0.3):
            sig_str = "WAIT ⏳"
        elif last_price > vwap_val:
            sig_str = "STRONG LONG 🚀" if trend == "BULLISH" else "WEAK LONG ⚠️"
        else:
            sig_str = "STRONG SHORT 📉" if trend == "BEARISH" else "WEAK SHORT ⚠️"

        st.subheader(f"Current Signal: {sig_str} | Price: {last_price:.2f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low
