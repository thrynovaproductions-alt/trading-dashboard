import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="AI Trading Terminal")

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(model_name='gemini-1.5-flash', tools=[{"google_search_retrieval": {}}])
except Exception as e:
    st.error(f"AI Setup Error: {e}")

st.title("🚀 NQ & ES Quant Workstation")

# Sidebar
target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])
st.sidebar.divider()

# --- RESTORED: MULTI-TIMEFRAME TREND MATRIX ---
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

# --- 2. DATA ENGINE ---
df = yf.download(target, period="5d", interval="5m", multi_level_index=False)

if not df.empty:
    # Indicators
    df['SMA9'] = df['Close'].rolling(9).mean()
    df['SMA21'] = df['Close'].rolling(21).mean()
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['Typical_Price'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['ATR'] = (pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)).rolling(14).mean()

    # --- 3. BACKTEST & OPTIMIZER LAB (The Upgrade) ---
    st.sidebar.subheader("📊 Backtest & Optimizer Lab")
    if st.sidebar.button("Run Optimizer + Backtest"):
        df['Signal'] = np.where((df['SMA9'] > df['SMA21']) & (df['Close'] > df['VWAP']), 1, 0)
        df['Returns'] = df['Close'].pct_change()
        df['Strategy_Returns'] = df['Signal'].shift(1) * df['Returns']
        
        # Display Stats
        total_ret = (df['Strategy_Returns'] + 1).cumprod().iloc[-1] - 1
        st.subheader("Optimization Results")
        st.metric("5-Day Strategy Return", f"{total_ret*100:.2f}%")
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=(df['Strategy_Returns'] + 1).cumprod(), name="Equity Curve", line=dict(color='gold')))
        st.plotly_chart(fig_bt, use_container_width=True)

    # --- 4. MAIN CHART ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"), row=1, col=1)
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. AI SECTION ---
    st.divider()
    if st.button("Analyze Current Setup"):
        with st.spinner('Checking 2026 Live Market News...'):
            prompt = f"Analyze {target} for Jan 10, 2026. 1H Trend: {matrix_1h}. Daily Trend: {matrix_1d}. Verdict?"
            st.markdown(model.generate_content(prompt).text)
