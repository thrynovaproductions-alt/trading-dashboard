import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from google import genai
from google.genai import types
import streamlit.components.v1 as components
from datetime import datetime

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="AI Trading Terminal", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE (Win-Rate Tracking) ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. SIDEBAR: ALL INDICATORS ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# A. API MANAGEMENT
st.sidebar.subheader("🔑 API Management")
manual_key = st.sidebar.text_input("Temporary API Key Override:", type="password")
active_key = manual_key if manual_key else st.secrets.get("GEMINI_API_KEY", "")

# B. PERFORMANCE TRACKER
total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0
st.sidebar.subheader("📈 Performance Tracker")
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total Trades: {total_trades}")

# C. INDEPENDENCE TRACKER & VITALS
def get_vitals_safe():
    try:
        vix_df = yf.download("^VIX", period="1d", interval="1m", progress=False, multi_level_index=False)
        dxy_df = yf.download("DX-Y.NYB", period="1d", interval="1m", progress=False, multi_level_index=False)
        gold_df = yf.download("GC=F", period="1d", interval="1m", progress=False, multi_level_index=False)
        vix = vix_df['Close'].iloc[-1] if not vix_df.empty else 0.0
        dxy = dxy_df['Close'].iloc[-1] if not dxy_df.empty else 0.0
        gold = gold_df['Close'].iloc[-1] if not gold_df.empty else 0.0
        return vix, dxy, gold
    except: return 0.0, 0.0, 0.0

vix_val, dxy_val, gold_val = get_vitals_safe()
st.sidebar.subheader("📊 Market Vitals")
st.sidebar.metric("Fear Index (VIX)", f"{vix_val:.2f}")
st.sidebar.metric("Gold (GC=F)", f"${gold_val:.2f}")
st.sidebar.metric("US Dollar (DXY)", f"{dxy_val:.2f}")

# D. TREND MATRIX
def get_trend(symbol, interval, period):
    try:
        data = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
        if len(data) < 20: return "Neutral"
        sma_short = data['Close'].rolling(9).mean().iloc[-1]
        sma_long = data['Close'].rolling(21).mean().iloc[-1]
        return "BULLISH 🟢" if sma_short > sma_long else "BEARISH 🔴"
    except: return "Offline ⚪"

st.sidebar.subheader("🌐 Technical Matrix")
target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])
st.sidebar.write(f"1-Hour Trend: {get_trend(target, '1h', '5d')}")
st.sidebar.write(f"Daily Trend: {get_trend(target, '1d', '1mo')}")

# E. SENTIMENT SLIDER & ALERTS
st.sidebar.divider()
sentiment_trend = st.sidebar.select_slider("Headline Sentiment", options=["Cooling", "Neutral", "Heating Up", "Explosive"], value="Heating Up")
event_alert = st.sidebar.toggle("🚨 SYSTEMIC EVENT ALERTS", value=True)

# --- 4. MAIN INTERFACE: RISK ALERTS ---
if event_alert:
    st.error(f"**🚨 SYSTEMIC RISK ALERT: FED INDEPENDENCE CRISIS** - News is currently **{sentiment_trend}**. High risk of liquidity shocks.")

# --- 5. THE REFRESHING MONITOR & RISK SHIELD ---
@st.fragment(run_every=60)
def monitor_market():
    df = yf.download(target, period="2d", interval="5m", multi_level_index=False)
    if not df.empty:
        df['VWAP'] = ((df['High'] + df['Low'] + df['Close'])/3 * df['Volume']).cumsum() / df['Volume'].cumsum()
        last_price = df['Close'].iloc[-1]
        
        # Risk Shield Logic (Stop-Loss & Profit Target)
        recent_10 = df.tail(10)
        volatility_range = (recent_10['High'] - recent_10['Low']).mean()
        sl_buffer = volatility_range * 1.5
        
        sl_long = last_price - sl_buffer
        tp_long = last_price + (sl_buffer * 2) # 2:1 Reward
        sl_short = last_price + sl_buffer
        tp_short = last_price - (sl_buffer * 2)
        
        st.subheader(f"🚀 {target} Live: {last_price:.2f}")
        
        # Risk Dashboard UI
        c1, c2 = st.columns(2)
        with c1: st.success(f"🟢 LONG: Target {tp_long:.2f} | SL {sl_long:.2f}")
        with c2: st.error(f"🔴 SHORT: Target {tp_short:.2f} | SL {sl_short:.2f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, recent_10.to_string(), tp_long, sl_long, tp_short, sl_short
    return None, None, None, None, None, None

last_price, momentum_data, calc_tp_long, calc_sl_long, calc_tp_short, calc_sl_short = monitor_market()

# --- 6. TRADE RESULT LOGGER ---
st.divider()
st.subheader("🏁 Trade Result Logger")
res_col1, res_col2, res_col3 = st.columns(3)
with res_col1:
    if st.button("✅ HIT TARGET (Win)", use_container_width=True):
        st.session_state.wins += 1
        st.balloons()
with res_col2:
    if st.button("❌ HIT STOP-LOSS (Loss)", use_container_width=True):
        st.session_state.losses += 1
with res_col3:
    if st.button("🔄 Reset Performance", use_container_width=True):
        st.session_state.wins = 0
        st.session_state.losses = 0

# --- 7. AI STRATEGY ENGINE ---
st.divider()
st.subheader("📓 AI Analysis & Strategy")
headline_context = f"- EVENT: Powell Probe\n- PLAN: LONG TP {calc_tp_long:.2f} / SL {calc_sl_long:.2f}\n- VITALS: VIX {vix_val:.2f} | Gold {gold_val:.2f}"
trade_notes = st.text_area("Live Context:", value=headline_context, height=100)

if st.button("Generate Final AI Trade Plan", use_container_width=True):
    if active_key:
        try:
            client = genai.Client(api_key=active_key)
            prompt = f"Analyze {target}. VIX: {vix_val}. Sentiment: {sentiment_trend}. Gold: {gold_val}. Momentum: {momentum_data}. Recommend LONG/SHORT/WAIT with 2:1 RR justification."
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
            st.info("### 🤖 AI Trade Plan")
            st.markdown(response.text)
        except Exception as e: st.error(f"AI Error: {e}")

# Download
log_c = f"WIN RATE: {win_rate}%\nTRADES: {total_trades}\nPLAN: TP {calc_tp_long}/SL {calc_sl_long}"
st.download_button("📁 Download Detailed Strategy Log", data=log_c, file_name=f"QuantPerformance_Log.txt", use_container_width=True)
