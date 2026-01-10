import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

st.set_page_config(layout="wide", page_title="AI Trading Terminal")

# --- 1. AI Setup ---
try:
    # We enable the 'google_search' tool in the model configuration
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        tools=[{"google_search": {}}] 
    )
except:
    st.error("Check Streamlit Secrets for GEMINI_API_KEY.")

st.title("🚀 NQ & ES Decision Support System (AI + News)")

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

    # RSI & Volume
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['AvgVolume'] = df['Volume'].rolling(window=20).mean()
    df['RVOL'] = df['Volume'] / df['AvgVolume']
    
    # ATR for Risk
    high_low = df['High'] - df['Low']
    high_cp = abs(df['High'] - df['Close'].shift())
    low_cp = abs(df['Low'] - df['Close'].shift())
    df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # --- 3. SIDEBAR ALERTS & ATR RISK ---
    last = df.iloc[-1]
    prev = df.iloc[-2]
    atr_val = last['ATR']
    
    st.sidebar.subheader("Live Signals & Risk")
    if last['SMA9'] > last['SMA21'] and prev['SMA9'] <= prev['SMA21']:
        sl, tp = last['Close'] - (2 * atr_val), last['Close'] + (4 * atr_val)
        st.success(f"🔥 BUY: Entry {last['Close']:.2f} | SL {sl:.2f} | TP {tp:.2f}")
    elif last['SMA9'] < last['SMA21'] and prev['SMA9'] >= prev['SMA21']:
        sl, tp = last['Close'] + (2 * atr_val), last['Close'] - (4 * atr_val)
        st.error(f"💥 SELL: Entry {last['Close']:.2f} | SL {sl:.2f} | TP {tp:.2f}")

    # --- 4. THE CHART ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA9'], line=dict(color='yellow', width=1), name="SMA 9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA21'], line=dict(color='orange', width=1), name="SMA 21"), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name="RSI"), row=3, col=1)
    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. AI "EYES" + LIVE NEWS SENTIMENT ---
    st.divider()
    st.subheader("🤖 AI Full Spectrum Analysis")
    obs = st.text_input("Anything specific to focus on?")
    
    if st.button("Analyze Charts + Live Market News"):
        recent_data = df.tail(30)[['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'RVOL']]
        data_to_send = recent_data.to_string()
        
        with st.spinner('AI is analyzing charts and scanning global 2026 news...'):
            prompt = f"""
            TODAY'S DATE: January 10, 2026.
            MARKET: {target}
            CURRENT PRICE: {last['Close']:.2f}
            
            PART 1: DATA ANALYSIS
            Examine these last 30 intervals:
            {data_to_send}
            
            PART 2: LIVE NEWS SEARCH
            Use your search tool to find the latest news for "{target}" and "US Stock Market" for today. 
            Identify if there are any FOMC reports, CPI data, or major tech earnings affecting sentiment.
            
            PART 3: FINAL VERDICT
            Combine the technical data with the news sentiment. 
            Provide a Risk Score (1-10) and a final trade recommendation.
            User Note: {obs}
            """
            response = model.generate_content(prompt)
            st.markdown(response.text)
else:
    st.error("Awaiting Market Data...")
