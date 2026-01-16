import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from google import genai
from google.genai import types
from datetime import datetime, timedelta
import databento as db
import pytz

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Workstation", initial_sidebar_state="collapsed")

# --- 2. PERSISTENT STATE ---
if 'wins' not in st.session_state: st.session_state.wins = 0
if 'losses' not in st.session_state: st.session_state.losses = 0

# --- 3. SIDEBAR: RECOGNIZABLE COMMAND CENTER ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

st.sidebar.subheader("🔌 API Authentication")
db_key_input = st.sidebar.text_input("Databento Key:", value="db-nxmsN86EgTWKpei8TiVfkin6XMcS9", type="password")
google_key_input = st.sidebar.text_input("Google AI Key:", type="password")

active_db_key = db_key_input if db_key_input else st.secrets.get("DATABENTO_API_KEY", "")
active_google_key = google_key_input if google_key_input else st.secrets.get("GEMINI_API_KEY", "")

# Databento Connection Check
def verify_db_auth(key):
    if not key: return "⚪ No Key"
    try:
        client = db.Historical(key)
        client.metadata.get_dataset_condition(dataset="GLBX.MDP3")
        return "🟢 Connected (CME L1)"
    except: return "🔴 Auth Failed"

db_status = verify_db_auth(active_db_key)
st.sidebar.write(f"Status: {db_status}")

# Asset Selection
asset_map = {"NQ=F": "NQ.c.0", "ES=F": "ES.c.0"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

# Performance Tracker
st.sidebar.divider()
total_trades = st.session_state.wins + st.session_state.losses
win_rate = (st.session_state.wins / total_trades * 100) if total_trades > 0 else 0.0
st.sidebar.metric("Win Rate", f"{win_rate:.1f}%", f"Total: {total_trades}")

# --- 4. MAIN INTERFACE ---
st.title(f"🚀 {target_label} Quant Workstation")

@st.fragment(run_every=60)
def monitor_market():
    if "Authenticated" not in db_status:
        st.info("💡 Waiting for Databento Key authentication...")
        return None
    
    try:
        client = db.Historical(active_db_key)
        # Fetching CME L1 Data
        data = client.timeseries.get_range(
            dataset="GLBX.MDP3",
            symbols=target_symbol,
            schema="ohlcv-5m",
            start=(datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        )
        df = data.to_df()
        
        # 5-Tier Signal Logic
        last_price = df['close'].iloc[-1]
        sma9 = df['close'].rolling(9).mean().iloc[-1]
        sma21 = df['close'].rolling(21).mean().iloc[-1]
        df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        vwap_val = df['vwap'].iloc[-1]
        
        # Volatility Buffer for WAIT
        vol = (df['high'].tail(10) - df['low'].tail(10)).mean()
        chop_zone = vol * 0.3
        
        # Strength logic
        trend = "BULLISH" if sma9 > sma21 else "BEARISH"
        
        if abs(last_price - vwap_val) < chop_zone:
            sig_str = "WAIT ⏳"
        elif last_price > vwap_val:
            sig_str = "STRONG LONG 🚀" if trend == "BULLISH" else "WEAK LONG ⚠️"
        else:
            sig_str = "STRONG SHORT 📉" if trend == "BEARISH" else "WEAK SHORT ⚠️"

        st.subheader(f"Current Signal: {sig_str} | Price: {last_price:.2f}")

        # Chart with Cyan VWAP
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['vwap'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return {
            "price": last_price, "signal": sig_str, "sma9": sma9, 
            "sma21": sma21, "vwap": vwap_val, "trend": trend
        }
    except Exception as e:
        st.error(f"Market Data Error: {e}")
        return None

market_data = monitor_market()

# --- 5. THE RESTORED VERDICT SYSTEM ---
st.divider()
if st.button("Analyze Current Setup", use_container_width=True):
    if not active_google_key:
        st.warning("⚠️ Google AI Key missing. Provide it in the sidebar.")
    elif market_data is None:
        st.warning("⚠️ Market data unavailable.")
    else:
        try:
            client = genai.Client(api_key=active_google_key)
            # Custom Restored Prompt
            prompt = f"""
            Act as a Quant Trader. Analyze {target_label}:
            Price: {market_data['price']}
            Signal: {market_data['signal']}
            Trend: {market_data['trend']}
            SMA(9): {market_data['sma9']}
            SMA(21): {market_data['sma21']}
            VWAP: {market_data['vwap']}
            
            FORMAT:
            AI Verdict: [SIGNAL]
            Analysis:
            1. Signal Assessment: Confidence % and breakdown.
            2. Technical Alignment: Pro-[Side] bullet points for Trend, SMAs, and VWAP.
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
