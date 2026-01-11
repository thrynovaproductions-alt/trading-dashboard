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

# --- 3. SIDEBAR & SETTINGS ---
target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])
st.sidebar.subheader("🎯 Price Alerts")
alert_price = st.sidebar.number_input("Notify at Price:", value=0.0, step=0.25)

if st.sidebar.button("Enable Mobile Alerts", use_container_width=True):
    components.html("<script>Notification.requestPermission();</script>", height=0)

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
st.sidebar.divider()

# --- 5. THE REFRESHING MONITOR ---
@st.fragment(run_every=60)
def monitor_market():
    df = yf.download(target, period="2d", interval="5m", multi_level_index=False)
    
    if not df.empty:
        df['SMA9'] = df['Close'].rolling(9).mean()
        df['SMA21'] = df['Close'].rolling(21).mean()
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (df['Typical_Price'] * df['Volume']).cumsum() / df['Volume'].cumsum()
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        last_price = last_row['Close']
        curr_time = datetime.now().strftime("%H:%M:%S")
        
        if prev_row['SMA9'] <= prev_row['SMA21'] and last_row['SMA9'] > last_row['SMA21']:
            if "BULLISH" in matrix_1h:
                fire_notification("🔥 CONFIRMED BUY", f"{target} at {last_price:.2f}")

        if alert_price > 0 and abs(last_price - alert_price) < 2:
            fire_notification("🎯 PRICE TARGET NEAR", f"{target} is at {last_price:.2f}")

        st.subheader(f"🚀 Live {target}: {last_price:.2f} (Refreshed: {curr_time})")
        
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price
    return None

last_market_price = monitor_market()

# --- 6. AI SECTION & TRADING JOURNAL (LOG BOOK) ---
st.divider()
st.subheader("📓 Trading Journal & AI Analysis")

trade_notes = st.text_area("Trading Notes:", placeholder="e.g., Price rejected VWAP...")

col1, col2 = st.columns(2)

with col1:
    if st.button("Generate AI Market Verdict", use_container_width=True):
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            # --- AUTO-FALLBACK MODEL LOGIC ---
            # Try Gemini 3 Flash first, fallback to 2.5 if needed
            model_to_use = "gemini-3-flash-preview" 
            try:
                model = genai.GenerativeModel(model_name=model_to_use, tools=[{"google_search_retrieval": {}}])
                prompt = f"Analyze {target} for Jan 11, 2026. 1H: {matrix_1h}. Notes: {trade_notes}. Verdict?"
                response_text = model.generate_content(prompt).text
            except Exception:
                model_to_use = "gemini-2.5-flash"
                model = genai.GenerativeModel(model_name=model_to_use, tools=[{"google_search_retrieval": {}}])
                prompt = f"Analyze {target} for Jan 11, 2026. 1H: {matrix_1h}. Notes: {trade_notes}. Verdict?"
                response_text = model.generate_content(prompt).text
            
            st.session_state['ai_verdict'] = response_text
            st.markdown(response_text)
        except Exception as e:
            st.error(f"AI Setup Error: {e}")

with col2:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    verdict_content = st.session_state.get('ai_verdict', "No AI Verdict generated yet.")
    
    log_content = f"""
TRADING LOG ENTRY
-----------------
Timestamp: {timestamp}
Asset: {target}
Market Price: {last_market_price}
1H Trend: {matrix_1h}
Daily Trend: {matrix_1d}

USER NOTES:
{trade_notes}

AI VERDICT:
{verdict_content}
-----------------
"""
    st.download_button(
        label="📁 Download Trading Log",
        data=log_content,
        file_name=f"Trade_Log_{target}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        use_container_width=True
    )
