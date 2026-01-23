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

active_google_key = st.secrets.get("GEMINI_API_KEY", "")
if not active_google_key:
    st.sidebar.subheader("🔌 AI Authentication")
    google_key_input = st.sidebar.text_input("Paste Google AI Key:", type="password")
    active_google_key = google_key_input
else:
    st.sidebar.success("✅ AI Engine Authenticated")

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

total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0.0
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total: {total_trades}")

# --- 4. PREDICTIVE HEADER (SHADOW + VIX + TREND STRENGTH) ---
st.title(f"🚀 {target_label} Quant Workstation")

def get_realtime_indicators(target):
    shadow_map = {"NQ=F": "QQQ", "ES=F": "SPY"}
    shadow_ticker = shadow_map.get(target, "QQQ")
    try:
        s_val = yf.download(shadow_ticker, period="1d", interval="1m", progress=False)['Close'].iloc[-1]
        vix_val = yf.download("^VIX", period="1d", interval="1m", progress=False)['Close'].iloc[-1]
        return s_val, shadow_ticker, vix_val
    except: return 0.0, "N/A", 0.0

shadow_p, shadow_n, vix_p = get_realtime_indicators(target_symbol)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric(f"Real-Time {shadow_n} (Shadow)", f"${shadow_p:.2f}")
with c2:
    vix_status = "⚠️ Spiking" if vix_p > 20 else "🟢 Calm"
    st.metric("VIX (Fear Index)", f"{vix_p:.2f}", delta=vix_status, delta_color="inverse")
with c3:
    st.write("📊 **Execution Intelligence:**")
    st.caption("Compare VIX and Shadow Price to identify potential lag reversals.")

# --- 5. THE MONITOR & SIGNAL ENGINE ---
@st.fragment(run_every=60)
def monitor_market():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        if df.empty: return None
        
        last_price = df['Close'].iloc[-1]
        # SMA & Trend Strength calculation
        sma_series = df['Close'].rolling(9).mean()
        sma9 = sma_series.iloc[-1]
        sma9_prev = sma_series.iloc[-2]
        sma21 = df['Close'].rolling(21).mean().iloc[-1]
        
        # Trend Angle (Slope)
        slope = sma9 - sma9_prev
        strength = "ACCELERATING ⚡" if abs(slope) > (last_price * 0.0001) else "STABLE 💎"
        
        df['VWAP'] = ((df['High'] + df['Low'] + df['Close'])/3 * df['Volume']).cumsum() / df['Volume'].cumsum()
        vwap_v = df['VWAP'].iloc[-1]
        
        vol = (df['High'].tail(10) - df['Low'].tail(10)).mean()
        trend_dir = "BULLISH" if sma9 > sma21 else "BEARISH"
        
        if abs(last_price - vwap_v) < (vol * 0.3):
            sig_s = "WAIT ⏳"
        elif last_price > vwap_v:
            sig_s = "STRONG LONG 🚀" if trend_dir == "BULLISH" else "WEAK LONG ⚠️"
        else:
            sig_s = "STRONG SHORT 📉" if trend_dir == "BEARISH" else "WEAK SHORT ⚠️"

        st.subheader(f"Signal: {sig_s} | Trend: {strength} | Price: {last_price:.2f}")
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        return {"price": last_price, "signal": sig_s, "sma9": sma9, "sma21": sma21, "vwap": vwap_v, "trend": trend_dir, "strength": strength}
    except Exception as e:
        st.error(f"Market Sync Error: {e}"); return None

market_d = monitor_market()

# --- 6. THE VERDICT (Fixed Syntax) ---
st.divider()
if st.button("Analyze Current Setup", use_container_width=True):
    if not active_google_key:
        st.warning("⚠️ Enter Google AI Key in sidebar or Secrets.")
    elif market_d:
        try:
            client = genai.Client(api_key=active_google_key)
            prompt = f"""
            AI Verdict: {market_d['signal']}
            Trend Momentum: {market_d['strength']}
            Price: {market_d['price']} | Shadow Price: {shadow_p} | VIX: {vix_p}
            Trend: {market_d['trend']} | SMA(9): {market_d['sma9']} | VWAP: {market_d['vwap']}
            
            Format:
            1. Signal Assessment (Confidence % and breakdown)
            2. Technical Alignment (Trend, SMA, VWAP)
            3. Leading Indicator Check (Shadow/VIX lag check)
            """
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            st.info(f"### 🤖 AI Strategy Verdict"); st.markdown(response.text)
        except Exception as e:
            st.error(f"Verdict Error: {e}")

# Corrected Column Syntax
c1, c2 = st.columns(2)
with c1:
    if st.button("✅ HIT TARGET", use_container_width=True): 
        st.session_state.wins += 1
        st.balloons()
with c2:
    if st.button("❌ HIT STOP-LOSS", use_container_width=True): 
        st.session_state.losses += 1
