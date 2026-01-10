import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai
from datetime import datetime

# --- 1. CORE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="AI Trading Terminal")

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        tools=[{"google_search_retrieval": {}}] 
    )
except Exception as e:
    st.error(f"AI Setup Error: {e}")

st.title("🚀 NQ & ES Quant Workstation")

# Sidebar
target = st.sidebar.selectbox("Market Asset", ["NQ=F", "ES=F"])
main_interval = "5m"

# --- 2. MULTI-TIMEFRAME TREND MATRIX ---
def get_trend(symbol, interval, period):
    data = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
    if len(data) < 20: return "Neutral ⚪"
    sma_short = data['Close'].rolling(9).mean().iloc[-1]
    sma_long = data['Close'].rolling(21).mean().iloc[-1]
    return "BULLISH 🟢" if sma_short > sma_long else "BEARISH 🔴"

st.sidebar.subheader("Multi-Timeframe Trend")
matrix_1h = get_trend(target, "1h", "5d")
matrix_1d = get_trend(target, "1d", "1mo")
st.sidebar.write(f"1-Hour: {matrix_1h}")
st.sidebar.write(f"Daily: {matrix_1d}")

# --- 3. MAIN DATA PROCESSING ---
df = yf.download(target, period="2d", interval=main_interval, multi_level_index=False)

if not df.empty:
    df['SMA9'] = df['Close'].rolling(9).mean()
    df['SMA21'] = df['Close'].rolling(21).mean()
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (df['Typical_Price'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()
    df['ATR'] = (pd.concat([df['High']-df['Low'], abs(df['High']-df['Close'].shift()), abs(df['Low']-df['Close'].shift())], axis=1).max(axis=1)).rolling(14).mean()

    # --- 4. SIGNALS & CHART ---
    last, prev = df.iloc[-1], df.iloc[-2]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', width=2, dash='dash'), name="VWAP"), row=1, col=1)
    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. AI AGENT & EXPORT ---
    st.divider()
    st.subheader("🤖 AI Technical & News Grounding")
    user_query = st.text_input("Ask about specific news or patterns:")
    
    if st.button("Generate Full Market Verdict"):
        recent_data = df.tail(10)[['Close', 'RSI', 'VWAP', 'RVOL']]
        with st.spinner('AI Researching...'):
            prompt = f"Analyze {target} for Jan 10, 2026. Data: {recent_data.to_string()}. 1H: {matrix_1h}. Search live news for today and give a verdict."
            response = model.generate_content(prompt)
            verdict_text = response.text
            st.markdown(verdict_text)
            
            # Create Journal Entry
            journal_entry = f"""
            --- TRADING JOURNAL ENTRY ---
            Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            Market: {target} | Price: {last['Close']:.2f}
            1H Trend: {matrix_1h} | Daily Trend: {matrix_1d}
            RSI: {last['RSI']:.2f} | RVOL: {last['RVOL']:.2f}
            
            AI VERDICT:
            {verdict_text}
            """
            
            # DOWNLOAD BUTTON
            st.download_button(
                label="📁 Save to Trading Journal",
                data=journal_entry,
                file_name=f"Trade_Journal_{target}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain"
            )
else:
    st.warning("Market closed or data unavailable.")
