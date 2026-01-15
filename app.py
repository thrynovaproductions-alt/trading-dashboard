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
st.set_page_config(layout="wide", page_title="NQ & ES Quant Workstation", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. SIDEBAR: THE RECOGNIZABLE COMMAND CENTER ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# A. API HEALTH & CREDIT GUARD
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

# B. MULTI-TIMEFRAME TREND MATRIX
st.sidebar.divider()
st.sidebar.subheader("Multi-Timeframe Trend")

def get_trend_status(symbol, interval):
    try:
        td = TDClient(apikey=active_twelve_key)
        ts = td.time_series(symbol=symbol, interval=interval, outputsize=30).as_pandas()
        sma9 = ts['close'].rolling(9).mean().iloc[-1]
        sma21 = ts['close'].rolling(21).mean().iloc[-1]
        return "BULLISH 🟢" if sma9 > sma21 else "BEARISH 🔴"
    except: return "Neutral ⚪"

# Asset Selector
asset_map = {"Nasdaq (QQQ)": "QQQ", "S&P 500 (SPY)": "SPY"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

st.sidebar.write(f"1-Hour: {get_trend_status(target_symbol, '1h')}")
st.sidebar.write(f"Daily: {get_trend_status(target_symbol, '1day')}")

# C. PERFORMANCE TRACKER
total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total: {total_trades}")

# --- 4. MAIN INTERFACE: WORKSTATION HEADER ---
st.title(f"🚀 {target_label} Quant Workstation")

# D. SYSTEMIC ALERTS
sentiment_trend = st.sidebar.select_slider("Headline Sentiment", options=["Cooling", "Neutral", "Heating Up", "Explosive"], value="Heating Up")
if sentiment_trend in ["Heating Up", "Explosive"]:
    st.error(f"**🚨 SYSTEMIC RISK ALERT: FED INDEPENDENCE CRISIS** - Sentiment: **{sentiment_trend}**.")

# --- 5. THE MONITOR & 5-TIER SIGNAL ENGINE ---
@st.fragment(run_every=60)
def monitor_market():
    if not active_twelve_key:
        st.warning("Enter Twelve Data API Key in Sidebar.")
        return None
    
    try:
        td = TDClient(apikey=active_twelve_key)
        df = td.time_series(symbol=target_symbol, interval="5min", outputsize=50).as_pandas()
        df.index = pd.to_datetime(df.index)
        
        # Data Integrity Check
        last_candle_time = df.index[0].to_pydatetime().replace(tzinfo=pytz.utc)
        lag = (datetime.now(pytz.utc) - last_candle_time).total_seconds()
        st.caption(f"⚡ Data Integrity: {int(lag)}s lag")

        # 5-Tier Signal Logic
        last_price = df['close'].iloc[0]
        vwap_val = (df['close'] * df['volume']).cumsum().iloc[0] / df['volume'].cumsum().iloc[0]
        vol_ref = (df['high'].head(10) - df['low'].head(10)).mean()
        chop_buffer = vol_ref * 0.3
        
        trend_1h = get_trend_status(target_symbol, '1h')
        
        if abs(last_price - vwap_val) < chop_buffer:
            sig_str = "WAIT ⏳"
        elif last_price > vwap_val:
            sig_str = "STRONG LONG 🚀" if "BULLISH" in trend_1h else "WEAK LONG ⚠️"
        else:
            sig_str = "STRONG SHORT 📉" if "BEARISH" in trend_1h else "WEAK SHORT ⚠️"

        # Risk Shield (2:1 Ratio)
        sl_buffer = vol_ref * 1.5
        sl_l = last_price - sl_buffer; tp_l = last_price + (sl_buffer * 3)
        sl_s = last_price + sl_buffer; tp_s = last_price - (sl_buffer * 3)

        st.subheader(f"Current Signal: {sig_str}")
        
        col1, col2 = st.columns(2)
        with col1: st.success(f"🟢 LONG: TP {tp_l:.2f} | SL {sl_l:.2f}")
        with col2: st.error(f"🔴 SHORT: TP {tp_s:.2f} | SL {sl_s:.2f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['close'].rolling(20).mean(), line=dict(color='cyan', dash='dash'), name="VWAP Proxy"))
        fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, sig_str, lag
    except Exception as e:
        st.error(f"Application Error: {e}")
        return None

m_data = monitor_market()

# --- 6. AI VERDICT & LOGGING ---
st.divider()
if st.button("Analyze Current Setup", use_container_width=True):
    if active_ai_key and m_data:
        client = genai.Client(api_key=active_ai_key)
        prompt = f"VERDICT: {target_symbol} at {m_data[0]}. Signal: {m_data[1]}. Lag: {m_data[2]}s. Risk: {sentiment_trend}. Max 50 words."
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        st.info(f"### 🤖 AI Strategy Verdict")
        st.markdown(response.text)

# Result Buttons
res_col1, res_col2 = st.columns(2)
with res_col1:
    if st.button("✅ HIT TARGET", use_container_width=True): st.session_state.wins += 1; st.balloons()
with res_col2:
    if st.button("❌ HIT STOP-LOSS", use_container_width=True): st.session_state.losses += 1
