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

# --- 2. PERSISTENT STATE (Warning: Resets on code changes) ---
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

# E. VITALS & INDEPENDENCE TRACKER
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
st.sidebar.metric("Fear Index (VIX)", f"{vix_val:.2f}")
st.sidebar.metric("Gold (GC=F)", f"${gold_val:.2f}")
st.sidebar.metric("US Dollar (DXY)", f"{dxy_val:.2f}")

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
    st.warning("⚠️ **MARKET CLOSE WARNING:** High volatility expected. Protect your gains.")

if event_alert:
    st.error(f"**🚨 SYSTEMIC RISK ALERT: POWELL INVESTIGATION** - News Sentiment: **{sentiment_trend}**.")

@st.fragment(run_every=60)
def monitor_market():
    df = yf.download(target, period="2d", interval="5m", multi_level_index=False)
    if not df.empty:
        df['VWAP'] = ((df['High'] + df['Low'] + df['Close'])/3 * df['Volume']).cumsum() / df['Volume'].cumsum()
        last_price = df['Close'].iloc[-1]
        vwap_val = df['VWAP'].iloc[-1]
        
        # 4-Tier Signal Logic
        if last_price > vwap_val:
            sig_str = "STRONG LONG 🚀" if trend_1h == "BULLISH" else "WEAK LONG ⚠️"
        else:
            sig_str = "STRONG SHORT 📉" if trend_1h == "BEARISH" else "WEAK SHORT ⚠️"

        # Risk Shield Calculations
        recent_10 = df.tail(10)
        vol_range = (recent_10['High'] - recent_10['Low']).mean()
        sl_buffer = vol_range * 1.5
        sl_l = last_price - sl_buffer; tp_l = last_price + (sl_buffer * 3)
        sl_s = last_price + sl_buffer; tp_s = last_price - (sl_buffer * 3)
        
        # Position Sizing
        micro_pt = 2 if "NQ" in target else 5
        micro_qty = risk_dollars / (abs(last_price - sl_l) * micro_pt) if abs(last_price - sl_l) > 0 else 0

        st.subheader(f"🚀 {target} Live: {last_price:.2f} | {sig_str}")
        
        c1, c2 = st.columns(2)
        with c1: st.success(f"🟢 LONG: TP {tp_l:.2f} | SL {sl_l:.2f} | Size: {micro_qty:.1f} Micros")
        with c2: st.error(f"🔴 SHORT: TP {tp_s:.2f} | SL {sl_s:.2f} | Size: {micro_qty:.1f} Micros")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, recent_10.to_string(), sig_str, tp_l, sl_l, tp_s, sl_s, micro_qty
    return None, None, None, None, None, None, None, None

last_p, momentum_d, sig_str, tp_l, sl_l, tp_s, sl_s, m_qty = monitor_market()

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
    if st.button("🔄 Reset Performance", use_container_width=True):
        st.session_state.wins = 0; st.session_state.losses = 0

# --- 6. HIGH-VELOCITY AI STRATEGY ENGINE ---
st.divider()
st.subheader("📓 Instant AI Analysis & Strategy")
headline_context = f"- EVENT: Powell Probe (Jan 12 Crisis)\n- VITALS: VIX {vix_val:.2f} | Gold {gold_val:.2f}\n- SIGNAL: {sig_str}"
trade_notes = st.text_area("Live Context Archive:", value=headline_context, height=100)

if st.button("🚀 Generate Instant Verdict", use_container_width=True):
    if active_key:
        try:
            client = genai.Client(api_key=active_key)
            prompt = f"FAST VERDICT: {target} at {last_p}. 1H: {trend_1h}. Signal: {sig_str}. Momentum: {momentum_d}. News: {trade_notes}. Task: Verdict (Long/Short/Wait), Confidence %, Risk Warning. Max 50 words."
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
            st.info(f"### 🤖 High-Velocity Verdict: {sig_str}")
            st.markdown(response.text)
        except Exception as e: st.error(f"AI Speed Error: {e}")

# --- 7. LOG DOWNLOAD ---
log_c = f"SESSION: {datetime.now()}\nWIN RATE: {win_rate}%\nTOTAL TRADES: {total_trades}\nSIGNAL: {sig_str}"
st.download_button("📁 Download Detailed Strategy Log", data=log_c, file_name=f"QuantPerformance_Log.txt", use_container_width=True)
