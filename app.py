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
st.sidebar.subheader("🔌 AI Authentication")
google_key_input = st.sidebar.text_input("Google AI Key:", type="password")
active_google_key = google_key_input if google_key_input else st.secrets.get("GEMINI_API_KEY", "")

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

# --- 4. MAIN INTERFACE ---
st.title(f"🚀 {target_label} Quant Workstation")

@st.fragment(run_every=60)
def monitor_market():
    try:
        # Fast, Free Market Data
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

        # Restored Chart
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return {"price": last_price, "signal": sig_str, "sma9": sma9, "sma21": sma21, "vwap": vwap_val, "trend": trend}
    except Exception as e:
        st.error(f"Market Sync Issue: {e}")
        return None

market_data = monitor_market()

# --- 5. RESTORED 5-TIER VERDICT ---
st.divider()
if st.button("Analyze Current Setup", use_container_width=True):
    if not active_google_key:
        st.warning("⚠️ Enter Google AI Key in sidebar.")
    elif market_data:
        try:
            client = genai.Client(api_key=active_google_key)
            prompt = f"""
            AI Verdict: {market_data['signal']}
            Price: {market_data['price']}
            Trend: {market_data['trend']}
            SMA(9): {market_data['sma9']} | SMA(21): {market_data['sma21']}
            VWAP: {market_data['vwap']}
            
            Provide:
            1. Signal Assessment (Confidence % and breakdown)
            2. Technical Alignment (Pro-Long or Pro-Short bullet points for Trend, SMAs, and VWAP)
            """
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            st.info(f"### 🤖 AI Strategy Verdict")
            st.markdown(response.text)
        except Exception as e:
            st.error(f"Verdict Error: {e}")

c1, c2 = st.columns(2)
with c1:
    if st.button("✅ HIT TARGET", use_container_width=True): st.session_state.wins += 1; st.balloons()
with c2:
    if st.button("❌ HIT STOP-LOSS", use_container_width=True): st.session_state.losses += 1
