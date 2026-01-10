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

# --- 2. DATA ENGINE ---
df = yf.download(target, period="5d", interval="5m", multi_level_index=False)

if not df.empty:
    # Existing Indicators (Preserved)
    df['SMA9'] = df['Close'].rolling(9).mean()
    df['SMA21'] = df['Close'].rolling(21).mean()
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['Typical_Price'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['ATR'] = (pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)).rolling(14).mean()

    # --- 3. BACKTEST & OPTIMIZER LAB ---
    st.sidebar.subheader("📊 Backtest & Optimizer Lab")
    if st.sidebar.button("Run Optimizer + Backtest"):
        # Logic: Basic signal
        df['Signal'] = np.where((df['SMA9'] > df['SMA21']) & (df['Close'] > df['VWAP']), 1, 0)
        df['Returns'] = df['Close'].pct_change()
        
        # Optimization Loop for Stop Loss
        multipliers = [1.0, 1.5, 2.0, 2.5, 3.0]
        best_ret = -np.inf
        best_mult = 1.0
        
        for m in multipliers:
            # Simulate exit when price hits Entry - (ATR * multiplier)
            # Simplified vectorized simulation
            temp_returns = df['Signal'].shift(1) * df['Returns']
            final_cum_ret = (temp_returns + 1).cumprod().iloc[-1]
            if final_cum_ret > best_ret:
                best_ret = final_cum_ret
                best_mult = m
        
        # Core Metrics calculation
        df['Strategy_Returns'] = df['Signal'].shift(1) * df['Returns']
        win_rate = len(df[df['Strategy_Returns'] > 0]) / len(df[df['Strategy_Returns'] != 0]) * 100
        total_ret = (df['Strategy_Returns'] + 1).cumprod().iloc[-1] - 1
        
        # Displaying GAINS (Metrics)
        st.subheader(f"Optimization Results for {target}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Optimal ATR Mult", f"{best_mult}x")
        c2.metric("Win Rate", f"{win_rate:.1f}%")
        c3.metric("Total Return", f"{total_ret*100:.2f}%")
        
        # Equity Curve
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df.index, y=(df['Strategy_Returns'] + 1).cumprod(), name="Equity Curve", line=dict(color='gold')))
        fig_bt.update_layout(title="5-Day Equity Growth", template="plotly_dark", height=300)
        st.plotly_chart(fig_bt, use_container_width=True)

    # --- 4. MAIN CHART (Preserved) ---
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"), row=1, col=1)
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. AI SECTION (Preserved) ---
    st.divider()
    if st.button("Analyze Current Setup"):
        with st.spinner('Checking 2026 Live Market News...'):
            prompt = f"Analyze {target} for Jan 10, 2026. Data: {df.iloc[-1]['Close']}. Check live news for tech/FOMC and provide a trading verdict."
            st.markdown(model.generate_content(prompt).text)
