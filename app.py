import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide")
st.title("🚀 Advanced NQ/ES Dashboard")

target = st.sidebar.selectbox("Market", ["NQ=F", "ES=F"])
df = yf.download(target, period="1d", interval="5m", multi_level_index=False)

if not df.empty:
    # --- 1. TECHNICAL MATH ---
    # SMA 9 & 21
    df['SMA9'] = df['Close'].rolling(window=9).mean()
    df['SMA21'] = df['Close'].rolling(window=21).mean()
    
    # Bollinger Bands
    df['MB'] = df['Close'].rolling(window=20).mean()
    df['UB'] = df['MB'] + (df['Close'].rolling(window=20).std() * 2)
    df['LB'] = df['MB'] - (df['Close'].rolling(window=20).std() * 2)

    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # --- 2. THE MULTI-CHART ---
    # Create 3 rows: Main Chart, Volume, RSI
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])

    # Candlestick + SMA + Bollinger
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA9'], line=dict(color='yellow', width=1), name="SMA 9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA21'], line=dict(color='orange', width=1), name="SMA 21"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['UB'], line=dict(color='gray', dash='dash'), name="Upper Band"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['LB'], line=dict(color='gray', dash='dash'), name="Lower Band"), row=1, col=1)

    # Volume
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='blue'), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name="RSI"), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

st.info("💡 Strategy: Look for SMA Crossovers confirmed by a Volume spike.")
