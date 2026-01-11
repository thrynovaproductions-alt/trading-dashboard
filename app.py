import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
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

# --- 3. SIDEBAR CONTROLS ---
target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])
st.sidebar.subheader("🎯 Price Alerts")
alert_price = st.sidebar.number_input("Notify at Price:", value=0.0, step=0.25)

if st.sidebar.button("Enable Mobile Alerts", use_container_width=True):
    components.html("<script>Notification.requestPermission();</script>", height=0)

# --- 4. TREND MATRIX (Static Calculation) ---
def get_trend(symbol, interval, period):
    data = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
    if len(data) < 20: return "Neutral"
    sma_short = data['Close'].rolling(9).mean().iloc[-1]
    sma_long = data['Close'].rolling(21).mean().iloc[-1]
    return "BULLISH" if sma_short > sma_long else "BEARISH"

matrix_1h = get_trend(target, "1h", "5d")
st.sidebar.write(f"1-Hour Trend: {matrix_1h}")

# --- 5. THE REFRESHING MONITOR (Auto-Updates 60s) ---
@st.fragment(run_every=60)
def monitor_market():
    # A. Fetch Fresh Data
    df = yf.download(target, period="2d", interval="5m", multi_level_index=False)
    
    if not df.empty:
        # B. Indicators
        df['SMA9'] = df['Close'].rolling(9).mean()
        df['SMA21'] = df['Close'].rolling(21).mean()
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (df['Typical_Price'] * df['Volume']).cumsum() / df['Volume'].cumsum()
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        last_price = last_row['Close']
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # C. Logic Trigger: SMA Crossover confirmed by 1H Trend
        # Bullish Trigger
        if prev_row['SMA9'] <= prev_row['SMA21'] and last_row['SMA9'] > last_row['SMA21']:
            if matrix_1h == "BULLISH":
                fire_notification("🔥 TREND CONFIRMED BUY", f"{target} at {last_price:.2f}")
        
        # Bearish Trigger
        if prev_row['SMA9'] >= prev_row['SMA21'] and last_row['SMA9'] < last_row['SMA21']:
            if matrix_1h == "BEARISH":
                fire_notification("💥 TREND CONFIRMED SELL", f"{target} at {last_price:.2f}")

        # D. Price Alert Logic
        if alert_price > 0:
            if (prev_row['Close'] < alert_price <= last_row['Close']) or (prev_row['Close'] > alert_price >= last_row['Close']):
                fire_notification("🎯 PRICE LEVEL HIT", f"{target} reached {alert_price}")

        # E. Live Display
        st.subheader(f"🚀 Live {target} at {last_price:.2f} (Updated: {timestamp})")
        
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        
        fig.update_layout(height=550, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Awaiting market data connection...")

monitor_market()

# --- 6. DEEP AI ANALYSIS (Static Section) ---
st.divider()
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(model_name='gemini-1.5-flash', tools=[{"google_search_retrieval": {}}])
    if st.button("Generate Deep AI Market Verdict", use_container_width=True):
        with st.spinner('Scanning Live 2026 Macro News...'):
            prompt = f"Analyze {target} for January 10, 2026. 1H Trend is {matrix_1h}. Provide a correlation between this trend and any breaking news from today."
            st.markdown(model.generate_content(prompt).text)
except Exception as e:
    st.error(f"AI Connection Error: {e}")
