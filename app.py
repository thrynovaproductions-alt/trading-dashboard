import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import google.generativeai as genai

# Fix for the Plotly dark theme error
pio.templates.default = "plotly"

st.set_page_config(page_title="Futures AI Terminal", layout="wide")

# --- AI Configuration ---
try:
    # Connects to the key you just saved in Secrets
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.warning("AI Key not found. Please check your Streamlit Secrets.")

st.title("📈 NQ & ES Trading Command Center")

# Sidebar
target = st.sidebar.selectbox("Select Future", ["NQ=F", "ES=F"])
period = st.sidebar.selectbox("Period", ["1d", "5d", "1mo"])

# Fetch Live Data
with st.spinner('Fetching market data...'):
    df = yf.download(target, period=period, interval="5m", multi_level_index=False)

if not df.empty:
    # Top Row Metrics
    last_price = df['Close'].iloc[-1]
    prev_close = df['Open'].iloc[0]
    change = last_price - prev_close
    pct_change = (change / prev_close) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Last Price", f"{last_price:,.2f}")
    c2.metric("Net Change", f"{change:,.2f}", delta=f"{pct_change:.2f}%")
    c3.metric("Status", "MARKET ACTIVE")

    # Interactive Chart
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close']
    )])
    # Simplified layout to prevent crashes
    fig.update_layout(xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    # --- AI STRATEGY ASSISTANT ---
    st.divider()
    st.subheader("🤖 AI Market Analysis")
    user_input = st.text_area("Your Observation:", placeholder="e.g., 'Price is hitting a 3-day high. What do you see?'")
    
    if st.button("Generate Strategy"):
        market_context = f"The current price of {target} is {last_price:,.2f}. The user says: {user_input}"
        with st.spinner('AI is thinking...'):
            response = model.generate_content(f"Act as a professional futures trader. Analyze this: {market_context}")
            st.write(response.text)
else:
    st.error("Waiting for data feed...")
