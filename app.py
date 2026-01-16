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

# --- 3. SIDEBAR: AUTHENTICATION & TRENDS ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

st.sidebar.subheader("🔌 API Authentication")
# Databento key entry
db_key = st.sidebar.text_input("Databento API Key:", type="password", help="db-...")
google_key = st.sidebar.text_input("Google AI Key:", type="password")

active_db_key = db_key if db_key else st.secrets.get("DATABENTO_API_KEY", "")
active_google_key = google_key if google_key else st.secrets.get("GEMINI_API_KEY", "")

# Verify Databento Auth
def check_db_auth(key):
    if not key: return "⚪ No Key"
    try:
        client = db.Historical(key)
        client.metadata.get_dataset_condition(dataset="GLBX.MDP3")
        return "🟢 Authenticated"
    except Exception as e:
        return f"🔴 Auth Failed: {str(e)[:20]}"

db_status = check_db_auth(active_db_key)
st.sidebar.write(f"Databento Status: {db_status}")

# Asset Selection
asset_map = {"NQ (Nasdaq 100)": "NQ.c.0", "ES (S&P 500)": "ES.c.0"}
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
        st.info("💡 Enter Databento API Key in sidebar to start live workstation.")
        return None, None
    
    try:
        client = db.Historical(active_db_key)
        # Fetching latest 100 bars of 5-minute data
        data = client.timeseries.get_range(
            dataset="GLBX.MDP3",
            symbols=target_symbol,
            schema="ohlcv-5m",
            start=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        )
        df = data.to_df()
        df.index = pd.to_datetime(df.index)
        
        # Calculations
        last_price = df['close'].iloc[-1]
        df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
        vwap_val = df['vwap'].iloc[-1]
        
        # 5-Tier Strength Logic
        vol = (df['high'].tail(10) - df['low'].tail(10)).mean()
        if abs(last_price - vwap_val) < (vol * 0.3):
            sig_str = "WAIT ⏳"
        else:
            sig_str = "STRONG LONG 🚀" if last_price > vwap_val else "STRONG SHORT 📉"

        st.subheader(f"Current Signal: {sig_str} | Price: {last_price:.2f}")

        # Restoration of the Cyan VWAP Chart
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price")])
        fig.add_trace(go.Scatter(x=df.index, y=df['vwap'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, sig_str
    except Exception as e:
        st.error(f"Market Connection Issue: {e}")
        return None, None

current_price, current_signal = monitor_market()

# --- 5. THE VERDICT (Google API Integration) ---
st.divider()
if st.button("Analyze Current Setup", use_container_width=True):
    if not active_google_key:
        st.warning("⚠️ Google AI Key missing. Provide it in the sidebar.")
    elif current_price is None:
        st.warning("⚠️ No data available for analysis.")
    else:
        try:
            client = genai.Client(api_key=active_google_key)
            prompt = f"VERDICT: {target_label} at {current_price}. Signal: {current_signal}. Context: Institutional data via Databento. Max 50 words."
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            st.info(f"### 🤖 AI Strategy Verdict")
            st.markdown(response.text)
        except Exception as e:
            st.error(f"Verdict Error: {e}")

c1, c2 = st.columns(2)
with c1:
    if st.button("✅ HIT TARGET", use_container_width=True): 
        st.session_state.wins += 1; st.balloons()
with c2:
    if st.button("❌ HIT STOP-LOSS", use_container_width=True): 
        st.session_state.losses += 1
