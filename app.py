import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Futures AI Terminal", layout="wide")

st.title("📈 NQ & ES Trading Command Center")

# Sidebar
st.sidebar.header("Market Selection")
target = st.sidebar.selectbox("Select Future", ["NQ=F", "ES=F"])
period = st.sidebar.selectbox("Period", ["1d", "5d", "1mo"])

# Fetch Live Data
with st.spinner('Fetching market data...'):
    df = yf.download(target, period=period, interval="5m", multi_level_index=False)

if not df.empty:
    # Metrics calculation
    last_price = df['Close'].iloc[-1]
    prev_close = df['Open'].iloc[0]
    change = last_price - prev_close
    pct_change = (change / prev_close) * 100

    # Display Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Last Price", f"{last_price:,.2f}")
    c2.metric("Net Change", f"{change:,.2f}", delta=f"{pct_change:.2f}%")
    c3.metric("Status", "MARKET ACTIVE")

    # Interactive Chart
    fig = go.Figure(data=[go.Candlestick(x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'])])
    fig.update_layout(template="dark", xaxis_rangeslider_visible=False, height=500)
    
    # This is the line that had the error - now fixed
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("No data found. The market might be closed or the symbol is incorrect.")

st.info("💡 Next Step: Link the Gemini API to analyze these price movements.")
