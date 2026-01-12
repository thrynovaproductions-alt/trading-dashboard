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

# --- 3. SIDEBAR: VIX TRACKER & RISK ---
st.sidebar.title("📊 Market Vitals")

# NEW: VIX Fear Gauge
def get_vix_data():
    vix_df = yf.download("^VIX", period="2d", interval="1m", progress=False)
    if not vix_df.empty:
        current_vix = vix_df['Close'].iloc[-1]
        prev_vix = vix_df['Close'].iloc[0]
        change = current_vix - prev_vix
        return current_vix, change
    return 0, 0

vix_val, vix_chg = get_vix_data()
vix_col1, vix_col2 = st.sidebar.columns(2)
vix_col1.metric("VIX (Fear Index)", f"{vix_val:.2f}")
vix_col2.metric("24H Change", f"{vix_chg:+.2f}")

if vix_val > 25:
    st.sidebar.warning("⚠️ High Volatility Detected")

# Macro Risk Slider
st.sidebar.subheader("⚖️ Macro Risk Level")
macro_risk = st.sidebar.select_slider(
    "Powell Investigation / Tariff Risk",
    options=["LOW", "MODERATE", "HIGH", "CRITICAL"],
    value="HIGH"
)

target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])

# System Health
st.sidebar.divider()
if st.sidebar.button("Test API Connectivity", use_container_width=True):
    with st.sidebar:
        with st.spinner("Checking connection..."):
            try:
                if "GEMINI_API_KEY" not in st.secrets:
                    st.error("❌ Key Missing in Secrets")
                else:
                    test_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                    test_client.models.list(config={'page_size': 1})
                    st.success("🟢 API Connected")
            except Exception as e:
                st.error(f"🔴 Connection Failed: {e}")

# --- 4. TREND MATRIX ---
def get_trend(symbol, interval, period):
    data = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
    if len(data) < 20: return "Neutral"
    sma_short = data['Close'].rolling(9).mean().iloc[-1]
    sma_long = data['Close'].rolling(21).mean().iloc[-1]
    return "BULLISH 🟢" if sma_short > sma_long else "BEARISH 🔴"

st.sidebar.subheader("Multi-Timeframe Trend")
matrix_1h = get_trend(target, "1h", "5d")
matrix_1d = get_trend(target, "1d", "1mo")
st.sidebar.write(f"1-Hour: {matrix_1h}")
st.sidebar.write(f"Daily: {matrix_1d}")

# --- 5. THE REFRESHING MONITOR ---
@st.fragment(run_every=60)
def monitor_market():
    df = yf.download(target, period="2d", interval="5m", multi_level_index=False)
    if not df.empty:
        df['SMA9'] = df['Close'].rolling(9).mean()
        df['SMA21'] = df['Close'].rolling(21).mean()
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (df['Typical_Price'] * df['Volume']).cumsum() / df['Volume'].cumsum()
        
        last_price = df['Close'].iloc[-1]
        st.subheader(f"🚀 Live {target}: {last_price:.2f}")
        
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        momentum_data = df.tail(10)[['Open', 'High', 'Low', 'Close']].to_string()
        return last_price, momentum_data
    return None, None

last_market_price, momentum_data = monitor_market()

# --- 6. AI SECTION & NEWS ARCHIVE ---
st.divider()
st.subheader("📓 News Impact Archive & AI Analysis")
default_headlines = f"- VIX Level: {vix_val:.2f} ({'Elevated' if vix_val > 20 else 'Stable'})\n- FED: Jerome Powell criminal investigation confirmed (Jan 11)\n- MACRO RISK: {macro_risk}"
trade_notes = st.text_area("Trading Notes & Headline Context:", value=default_headlines, height=150)

if st.button("Generate AI Market Verdict", use_container_width=True):
    try:
        client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        search_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(tools=[search_tool])
        with st.spinner('Analyzing Volatility & Macro News...'):
            prompt = f"Analyze {target} for Jan 11-12, 2026. VIX: {vix_val}. Risk: {macro_risk}. News: {trade_notes}. Momentum: {momentum_data}"
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=config)
            st.session_state['ai_verdict'] = response.text
            st.markdown(response.text)
    except Exception as e:
        st.error(f"AI Setup Error: {e}")

# Download Log Book
verdict_content = st.session_state.get('ai_verdict', "No AI Verdict generated yet.")
log_content = f"LOG: {datetime.now()}\nASSET: {target}\nVIX: {vix_val}\nAI VERDICT:\n{verdict_content}"
st.download_button(label="📁 Download Complete Trade Log", data=log_content, file_name=f"QuantLog_{datetime.now().strftime('%Y%m%d')}.txt", use_container_width=True)
