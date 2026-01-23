import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
from google import genai

# --- 1. CORE CONFIGURATION & AUTO-HEALING ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Pro", initial_sidebar_state="expanded")

if 'integrity_error_count' not in st.session_state:
    st.session_state.integrity_error_count = 0

# --- 2. ANALYTICS FUNCTIONS ---
def calculate_vwap_metrics(df):
    """Calculates all core quantitative metrics"""
    if df.empty or len(df) < 21: return None
    
    # Core Indicators
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
    df['SMA9'] = df['Close'].rolling(9).mean() # Green SMA
    df['SMA21'] = df['Close'].rolling(21).mean() # Red SMA
    
    # Momentum & RSI
    df['Momentum'] = df['Close'].pct_change(5) * 100
    delta = df['Close'].diff()
    gain, loss = (delta.where(delta > 0, 0)).rolling(14).mean(), (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    return df, ((df['Close'].iloc[-1] - df['VWAP'].iloc[-1]) / df['VWAP'].iloc[-1]) * 100

# --- 3. MAIN MONITOR ---
@st.fragment(run_every=60)
def main_monitor():
    try:
        # Asset Selection
        target_symbol = st.session_state.get('target_symbol', 'NQ=F')
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        metrics_data = calculate_vwap_metrics(df)
        
        if metrics_data:
            df, dev = metrics_data
            last_p, last_rsi = df['Close'].iloc[-1], df['RSI'].iloc[-1]
            s9, s21 = df['SMA9'].iloc[-1], df['SMA21'].iloc[-1]
            prev_s9, prev_s21 = df['SMA9'].iloc[-2], df['SMA21'].iloc[-2]

            # REVERSAL CONFIRMATION ALERTS
            # 1. Golden Cross Detection
            if prev_s9 < prev_s21 and s9 >= s21:
                st.toast("🌟 GOLDEN CROSS: Trend Reversal Confirmed!", icon="🚀")
                st.success(f"9 SMA ({s9:.1f}) crossed above 21 SMA ({s21:.1f}). Long Bias strengthening.")
            
            # 2. Death Cross Detection
            elif prev_s9 > prev_s21 and s9 <= s21:
                st.toast("💀 DEATH CROSS: Trend Reversal Confirmed!", icon="⚠️")
                st.error(f"9 SMA ({s9:.1f}) crossed below 21 SMA ({s21:.1f}). Short Bias resuming.")

            # RSI VOLATILITY ALERTS
            if last_rsi < 30: st.warning(f"OVERSOLD: RSI at {last_rsi:.1f}")
            elif last_rsi > 70: st.warning(f"OVERBOUGHT: RSI at {last_rsi:.1f}")

            # CHARTING & EXECUTION logic remains consistent...
            st.metric("Price", f"${last_p:.2f}", f"SMA Gap: {s21-s9:.2f}")
            
    except Exception as e: st.error(f"Monitor Error: {e}")

main_monitor()
