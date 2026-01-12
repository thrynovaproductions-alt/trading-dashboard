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

sentiment_trend = st.sidebar.select_slider(
    "Headline Sentiment Trend",
    options=["Cooling", "Neutral", "Heating Up", "Explosive"],
    value="Heating Up"
)

def get_vitals_safe():
    try:
        vix_df = yf.download("^VIX", period="1d", interval="1m", progress=False, multi_level_index=False)
        gold_df = yf.download("GC=F", period="1d", interval="1m", progress=False, multi_level_index=False)
        vix = vix_df['Close'].iloc[-1] if not vix_df.empty else 0.0
        gold = gold_df['Close'].iloc[-1] if not gold_df.empty else 0.0
        return vix, gold
    except: return 0.0, 0.0

vix_val, gold_val = get_vitals_safe()
st.sidebar.metric("Fear Index (VIX)", f"{vix_val:.2f}" if vix_val > 0 else "N/A")
st.sidebar.metric("Gold (GC=F)", f"${gold_val:.2f}" if gold_val > 0 else "N/A")

st.sidebar.divider()
target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])

# --- 4. THE REFRESHING MONITOR & RISK/REWARD LOGIC ---
@st.fragment(run_every=60)
def monitor_market():
    df = yf.download(target, period="2d", interval="5m", multi_level_index=False)
    if not df.empty:
        df['VWAP'] = ((df['High'] + df['Low'] + df['Close'])/3 * df['Volume']).cumsum() / df['Volume'].cumsum()
        last_price = df['Close'].iloc[-1]
        
        # --- RISK/REWARD CALCULATIONS ---
        recent_10 = df.tail(10)
        volatility_range = (recent_10['High'] - recent_10['Low']).mean()
        sl_buffer = volatility_range * 1.5
        
        # Long Setup
        sl_long = last_price - sl_buffer
        risk_per_contract = last_price - sl_long
        tp_long = last_price + (risk_per_contract * 2) # 2:1 Reward
        
        # Short Setup
        sl_short = last_price + sl_buffer
        tp_short = last_price - (risk_per_contract * 2)
        
        st.subheader(f"🚀 {target} Live: {last_price:.2f}")
        
        # Risk Dashboard UI
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🟢 Long Setup (2:1 Ratio)")
            st.write(f"**Target Profit:** {tp_long:.2f}")
            st.write(f"**Stop Loss:** {sl_long:.2f}")
            st.write(f"**Potential Gain:** +{tp_long - last_price:.2f}")
            
        with col2:
            st.markdown("### 🔴 Short Setup (2:1 Ratio)")
            st.write(f"**Target Profit:** {tp_short:.2f}")
            st.write(f"**Stop Loss:** {sl_short:.2f}")
            st.write(f"**Potential Gain:** +{last_price - tp_short:.2f}")

        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        st.plotly_chart(fig, use_container_width=True)
        
        return last_price, recent_10.to_string(), tp_long, sl_long, tp_short, sl_short
    return None, None, None, None, None, None

last_price, momentum_data, calc_tp_long, calc_sl_long, calc_tp_short, calc_sl_short = monitor_market()

# --- 5. AI VERDICT & STRATEGY ---
st.divider()
st.subheader("📓 AI Analysis & Trade Strategy")

headline_context = f"- EVENT: Fed Chair Powell Probe\n- LONG PLAN: TP {calc_tp_long:.2f} / SL {calc_sl_long:.2f}\n- SHORT PLAN: TP {calc_tp_short:.2f} / SL {calc_sl_short:.2f}"
trade_notes = st.text_area("Trade Context:", value=headline_context, height=120)

if st.button("Generate Final Trade Plan", use_container_width=True):
    active_key = st.secrets.get("GEMINI_API_KEY", "")
    if not active_key:
        st.error("Missing API Key.")
    else:
        try:
            client = genai.Client(api_key=active_key)
            config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
            
            prompt = f"""Analyze {target} for Jan 12. VIX: {vix_val}. Sentiment: {sentiment_trend}.
            Plan: LONG Target {calc_tp_long}, SHORT Target {calc_tp_short}.
            Recent Momentum: {momentum_data}
            
            TASK: 
            1. Directional Verdict: LONG, SHORT, or WAIT.
            2. Probability of hitting the Target Profit before the Stop Loss.
            3. How should the 'Powell news' affect position sizing?"""
            
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=config)
            st.info("### 🤖 AI Trade Plan")
            st.markdown(response.text)
        except Exception as e:
            st.error(f"AI Setup Error: {e}")

# Download
log_c = f"LOG: {datetime.now()}\nASSET: {target}\nLONG PLAN: TP {calc_tp_long}/SL {calc_sl_long}\nSHORT PLAN: TP {calc_tp_short}/SL {calc_sl_short}\nAI PLAN:\n{st.session_state.get('ai_verdict', 'N/A')}"
st.download_button("📁 Download Detailed Strategy Log", data=log_c, file_name=f"QuantStrategy_Log.txt", use_container_width=True)
