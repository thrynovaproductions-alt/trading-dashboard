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
import pytz

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="AI Trading Terminal", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. SIDEBAR: COMMAND CENTER ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# A. MARKET CLOCK & CLOSE WARNING
est = pytz.timezone('US/Eastern')
now_est = datetime.now(est)
curr_time_str = now_est.strftime("%H:%M:%S")
is_close_near = now_est.hour == 15 and now_est.minute >= 30

st.sidebar.subheader(f"🕒 Market Time (EST): {curr_time_str}")
if is_close_near:
    st.sidebar.warning("⚡ VOLATILE CLOSE: Use Extreme Caution")

# B. POSITION SIZING
st.sidebar.subheader("💰 Position Sizing")
acc_balance = st.sidebar.number_input("Account Balance ($)", value=10000)
risk_percent = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.0)
risk_dollars = acc_balance * (risk_percent / 100)

# C. API MANAGEMENT
manual_key = st.sidebar.text_input("Temporary API Key Override:", type="password")
active_key = manual_key if manual_key else st.secrets.get("GEMINI_API_KEY", "")

# D. PERFORMANCE TRACKER
total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0
st.sidebar.subheader("📈 Performance Tracker")
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total Trades: {total_trades}")

# E. VITALS & INDEPENDENCE
def get_vitals_safe():
    try:
        vix_df = yf.download("^VIX", period="1d", interval="1m", progress=False, multi_level_index=False)
        gold_df = yf.download("GC=F", period="1d", interval="1m", progress=False, multi_level_index=False)
        vix = vix_df['Close'].iloc[-1] if not vix_df.empty else 0.0
        gold = gold_df['Close'].iloc[-1] if not gold_df.empty else 0.0
        return vix, gold
    except: return 0.0, 0.0

vix_val, gold_val = get_vitals_safe()
st.sidebar.metric("Fear Index (VIX)", f"{vix_val:.2f}")
st.sidebar.metric("Gold (GC=F)", f"${gold_val:.2f}")

# F. TREND MATRIX
def get_trend(symbol, interval, period):
    try:
        data = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
        if len(data) < 20: return "Neutral"
        sma_short = data['Close'].rolling(9).mean().iloc[-1]
        sma_long = data['Close'].rolling(21).mean().iloc[-1]
        return "BULLISH" if sma_short > sma_long else "BEARISH"
    except: return "Neutral"

target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])
trend_1h = get_trend(target, '1h', '5d')
st.sidebar.write(f"1-Hour Trend: {trend_1h}")

st.sidebar.divider()
sentiment_trend = st.sidebar.select_slider("Headline Sentiment", options=["Cooling", "Neutral", "Heating Up", "Explosive"], value="Heating Up")
event_alert = st.sidebar.toggle("🚨 SYSTEMIC EVENT ALERTS", value=True)

# --- 4. MAIN INTERFACE ---
if is_close_near:
    st.warning("⚠️ **MARKET CLOSE WARNING:** High volatility expected in the final minutes. Consider protecting current gains.")

if event_alert:
    st.error(f"**🚨 SYSTEMIC RISK ALERT: FED INDEPENDENCE CRISIS** - Sentiment: **{sentiment_trend}**.")

@st.fragment(run_every=60)
def monitor_market():
    df = yf.download(target, period="2d", interval="5m", multi_level_index=False)
    if not df.empty:
        df['VWAP'] = ((df['High'] + df['Low'] + df['Close'])/3 * df['Volume']).cumsum() / df['Volume'].cumsum()
        last_price = df['Close'].iloc[-1]
        vwap_val = df['VWAP'].iloc[-1]
        
        # 4-Tier Signal Logic
        if last_price > vwap_val:
            signal_type = "STRONG LONG 🚀" if trend_1h == "BULLISH" else "WEAK LONG ⚠️"
        else:
            signal_type = "STRONG SHORT 📉" if trend_1h == "BEARISH" else "WEAK SHORT ⚠️"

        # Risk Shield
        vol_range = (df['High'].tail(10) - df['Low'].tail(10)).mean()
        sl_buffer = vol_range * 1.5
        sl_l = last_price - sl_buffer; tp_l = last_price + (sl_buffer * 3)
        sl_s = last_price + sl_buffer; tp_s = last_price - (sl_buffer * 3)

        st.subheader(f"🚀 {target} Live: {last_price:.2f} | Signal: {signal_type}")
        
        c1, c2 = st.columns(2)
        with c1: st.success(f"🟢 LONG: Target {tp_l:.2f} | SL {sl_l:.2f}")
        with c2: st.error(f"🔴 SHORT: Target {tp_s:.2f} | SL {sl_s:.2f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, df.tail(10).to_string(), signal_type, tp_l, sl_l, tp_s, sl_s
    return None, None, None, None, None, None, None

last_p, momentum_d, sig_str, tp_l, sl_l, tp_s, sl_s = monitor_market()

# --- 5. TRADE RESULT LOGGER ---
st.divider()
st.subheader("🏁 Trade Result Logger")
res_col1, res_col2, res_col3 = st.columns(3)
with res_col1:
    if st.button("✅ HIT TARGET (Win)", use_container_width=True):
        st.session_state.wins += 1; st.balloons()
with res_col2:
    if st.button("❌ HIT STOP-LOSS (Loss)", use_container_width=True):
        st.session_state.losses += 1
with res_col3:
    if st.button("🔄 Reset Tracker", use_container_width=True):
        st.session_state.wins = 0; st.session_state.losses = 0

# --- 6. AI STRATEGY ENGINE ---
st.divider()
st.subheader("📓 AI Analysis & Strength Validation")
headline_context = f"- SIGNAL: {sig_str}\n- TIME: {curr_time_str} ({'Volatile Close' if is_close_near else 'Normal'})\n- VITALS: Gold {gold_val:.2f} | VIX {vix_val:.2f}"
trade_notes = st.text_area("Live Context:", value=headline_context, height=100)

if st.button("Generate Final AI Trade Plan", use_container_width=True):
    if active_key:
        try:
            client = genai.Client(api_key=active_key)
            prompt = f"Analyze {target}. Time: {curr_time_str}. VIX: {vix_val}. Momentum: {momentum_d}. Signal: {sig_str}. Is the market close too dangerous?"
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
            st.info(f"### 🤖 AI Verdict: {sig_str}")
            st.markdown(response.text)
        except Exception as e: st.error(f"AI Error: {e}")

# Download
log_c = f"WIN RATE: {win_rate}%\nTIME: {curr_time_str}\nAI PLAN:\n{st.session_state.get('ai_verdict', 'N/A')}"
st.download_button("📁 Download Performance Log", data=log_c, file_name=f"QuantPerformance_Log.txt", use_container_width=True)
