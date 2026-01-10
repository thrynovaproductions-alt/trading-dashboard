import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="AI Trading Terminal")

try:
    # Safely retrieve key from Streamlit Secrets
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # FIXED: Using 'google_search_retrieval' for Gemini 1.5
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        tools=[{"google_search_retrieval": {}}] 
    )
except Exception as e:
    st.error(f"AI Setup Error: {e}")

st.title("📊 NQ & ES Decision Support System")

# Sidebar for Market Selection
target = st.sidebar.selectbox("Select Market", ["NQ=F", "ES=F"])
period = st.sidebar.selectbox("Period", ["1d", "5d"])

# --- 2. DATA PROCESSING ---
with st.spinner('Updating live market feed...'):
    df = yf.download(target, period=period, interval="5m", multi_level_index=False)

if not df.empty:
    # Technical Indicator Calculations
    df['SMA9'] = df['Close'].rolling(window=9).mean()
    df['SMA21'] = df['Close'].rolling(window=21).mean()
    
    # RSI & RVOL Logic
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['AvgVolume'] = df['Volume'].rolling(window=20).mean()
    df['RVOL'] = df['Volume'] / df['AvgVolume']
    
    # ATR for Volatility-Adjusted Risk
    high_low = df['High'] - df['Low']
    high_cp = abs(df['High'] - df['Close'].shift())
    low_cp = abs(df['Low'] - df['Close'].shift())
    df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # --- 3. LIVE SIGNALS ---
    last, prev = df.iloc[-1], df.iloc[-2]
    atr_val = last['ATR']
    
    st.sidebar.subheader("Live Analysis & Risk")
    if last['SMA9'] > last['SMA21'] and prev['SMA9'] <= prev['SMA21']:
        sl, tp = last['Close'] - (2 * atr_val), last['Close'] + (4 * atr_val)
        st.success(f"🔥 BUY: Entry {last['Close']:.2f} | SL {sl:.2f} | TP {tp:.2f}")
    elif last['SMA9'] < last['SMA21'] and prev['SMA9'] >= prev['SMA21']:
        sl, tp = last['Close'] + (2 * atr_val), last['Close'] - (4 * atr_val)
        st.error(f"💥 SELL: Entry {last['Close']:.2f} | SL {sl:.2f} | TP {tp:.2f}")

    # --- 4. DATA VISUALIZATION ---
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)

    # Main Candlestick Chart
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA9'], line=dict(color='yellow', width=1), name="SMA 9"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA21'], line=dict(color='orange', width=1), name="SMA 21"), row=1, col=1)

    # Volume & RSI Panels
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='blue'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name="RSI"), row=3, col=1)
    
    fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. AI "FULL SCAN" ANALYSIS ---
    st.divider()
    st.subheader("🤖 AI Data & Sentiment Scan")
    obs = st.text_input("Looking for something specific? (e.g. 'How is inflation data affecting this?')")
    
    if st.button("Run Professional Analysis"):
        # Send 30 candles of context to the AI
        recent_data = df.tail(30)[['Open', 'High', 'Low', 'Close', 'Volume', 'RSI', 'RVOL']]
        
        with st.spinner('The AI is correlating 30-candle data with live 2026 news...'):
            prompt = f"""
            TODAY: January 10, 2026. 
            MARKET: {target}
            PRICE: {last['Close']:.2f}
            
            1. TECHNICAL CONTEXT (Last 30 Intervals):
            {recent_data.to_string()}
            
            2. NEWS SEARCH TASK:
            Search for the latest live news headlines for {target} and the US Market for TODAY. 
            Look for interest rate rumors, earnings, or geopolitical shifts.
            
            3. VERDICT:
            Correlate technicals with news. Provide a 1-10 Confidence Score. 
            Note: {obs}
            """
            response = model.generate_content(prompt)
            st.markdown(response.text)
else:
    st.error("Waiting for data stream... check your internet connection.")
