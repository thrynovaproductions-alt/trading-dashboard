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

# --- 2. PWA & NOTIFICATION ENGINE ---
def fire_notification(title, body):
    components.html(f"""
        <script>
        if (Notification.permission === 'granted') {{
            new Notification('{title}', {{ body: '{body}', icon: 'https://cdn-icons-png.flaticon.com/512/2464/2464402.png' }});
        }}
        </script>
    """, height=0)

components.html("""
    <script>
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', function() { navigator.serviceWorker.register('./sw.js'); });
    }
    var link = window.parent.document.createElement("link");
    link.rel = "manifest"; link.href = "./manifest.json";
    window.parent.document.head.appendChild(link);
    </script>
""", height=0)

# --- 3. SIDEBAR: INDEPENDENCE TRACKER & Vitals ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# VIX TRACKER
def get_vitals():
    vix = yf.download("^VIX", period="1d", interval="1m", progress=False)['Close'].iloc[-1]
    # Independence Tracker: USD Index vs Gold
    dxy = yf.download("DX-Y.NYB", period="1d", interval="1m", progress=False)['Close'].iloc[-1]
    gold = yf.download("GC=F", period="1d", interval="1m", progress=False)['Close'].iloc[-1]
    return vix, dxy, gold

vix_val, dxy_val, gold_val = get_vitals()
st.sidebar.metric("Fear Index (VIX)", f"{vix_val:.2f}")

st.sidebar.subheader("⚖️ Independence Tracker")
# If Gold rises and USD falls, it signals a flight from fiat trust
st.sidebar.metric("Gold (GC=F)", f"${gold_val:.2f}")
st.sidebar.metric("US Dollar (DXY)", f"{dxy_val:.2f}")

# Systemic Shock Toggle
shock_active = st.sidebar.toggle("POWELL PROBE ACTIVE", value=True)
macro_risk = "CRITICAL" if shock_active else "MODERATE"

target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])

# --- 4. TREND MATRIX ---
def get_trend(symbol, interval, period):
    data = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
    if len(data) < 20: return "Neutral"
    sma_short = data['Close'].rolling(9).mean().iloc[-1]
    sma_long = data['Close'].rolling(21).mean().iloc[-1]
    return "BULLISH 🟢" if sma_short > sma_long else "BEARISH 🔴"

st.sidebar.subheader("Technical Matrix")
matrix_1h = get_trend(target, "1h", "5d")
matrix_1d = get_trend(target, "1d", "1mo")

# --- 5. THE REFRESHING MONITOR ---
@st.fragment(run_every=60)
def monitor_market():
    df = yf.download(target, period="2d", interval="5m", multi_level_index=False)
    if not df.empty:
        df['VWAP'] = ((df['High'] + df['Low'] + df['Close'])/3 * df['Volume']).cumsum() / df['Volume'].cumsum()
        last_price = df['Close'].iloc[-1]
        st.subheader(f"🚀 {target}: {last_price:.2f}")
        
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        return last_price, df.tail(10).to_string()
    return None, None

last_price, momentum_data = monitor_market()

# --- 6. AI VERDICT & SHOCK LOG ---
st.divider()
st.subheader("📓 AI Analysis & Powell Probe Archive")

shock_notes = f"""- DOJ PROBE: Jerome Powell criminal investigation active (Jan 11).
- INDEPENDENCE: USD at {dxy_val:.2f} | Gold at {gold_val:.2f}.
- RISK: {macro_risk} systemic shock status."""

trade_notes = st.text_area("Live Headlines & Context:", value=shock_notes if shock_active else "", height=150)

if st.button("Generate Systemic Risk Verdict", use_container_width=True):
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
        
        prompt = f"""Analyze {target} for Jan 11-12, 2026. 
        VIX: {vix_val} | Macro Risk: {macro_risk}
        Independence Tracker: DXY {dxy_val}, Gold {gold_val}.
        Headline Archive: {trade_notes}
        Momentum: {momentum_data}
        Task: Weigh technicals against the Fed crisis. Is trust in the US system deteriorating?"""
        
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=config)
        st.session_state['ai_verdict'] = response.text
        st.markdown(response.text)
    except Exception as e:
        st.error(f"AI Setup Error: {e}")

# Download Logic
log_content = f"LOG: {datetime.now()}\nASSET: {target}\nVIX: {vix_val}\nDXY: {dxy_val}\nGOLD: {gold_val}\nAI VERDICT:\n{st.session_state.get('ai_verdict', 'N/A')}"
st.download_button("📁 Download Systemic Risk Log", data=log_content, file_name=f"Powell_Crisis_Log.txt")
