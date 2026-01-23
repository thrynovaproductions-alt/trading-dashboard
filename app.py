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
    """Fetch macro and sector data"""
    try:
        tickers = ["XLK", "XLU", "XLF", "^TNX", "^VIX", "NQ=F", "ES=F"]
        data = yf.download(tickers, period="2d", interval="5m", progress=False, multi_level_index=False)['Close']
        perf = {k: ((data[v].iloc[-1] - data[v].iloc[0]) / data[v].iloc[0]) * 100 for k, v in {"Tech": "XLK", "Def": "XLU", "Fin": "XLF"}.items()}
        rs_ratio = data["NQ=F"] / data["ES=F"]
        rs_change = ((rs_ratio.iloc[-1] - rs_ratio.iloc[0]) / rs_ratio.iloc[0]) * 100
        return perf, data["^VIX"].iloc[-1], data["^TNX"].iloc[-1], rs_change
    except: return {}, 0.0, 0.0, 0.0

# --- 2. PERSISTENT STATE ---
defaults = {'wins': 0, 'losses': 0, 'trade_log': [], 'total_pnl': 0.0}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 3. SIDEBAR: RISK & TREND ---
st.sidebar.title("🛡️ Risk Management")
active_google_key = st.secrets.get("GEMINI_API_KEY", "")
if not active_google_key:
    active_google_key = st.sidebar.text_input("Gemini API Key:", type="password")

account_size = st.sidebar.number_input("Account Balance ($)", value=50000)
risk_pct = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0) / 100

st.sidebar.divider()
st.sidebar.subheader("🔥 Trend Heatmap")
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

# --- 4. ANALYTICS FUNCTIONS ---
def calculate_vwap_metrics(df):
    if df.empty or len(df) < 21: return None
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
    df['Vol_Avg'] = df['Volume'].rolling(20).mean() # Volume Moving Average
    
    delta = df['Close'].diff()
    gain, loss = (delta.where(delta > 0, 0)).rolling(14).mean(), (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    return df, ((df['Close'].iloc[-1] - df['VWAP'].iloc[-1]) / df['VWAP'].iloc[-1]) * 100

# --- 5. MAIN INTERFACE ---
st.title("🚀 NQ & ES Quantitative Trading Platform")
sectors, vix, tnx, rs_lead = get_market_pulse()

@st.fragment(run_every=60)
def main_monitor():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        metrics_data = calculate_vwap_metrics(df)
        if metrics_data:
            df, dev = metrics_data
            last_p, last_rsi, last_vol = df['Close'].iloc[-1], df['RSI'].iloc[-1], df['Volume'].iloc[-1]
            vol_avg = df['Vol_Avg'].iloc[-1]

            # CLIMAX ALERT SYSTEM
            if last
