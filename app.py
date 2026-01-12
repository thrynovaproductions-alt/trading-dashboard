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

# --- 3. SIDEBAR: VITALS & SENTIMENT ---
st.sidebar.title("⚠️ Systemic Risk Monitor")

# NEW: Sentiment Gauge
sentiment_trend = st.sidebar.select_slider(
    "Headline Sentiment Trend",
    options=["Cooling", "Neutral", "Heating Up", "Explosive"],
    value="Heating Up"
)

event_alert = st.sidebar.toggle("🚨 SHOW SYSTEMIC EVENT ALERTS", value=True)

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

st.sidebar.metric("Fear Index (VIX)", f"{vix_val:.2f}" if vix_val > 0 else "N/A")
st.sidebar.metric("Gold (GC=F)", f"${gold_val:.2f}" if gold_val > 0 else "N/A")

st.sidebar.divider()
target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])

# --- 4. MAIN INTERFACE: EVENT ALERTS ---
if event_alert:
    st.error(f"""
    **🚨 SYSTEMIC RISK ALERT: FED INDEPENDENCE CRISIS**
    - **Headline:** DOJ Investigation into Chair Powell escalates.
    - **Sentiment:** News cycle is currently **{sentiment_trend}**.
    """)

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
        fig.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        return last_price, df.tail(10).to_string()
    return None, None

last_price, momentum_data = monitor_market()

# --- 6. AI VERDICT & ACTION RECOMMENDATION ---
st.divider()
st.subheader("📓 AI Analysis & Trade Recommendation")

headline_context = f"- EVENT: Fed Chair Powell Probe.\n- SENTIMENT: {sentiment_trend}.\n- VITALS: Gold at {gold_val:.2f}." if event_alert else ""
trade_notes = st.text_area("Live Context:", value=headline_context, height=100)

if st.button("Generate AI Market Verdict & Action", use_container_width=True):
    active_key = st.secrets.get("GEMINI_API_KEY", "")
    if not active_key:
        st.error("Missing API Key.")
    else:
        try:
            client = genai.Client(api_key=active_key)
            config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
            
            # Updated Prompt for specific recommendation action
            prompt = f"""Analyze {target} for Jan 12. VIX: {vix_val}. Gold: {gold_val}. Sentiment: {sentiment_trend}. Headlines: {trade_notes}. Momentum: {momentum_data}
            
            TASK: 
            1. Provide a one-word recommendation: LONG, SHORT, or WAIT.
            2. Explain the primary reason based on the 'Powell Probe' news.
            3. List a 'Stop-Loss' level based on recent candle volatility."""
            
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=config)
            st.session_state['ai_verdict'] = response.text
            
            # Visually separate the Recommendation
            st.info("### 🤖 AI Trade Recommendation")
            st.markdown(response.text)
        except Exception as e:
            st.error(f"AI Setup Error: {e}")

# Download
log_c = f"LOG: {datetime.now()}\nASSET: {target}\nAI VERDICT:\n{st.session_state.get('ai_verdict', 'N/A')}"
st.download_button("📁 Download Systemic Risk Log", data=log_c, file_name=f"Powell_Trade_Log.txt", use_container_width=True)
