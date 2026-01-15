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
st.set_page_config(layout="wide", page_title="AI Trading Terminal", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. API MONITORING & HEALTH ---
def get_api_usage(key):
    try:
        if not key: return 0, "N/A"
        url = f"https://api.twelvedata.com/api_usage?apikey={key}"
        res = requests.get(url).json()
        return res.get('credits_used', 0), res.get('credits_left', 'Unknown')
    except:
        return 0, "N/A"

# --- 4. SIDEBAR: COMMAND CENTER ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# A. API MANAGEMENT
st.sidebar.subheader("🔌 API Health")
twelve_key = st.sidebar.text_input("Twelve Data Key:", type="password")
ai_key = st.sidebar.text_input("Gemini Key Override:", type="password")

active_twelve_key = twelve_key if twelve_key else st.secrets.get("TWELVE_DATA_API_KEY", "")
active_ai_key = ai_key if ai_key else st.secrets.get("GEMINI_API_KEY", "")

used, left = get_api_usage(active_twelve_key)
st.sidebar.write(f"Credits Used: {used}")
st.sidebar.write(f"Credits Left: {left}")

# B. AUTO-REFRESH & PERFORMANCE
auto_refresh = st.sidebar.toggle("Auto-Refresh Data (60s)", value=True)
total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total: {total_trades}")

# C. MARKET VITALS
def get_vitals():
    try:
        td = TDClient(apikey=active_twelve_key)
        vix = td.time_series(symbol="VIX", interval="1min", outputsize=1).as_pandas().iloc[0]['close']
        dxy = td.time_series(symbol="DXY", interval="1min", outputsize=1).as_pandas().iloc[0]['close']
        gold = yf.download("GC=F", period="1d", interval="1m", progress=False, multi_level_index=False)['Close'].iloc[-1]
        return float(vix), float(dxy), float(gold)
    except:
        return 0.0, 0.0, 0.0

v_val, d_val, g_val = get_vitals()
st.sidebar.metric("VIX (Real-Time)", f"{v_val:.2f}")
st.sidebar.metric("Gold", f"${g_val:.2f}")

# D. SYMBOL MAPPING & TREND
asset_map = {"NQ (Nasdaq 100)": "NDX", "ES (S&P 500)": "SPX"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

def get_trend_twelve(symbol):
    try:
        td = TDClient(apikey=active_twelve_key)
        ts = td.time_series(symbol=symbol, interval="1h", outputsize=30).as_pandas()
        sma9, sma21 = ts['close'].rolling(9).mean().iloc[-1], ts['close'].rolling(21).mean().iloc[-1]
        return "BULLISH" if sma9 > sma21 else "BEARISH"
    except: return "Neutral"

trend_1h = get_trend_twelve(target_symbol)
st.sidebar.write(f"1-Hour Trend ({target_symbol}): {trend_1h}")

st.sidebar.divider()
sentiment_trend = st.sidebar.select_slider("Headline Sentiment", options=["Cooling", "Neutral", "Heating Up", "Explosive"], value="Heating Up")

# --- 5. THE MONITOR & 5-TIER SIGNAL LOGIC ---
refresh_rate = 60 if auto_refresh else None

@st.fragment(run_every=refresh_rate)
def monitor_market():
    if not active_twelve_key:
        st.warning("Enter Twelve Data API Key in sidebar.")
        return None
    
    try:
        td = TDClient(apikey=active_twelve_key)
        df = td.time_series(symbol=target_symbol, interval="5min", outputsize=50).as_pandas()
        df.index = pd.to_datetime(df.index)
        
        last_price = df['close'].iloc[0]
        vwap_last = (df['close'] * df['volume']).cumsum().iloc[0] / df['volume'].cumsum().iloc[0]
        
        # 5-Tier Signal Strength
        chop_buffer = (df['high'].head(10) - df['low'].head(10)).mean() * 0.3
        if abs(last_price - vwap_last) < chop_buffer:
            sig_str = "WAIT ⏳"
        elif last_price > vwap_last:
            sig_str = "STRONG LONG 🚀" if trend_1h == "BULLISH" else "WEAK LONG ⚠️"
        else:
            sig_str = "STRONG SHORT 📉" if trend_1h == "BEARISH" else "WEAK SHORT ⚠️"

        # Risk Shield
        sl_buffer = (df['high'].head(10) - df['low'].head(10)).mean() * 1.5
        sl_l = last_price - sl_buffer; tp_l = last_price + (sl_buffer * 3)
        sl_s = last_price + sl_buffer; tp_s = last_price - (sl_buffer * 3)

        st.subheader(f"🚀 {target_label} Live: {last_price:.2f} | {sig_str}")
        
        c1, c2 = st.columns(2)
        with c1: st.success(f"🟢 LONG: TP {tp_l:.2f} | SL {sl_l:.2f}")
        with c2: st.error(f"🔴 SHORT: TP {tp_s:.2f} | SL {sl_s:.2f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
        fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, df.head(10).to_string(), sig_str
    except Exception as e:
        st.error(f"Data Error: {e}")
        return None

m_data = monitor_market()
if m_data:
    lp, mom, ss = m_data

# --- 6. AI & LOGGING ---
st.divider()
if st.button("🚀 Generate AI Verdict", use_container_width=True):
    if active_ai_key:
        client = genai.Client(api_key=active_ai_key)
        prompt = f"VERDICT: {target_label} at {lp}. Signal: {ss}. Context: Powell Probe. Max 50 words."
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        st.info(f"### 🤖 AI Verdict: {ss}")
        st.markdown(response.text)

res_col1, res_col2 = st.columns(2)
with res_col1:
    if st.button("✅ WIN", use_container_width=True): st.session_state.wins += 1; st.balloons()
with res_col2:
    if st.button("❌ LOSS", use_container_width=True): st.session_state.losses += 1
