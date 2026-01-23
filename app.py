import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from google import genai

# --- 1. CORE CONFIG & AUTO-HEALING ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Pro", initial_sidebar_state="expanded")

if 'error_strikes' not in st.session_state:
    st.session_state.update({'error_strikes': 0, 'wins': 0, 'losses': 0, 'total_pnl': 0.0, 'trade_log': []})

# --- 2. ANALYTICS & AI ENGINE ---
def get_full_ai_report(label, last_p, dev, atr, rsi, vix, tnx, tech, defen, fin, conf, api_key):
    """Corrected 11-parameter structured analyst"""
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"Elite Report for {label} (${last_p:.2f}). Conf: {conf:.0f}%. VIX: {vix:.1f}. RSI: {rsi:.1f}. Sector: Tech {tech:.2f}%. Verdict, Factors, Risk, Guidance."
        resp = client.models.generate_content(model='gemini-2.0-flash-exp', contents=prompt)
        return resp.text
    except Exception as e: return f"AI Error: {e}"

@st.cache_data(ttl=60)
def fetch_pulse(target):
    try:
        tickers = ["XLK", "XLU", "XLF", "^TNX", "^VIX", "NQ=F", "ES=F", target]
        data = yf.download(tickers, period="2d", interval="5m", progress=False, multi_level_index=False)['Close']
        vix, tnx = data["^VIX"].iloc[-1], data["^TNX"].iloc[-1]
        rs_lead = ((data["NQ=F"] / data["ES=F"]).pct_change(5).iloc[-1]) * 1000
        sects = {k: data[v].pct_change(20).iloc[-1]*100 for k, v in {"Tech": "XLK", "Def": "XLU", "Fin": "XLF"}.items()}
        return data, sects, vix, tnx, rs_lead, True
    except: return None, {}, 0.0, 0.0, 0.0, False

# --- 3. SIDEBAR: HEATMAP & INTEGRITY ---
st.sidebar.title("🛡️ Risk Management")
key = st.sidebar.text_input("Gemini API Key:", type="password")
target_sym = st.sidebar.selectbox("Asset", ["NQ=F", "ES=F"])

data, sects, vix, tnx, rs_lead, is_clean = fetch_pulse(target_sym)

# Auto-Healing Shield
if not is_clean:
    st.session_state.error_strikes += 1
    if st.session_state.error_strikes >= 3:
        st.cache_data.clear(); st.session_state.error_strikes = 0; st.rerun()
    st.sidebar.error(f"⚠️ Sync Lag ({st.session_state.error_strikes}/3)")
else:
    st.session_state.error_strikes = 0; st.sidebar.success("✅ Data Integrity: 100%")

# Heatmap
st.sidebar.subheader("🔥 Trend Heatmap")
def get_trend(tf):
    d = yf.download(target_sym, period="2d", interval=tf, progress=False)['Close']
    return "🟢" if d.rolling(9).mean().iloc[-1] > d.rolling(21).mean().iloc[-1] else "🔴"

c1, c2, c3 = st.sidebar.columns(3)
c1.metric("1m", get_trend("1m")); c2.metric("5m", get_trend("5m")); c3.metric("15m", get_trend("15m"))

# --- 4. MAIN MONITOR ---
st.title("🚀 NQ & ES Quantitative Trading Platform")

@st.fragment(run_every=60)
def main_monitor():
    df = yf.download(target_sym, period="2d", interval="5m", progress=False)
    # Technicals
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
    last_p, last_vol = df['Close'].iloc[-1], df['Volume'].iloc[-1]
    vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
    
    # RSI & Confidence Scoring
    delta = df['Close'].diff(); g = delta.where(delta > 0, 0).rolling(14).mean(); l = -delta.where(delta < 0, 0).rolling(14).mean()
    rsi = 100 - (100 / (1 + (g / l))).iloc[-1]
    conf = (max(0, 100-(vix*2.5))*0.3) + (rsi*0.25) + (min(100, 50+(rs_lead*10))*0.25) + (20 if get_trend("5m")=="🟢" else 0)

    # Volume Surge Alert
    if last_vol > (vol_avg * 2):
        st.toast("🚀 INSTITUTIONAL VOLUME SURGE!", icon="🔥")

    m1, m2, m3 = st.columns(3)
    m1.metric("Price", f"${last_p:.2f}"); m2.metric("Confidence", f"{conf:.0f}%"); m3.metric("RSI", f"{rsi:.1f}")

    # Chart & Report
    st.plotly_chart(go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])]).update_layout(template="plotly_dark", xaxis_rangeslider_visible=False))
    
    if st.button("🧠 Generate Full Prediction Report", use_container_width=True, type="primary"):
        report = get_full_ai_report(target_sym, last_p, 0.0, 0.0, rsi, vix, tnx, sects['Tech'], sects['Def'], sects['Fin'], conf, key)
        st.markdown(report)

main_monitor()
