import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

st.set_page_config(layout="wide", page_title="AI Trading Terminal")

# --- AI Setup ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("API Key error. Check Secrets.")

st.title("📊 NQ & ES Decision Support System")

# Sidebar
target = st.sidebar.selectbox("Select Market", ["NQ=F", "ES=F"])
period = st.sidebar.selectbox("Period", ["1d", "5d"])

# Data Fetch
df = yf.download(target, period=period, interval="5m", multi_level_index=False)

if not df.empty:
    # 1. Indicator Calculations
    df['SMA9'] = df['Close'].rolling(window=9).mean()
    df['SMA21'] = df['Close'].rolling(window=21).mean()
    df['MB'] = df['Close'].rolling(window=20).mean()
    df['UB'] = df['MB'] + (df['Close'].rolling(window=20).std() * 2)
    df['LB'] = df['MB'] - (df['Close'].rolling(window=20).std() * 2)

    # 2. RSI Calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    # 3. Alert Logic
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    if last['SMA9'] > last['SMA21'] and prev['SMA9'] <= prev['SMA21']:
        st.toast("BULLISH CROSSOVER!", icon="🚀")
        st.success(f"Trade Suggestion: Potential LONG at {last['Close']:.2f}")
    elif last['SMA9'] < last['SMA21'] and prev['SMA9'] >= prev['SMA21']:
        st.toast("BEARISH CROSSOVER!", icon="🔻")
        st.error(f"Trade Suggestion: Potential SHORT at {last['Close']:.2f}")

    # 4. Multi-Row Chart Layout
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)

    # Main Candlestick + SMA + Bollinger
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA9'], line=dict(color='yellow', width=1), name="SMA 9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA21'], line=dict(color='orange', width=1), name="SMA 21"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['UB'], line=dict(color='gray', dash='dot'), name="Bollinger Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['LB'], line=dict(color='gray', dash='dot'), name="Bollinger Lower"), row=1, col=1)

    # Volume
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume"), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name="RSI"), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # 5. AI Assistant
    st.subheader("🤖 AI Market Logic Check")
    obs = st.text_input("What are you seeing?")
    if st.button("Analyze"):
        context = f"Market: {target}, Price: {last['Close']:.2f}, RSI: {last['RSI']:.1f}. User sees: {obs}"
        resp = model.generate_content(f"Analyze this trade setup for a futures trader: {context}")
        st.write(resp.text)
        # --- ADVANCED VOLUME FILTER ---
# Calculate the average volume of the last 20 candles
df['AvgVolume'] = df['Volume'].rolling(window=20).mean()
df['RVOL'] = df['Volume'] / df['AvgVolume'] # Relative Volume ratio

# --- ENHANCED ALERT LOGIC ---
if last['SMA9'] > last['SMA21'] and prev['SMA9'] <= prev['SMA21']:
    if last['RVOL'] > 1.5:
        st.success(f"🔥 HIGH CONFIDENCE BUY: Crossover + High Volume (RVOL: {last['RVOL']:.2f})")
    else:
        st.info(f"⚖️ Weak Buy Signal: Crossover detected but Volume is low (RVOL: {last['RVOL']:.2f})")

