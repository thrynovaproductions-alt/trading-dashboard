import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

st.set_page_config(layout="wide", page_title="AI Trading Terminal")

# --- 1. AI Setup ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("Check Streamlit Secrets for GEMINI_API_KEY.")

st.title("🚀 NQ & ES Decision Support System")

# Sidebar
target = st.sidebar.selectbox("Market", ["NQ=F", "ES=F"])
period = st.sidebar.selectbox("Period", ["1d", "5d"])

# Data Fetch
df = yf.download(target, period=period, interval="5m", multi_level_index=False)

if not df.empty:
    # --- 2. INDICATOR CALCULATIONS ---
    df['SMA9'] = df['Close'].rolling(window=9).mean()
    df['SMA21'] = df['Close'].rolling(window=21).mean()
    df['MB'] = df['Close'].rolling(window=20).mean()
    df['UB'] = df['MB'] + (df['Close'].rolling(window=20).std() * 2)
    df['LB'] = df['MB'] - (df['Close'].rolling(window=20).std() * 2)

    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    # RVOL (Relative Volume)
    df['AvgVolume'] = df['Volume'].rolling(window=20).mean()
    df['RVOL'] = df['Volume'] / df['AvgVolume']

    # --- 3. ENHANCED ALERT LOGIC ---
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    st.sidebar.subheader("Live Signals")
    if last['SMA9'] > last['SMA21'] and prev['SMA9'] <= prev['SMA21']:
        if last['RVOL'] > 1.5:
            st.success(f"🔥 HIGH CONFIDENCE BUY: RVOL {last['RVOL']:.2f}")
            st.toast("BULLISH CROSS + HIGH VOL", icon="🚀")
        else:
            st.info(f"⚖️ Low Volume Buy (RVOL: {last['RVOL']:.2f})")
            
    elif last['SMA9'] < last['SMA21'] and prev['SMA9'] >= prev['SMA21']:
        if last['RVOL'] > 1.5:
            st.error(f"💥 HIGH CONFIDENCE SELL: RVOL {last['RVOL']:.2f}")
            st.toast("BEARISH CROSS + HIGH VOL", icon="🔻")
        else:
            st.warning(f"⚖️ Low Volume Sell (RVOL: {last['RVOL']:.2f})")

    # --- 4. MULTI-ROW CHART ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA9'], line=dict(color='yellow', width=1), name="SMA 9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA21'], line=dict(color='orange', width=1), name="SMA 21"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['UB'], line=dict(color='gray', dash='dot'), name="Upper Band"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['LB'], line=dict(color='gray', dash='dot'), name="Lower Band"), row=1, col=1)

    # Volume & RSI
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='blue'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name="RSI"), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. AI ASSISTANT ---
    st.divider()
    obs = st.text_input("AI Logic Check: What do you see on the chart?")
    if st.button("Run Analysis"):
        context = f"Market: {target}, Price: {last['Close']:.2f}, RSI: {last['RSI']:.1f}, RVOL: {last['RVOL']:.2f}."
        resp = model.generate_content(f"Act as a professional trader. Analyze this setup: {context}. User observation: {obs}")
        st.write(resp.text)
else:
    st.error("Awaiting Market Data...")
