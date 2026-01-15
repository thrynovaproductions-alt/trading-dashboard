import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from google import genai
from google.genai import types
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import pytz

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="AI Trading Terminal", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. SIDEBAR: COMMAND CENTER ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# A. MARKET CLOCK
est = pytz.timezone('US/Eastern')
now_est = datetime.now(est)
curr_time_str = now_est.strftime("%H:%M:%S")
is_close_near = now_est.hour == 15 and now_est.minute >= 30
st.sidebar.subheader(f"🕒 Market Time (EST): {curr_time_str}")

# B. POSITION SIZING
acc_balance = st.sidebar.number_input("Account Balance ($)", value=10000)
risk_percent = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.0)
risk_dollars = acc_balance * (risk_percent / 100)

# C. API & PERFORMANCE
manual_key = st.sidebar.text_input("Temporary API Key Override:", type="password")
active_key = manual_key if manual_key else st.secrets.get("GEMINI_API_KEY", "")

total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total Trades: {total_trades}")

# D. VITALS (DXY, Gold, VIX)
def get_vitals_safe():
    try:
        vix_df = yf.download("^VIX", period="1d", interval="1m", progress=False, multi_level_index=False)
        dxy_df = yf.download("DX-Y.NYB", period="1d", interval="1m", progress=False, multi_level_index=False)
        gold_df = yf.download("GC=F", period="1d", interval="1m", progress=False, multi_level_index=False)
        return vix_df['Close'].iloc[-1], dxy_df['Close'].iloc[-1], gold_df['Close'].iloc[-1]
    except: return 0.0, 0.0, 0.0

vix_val, dxy_val, gold_val = get_vitals_safe()
st.sidebar.metric("VIX", f"{vix_val:.2f}"); st.sidebar.metric("Gold", f"${gold_val:.2f}"); st.sidebar.metric("DXY", f"{dxy_val:.2f}")

# E. TREND MATRIX
def get_trend(symbol, interval, period):
    try:
        data = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
        sma_short = data['Close'].rolling(9).mean().iloc[-1]
        sma_long = data['Close'].rolling(21).mean().iloc[-1]
        return "BULLISH" if sma_short > sma_long else "BEARISH"
    except: return "Neutral"

target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])
trend_1h = get_trend(target, '1h', '5d')

st.sidebar.divider()
sentiment_trend = st.sidebar.select_slider("Headline Sentiment", options=["Cooling", "Neutral", "Heating Up", "Explosive"], value="Heating Up")
event_alert = st.sidebar.toggle("🚨 SYSTEMIC EVENT ALERTS", value=True)

# --- 4. THE MONITOR & 5-TIER SIGNAL LOGIC ---
@st.fragment(run_every=60)
def monitor_market():
    df = yf.download(target, period="2d", interval="5m", multi_level_index=False)
    if not df.empty:
        # Data Integrity Check
        last_candle_time = df.index[-1].to_pydatetime().replace(tzinfo=pytz.utc)
        lag = (datetime.now(pytz.utc) - last_candle_time).total_seconds()
        st.caption(f"🟢 Data Integrity: {int(lag)}s lag")

        df['VWAP'] = ((df['High'] + df['Low'] + df['Close'])/3 * df['Volume']).cumsum() / df['Volume'].cumsum()
        last_price = df['Close'].iloc[-1]
        vwap_val = df['VWAP'].iloc[-1]
        
        # --- 5-TIER SIGNAL REINSTATEMENT ---
        chop_buffer = (df['High'].tail(10) - df['Low'].tail(10)).mean() * 0.3
        
        if abs(last_price - vwap_val) < chop_buffer:
            sig_str = "WAIT ⏳ (Neutral Zone)"
        elif last_price > vwap_val:
            sig_str = "STRONG LONG 🚀" if trend_1h == "BULLISH" else "WEAK LONG ⚠️"
        else:
            sig_str = "STRONG SHORT 📉" if trend_1h == "BEARISH" else "WEAK SHORT ⚠️"

        # Risk Shield
        vol_range = (df['High'].tail(10) - df['Low'].tail(10)).mean()
        sl_buffer = vol_range * 1.5
        sl_l = last_price - sl_buffer; tp_l = last_price + (sl_buffer * 3)
        sl_s = last_price + sl_buffer; tp_s = last_price - (sl_buffer * 3)
        
        # Position Size
        micro_pt = 2 if "NQ" in target else 5
        m_qty = risk_dollars / (abs(last_price - sl_l) * micro_pt) if abs(last_price - sl_l) > 0 else 0

        st.subheader(f"🚀 {target}: {last_price:.2f} | {sig_str}")
        
        c1, c2 = st.columns(2)
        with c1: st.success(f"🟢 LONG: TP {tp_l:.2f} | SL {sl_l:.2f} | Size: {m_qty:.1f}")
        with c2: st.error(f"🔴 SHORT: TP {tp_s:.2f} | SL {sl_s:.2f} | Size: {m_qty:.1f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, df.tail(10).to_string(), sig_str, tp_l, sl_l, tp_s, sl_s, lag
    return None, None, None, None, None, None, None, None

last_p, momentum_d, sig_str, tp_l, sl_l, tp_s, sl_s, lag = monitor_market()

# --- 5. RESULT LOGGER & AI ENGINE ---
st.divider()
st.subheader("🏁 Trade Logger & AI Instant Verdict")
res_col1, res_col2, res_col3 = st.columns(3)
with res_col1:
    if st.button("✅ WIN", use_container_width=True): st.session_state.wins += 1; st.balloons()
with res_col2:
    if st.button("❌ LOSS", use_container_width=True): st.session_state.losses += 1
with res_col3:
    if st.button("🔄 Reset", use_container_width=True): st.session_state.wins = 0; st.session_state.losses = 0

if st.button("🚀 Generate Instant Verdict", use_container_width=True):
    if active_key:
        try:
            client = genai.Client(api_key=active_key)
            prompt = f"FAST VERDICT: {target} at {last_p}. Data Lag: {lag}s. Signal: {sig_str}. Momentum: {momentum_d}. News: Powell Probe. Verdict (L/S/Wait), Max 50 words."
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
            st.info(f"### 🤖 AI Verdict: {sig_str}")
            st.markdown(response.text)
        except Exception as e: st.error(f"AI Error: {e}")

# Download
log_c = f"WIN RATE: {win_rate}%\nSIGNAL: {sig_str}"
st.download_button("📁 Download Log", data=log_c, file_name=f"QuantLog.txt", use_container_width=True)
