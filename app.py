import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

st.set_page_config(layout="wide", page_title="AI Trading Terminal")

# --- 1. AI Setup with Search Tool ---
try:
    # Use the key you just saved in Secrets
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # We use 'gemini-1.5-flash' and enable the google_search tool
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        tools=[{"google_search": {}}] 
    )
except Exception as e:
    st.error(f"AI Setup Error: {e}")

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

    # RSI & RVOL
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['AvgVolume'] = df['Volume'].rolling(window=20).mean()
    df['RVOL'] = df['Volume'] / df['AvgVolume']
    
    # ATR for Risk management
    high_low = df['High'] - df['Low']
    high_cp = abs(df['High'] - df['Close'].shift())
    low_cp = abs(df['Low'] - df['Close'].shift())
    df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # --- 3. LIVE SIGNALS & RISK MATH ---
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
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA9'], line=dict(color='yellow', width=1), name="SMA 9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA21'], line=dict(color='orange', width=1), name="SMA 21"), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name="RSI"), row=3, col=1)
    
    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. AI FULL SCAN (Chart Data + Live News) ---
    st.divider()
    st.subheader("🤖 AI Market Intelligence")
    user_note = st.text_input("Focus on anything specific? (e.g. 'Check for news on interest rates')")
    
    if st.button("Analyze Charts + Live 2026 News"):
        # Send last 30 candles for "Vision"
        recent_data = df.tail(30)[['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'RVOL']]
        
        with st.spinner('AI is reading the chart and scanning global news for today...'):
            prompt = f"""
            TODAY'S DATE: January 10, 2026.
            ANALYZING: {target} at {last['Close']:.2f}
            
            1. TECH ANALYSIS: Look at the last 30 intervals of data:
            {recent_data.to_string()}
            
            2. NEWS SEARCH: Search for today's live news regarding {target} and the US Stock Market.
            
            3. VERDICT: Combine the technicals and news. Give me a Risk/Reward rating (1-10) 
            and a clear 'Trade or Wait' suggestion based on user note: {user_note}
            """
            response = model.generate_content(prompt)
            st.markdown(response.text)
else:
    st.error("Awaiting Market Data...")
