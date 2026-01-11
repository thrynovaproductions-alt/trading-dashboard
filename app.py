import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
import streamlit.components.v1 as components

# --- 1. CORE CONFIGURATION (CRITICAL: MUST BE FIRST) ---
st.set_page_config(
    layout="wide", 
    page_title="AI Trading Terminal",
    initial_sidebar_state="collapsed" 
)

# --- 2. PWA INJECTION ---
components.html(
    """
    <script>
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', function() {
        navigator.serviceWorker.register('./sw.js');
      });
    }
    var link = window.parent.document.createElement("link");
    link.rel = "manifest";
    link.href = "./manifest.json";
    window.parent.document.head.appendChild(link);
    </script>
    """,
    height=0,
)

# --- 3. AI SETUP ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash', 
        tools=[{"google_search_retrieval": {}}]
    )
except Exception as e:
    st.error(f"AI Setup Error: {e}")

st.title("🚀 NQ & ES Quant Workstation")

# Sidebar
target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])
st.sidebar.divider()

# --- TREND MATRIX ---
def get_trend(symbol, interval, period):
    data = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
    if len(data) < 20: return "Neutral ⚪"
    sma_short = data['Close'].rolling(9).mean().iloc[-1]
    sma_long = data['Close'].rolling(21).mean().iloc[-1]
    return "BULLISH 🟢" if sma_short > sma_long else "BEARISH 🔴"

st.sidebar.subheader("Multi-Timeframe Trend")
matrix_1h = get_trend(target, "1h", "5d")
matrix_1d = get_trend(target, "1d", "1mo")
st.sidebar.write(f"1-Hour: {matrix_1h}")
st.sidebar.write(f"Daily: {matrix_1d}")
st.sidebar.divider()

# --- 4. DATA ENGINE ---
df = yf.download(target, period="5d", interval="5m", multi_level_index=False)

if not df.empty:
    # Indicators
    df['SMA9'] = df['Close'].rolling(9).mean()
    df['SMA21'] = df['Close'].rolling(21).mean()
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['Typical_Price'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['ATR'] = (pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)).rolling(14).mean()

    # --- 5. BACKTEST LAB ---
    st.sidebar.subheader("📊 Backtest & Optimizer Lab")
    if st.sidebar.button("Run Optimizer + Backtest", use_container_width=True):
        df['Signal'] = np.where((df['SMA9'] > df['SMA21']) & (df['Close'] > df['VWAP']), 1, 0)
        df['Returns'] = df['Close'].pct_change()
        df['Strategy_Returns'] = df['Signal'].shift(1) * df['Returns']
        
        total_ret = (df['Strategy_Returns'] + 1).cumprod().iloc[-1] - 1
        st.subheader("Optimization Results")
        st.metric("5-Day Strategy Return", f"{total_ret*100:.2f}%")
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=(df['Strategy_Returns'] + 1).cumprod(), name="Equity Curve", line=dict(color='gold')))
        fig_bt.update_layout(height=300, template="plotly_dark")
        st.plotly_chart(fig_bt, use_container_width=True)

    # --- 6. PUSH NOTIFICATION PERMISSION ---
    st.sidebar.subheader("🔔 Alerts")
    if st.sidebar.button("Enable Mobile Alerts", use_container_width=True):
        components.html(
            """
            <script>
            Notification.requestPermission().then(function(permission) {
                if (permission === 'granted') {
                    alert('Notifications Enabled!');
                } else {
                    alert('Permission denied. Please check phone settings.');
                }
            });
            </script>
            """,
            height=0,
        )

    # --- 7. MAIN CHART ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='blue'), row=2, col=1)

    fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- 8. AI SECTION ---
    st.divider()
    if st.button("Analyze Current Setup", use_container_width=True):
        with st.spinner('Checking 2026 Live Market News...'):
            prompt = f"Analyze {target} for Jan 10, 2026. 1H: {matrix_1h}. Daily: {matrix_1d}. Price: {df.iloc[-1]['Close']}."
            st.markdown(model.generate_content(prompt).text)
else:
    st.warning("Market closed or data unavailable.")
