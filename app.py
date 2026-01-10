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
    # Moving Averages
    df['SMA9'] = df['Close'].rolling(window=9).mean()
    df['SMA21'] = df['Close'].rolling(window=21).mean()
    
    # Bollinger Bands
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

    # ATR (Average True Range) for Risk
    high_low = df['High'] - df['Low']
    high_cp = abs(df['High'] - df['Close'].shift())
    low_cp = abs(df['Low'] - df['Close'].shift())
    df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # --- 3. ENHANCED ALERT LOGIC ---
    last = df.iloc[-1]
    prev = df.iloc[-2]
    atr_val = last['ATR']
    
    st.sidebar.subheader("Live Signals & Risk")
    
    if last['SMA9'] > last['SMA21'] and prev['SMA9'] <= prev['SMA21']:
        sl = last['Close'] - (2 * atr_val)
        tp = last['Close'] + (4 * atr_val)
        st.success(f"🔥 BUY SIGNAL (RVOL: {last['RVOL']:.2f})")
        st.sidebar.write(f"**Entry:** {last['Close']:.2f}")
        st.sidebar.write(f"**Stop Loss:** {sl:.2f}")
        st.sidebar.write(f"**Take Profit:** {tp:.2f}")
        st.toast("BULLISH CROSSOVER!", icon="🚀")
            
    elif last['SMA9'] < last['SMA21'] and prev['SMA9'] >= prev['SMA21']:
        sl = last['Close'] + (2 * atr_val)
        tp = last['Close'] - (4 * atr_val)
        st.error(f"💥 SELL SIGNAL (RVOL: {last['RVOL']:.2f})")
        st.sidebar.write(f"**Entry:** {last['Close']:.2f}")
        st.sidebar.write(f"**Stop Loss:** {sl:.2f}")
        st.sidebar.write(f"**Take Profit:** {tp:.2f}")
        st.toast("BEARISH CROSSOVER!", icon="🔻")

    # --- 4. MULTI-ROW CHART ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)

    # Main Chart
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

    # --- 5. AI "VISION" ANALYSIS ---
    st.divider()
    st.subheader("🤖 AI Data Analysis (The 'Eyes')")
    obs = st.text_input("Anything specific to focus on? (e.g. 'Is this a fake breakout?')")
    
    if st.button("Analyze Last 30 Candles"):
        # We grab the relevant columns to give the AI context
        recent_data = df.tail(30)[['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'SMA9', 'SMA21', 'RVOL']]
        data_to_send = recent_data.to_string()
        
        with st.spinner('The AI is reading the chart data...'):
            prompt = f"""
            You are a master futures trader specializing in NQ and ES. 
            Below is the last 30 intervals (5-min each) of market data.
            
            MARKET DATA:
            {data_to_send}
            
            USER OBSERVATION: {obs}
            
            YOUR ANALYSIS TASK:
            1. Describe the recent price action (e.g., trend strength, volatility).
            2. Identify technical patterns based on the OHLC data provided.
            3. Check RSI for overbought/oversold conditions or divergence.
            4. Check RVOL to see if recent moves are institutional or retail-driven.
            5. Provide a FINAL VERDICT: Bullish, Bearish, or Neutral with a Confidence Score (1-10).
            """
            response = model.generate_content(prompt)
            st.markdown(response.text)
else:
    st.error("Awaiting Market Data...")
