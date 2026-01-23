import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, time
import pytz
from google import genai

# --- 1. CORE CONFIGURATION & CACHING ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Pro", initial_sidebar_state="expanded")

@st.cache_data(ttl=300)
def get_market_pulse():
    """Macro data, sectors, and RS"""
    try:
        tickers = ["XLK", "XLU", "XLF", "^TNX", "^VIX", "NQ=F", "ES=F"]
        data = yf.download(tickers, period="2d", interval="5m", progress=False, multi_level_index=False)['Close']
        perf = {k: ((data[v].iloc[-1] - data[v].iloc[0]) / data[v].iloc[0]) * 100 for k, v in {"Tech": "XLK", "Def": "XLU", "Fin": "XLF"}.items()}
        rs_ratio = data["NQ=F"] / data["ES=F"]
        rs_change = ((rs_ratio.iloc[-1] - rs_ratio.iloc[0]) / rs_ratio.iloc[0]) * 100
        return perf, data["^VIX"].iloc[-1], data["^TNX"].iloc[-1], rs_change
    except: return {}, 0.0, 0.0, 0.0

# --- 2. TREND HEATMAP LOGIC ---
def get_tf_trend(symbol, interval):
    """Calculates SMA trend for specific timeframes"""
    try:
        data = yf.download(symbol, period="2d", interval=interval, progress=False, multi_level_index=False)['Close']
        sma9, sma21 = data.rolling(9).mean().iloc[-1], data.rolling(21).mean().iloc[-1]
        return "🟢" if sma9 > sma21 else "🔴"
    except: return "⚪"

# --- 3. PERSISTENT STATE ---
defaults = {'wins': 0, 'losses': 0, 'trade_log': [], 'total_pnl': 0.0}
for key, val in defaults.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 4. SIDEBAR: HEATMAP & MACRO ---
st.sidebar.title("🛡️ Risk Management")
active_google_key = st.secrets.get("GEMINI_API_KEY", "")
if not active_google_key:
    active_google_key = st.sidebar.text_input("Gemini API Key:", type="password")

account_size = st.sidebar.number_input("Account Balance ($)", value=50000)
risk_pct = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0) / 100

# Trend Heatmap
st.sidebar.divider()
st.sidebar.subheader("🔥 Trend Heatmap")
asset_map = {"NQ=F (Nasdaq)": "NQ=F", "ES=F (S&P 500)": "ES=F"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

c1, c2, c3 = st.sidebar.columns(3)
c1.metric("1m", get_tf_trend(target_symbol, "1m"))
c2.metric("5m", get_tf_trend(target_symbol, "5m"))
c3.metric("15m", get_tf_trend(target_symbol, "15m"))

sectors, vix, tnx, rs_lead = get_market_pulse()
st.sidebar.divider()
st.sidebar.metric("VIX (Fear)", f"{vix:.1f}"); st.sidebar.metric("10Y Yield", f"{tnx:.2f}%")

# --- 5. ANALYTICS FUNCTIONS ---
def calculate_vwap_metrics(df):
    if df.empty or len(df) < 21: return None
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
    df['Momentum'] = df['Close'].pct_change(5) * 100
    return df, ((df['Close'].iloc[-1] - df['VWAP'].iloc[-1]) / df['VWAP'].iloc[-1]) * 100

# --- 6. MAIN INTERFACE ---
st.title("🚀 NQ & ES Quantitative Trading Platform")
col1, col2 = st.columns([3, 1])
with col1: st.subheader(f"Current Target: {target_label}")
with col2: st.metric("Alpha RS Lead (NQ/ES)", f"{rs_lead:+.2f}%")

@st.fragment(run_every=60)
def main_monitor():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        metrics_data = calculate_vwap_metrics(df)
        if metrics_data:
            df, dev = metrics_data
            last_p, last_atr = df['Close'].iloc[-1], df['ATR'].iloc[-1]
            stop_dist = max(last_atr * 0.5, 0.25)
            risk_amt, tick_val = account_size * risk_pct, (20 if "NQ" in target_symbol else 50)
            suggested_size = max(1, int(risk_amt / (stop_dist * tick_val)))
            
            # Logic & Signals
            score = (1 if dev > 0.3 else -1 if dev < -0.3 else 0) + (1 if df['Momentum'].iloc[-1] > 0 else -1 if df['Momentum'].iloc[-1] < 0 else 0)
            signal = "🟢 STRONG LONG" if score >= 2 else "🔴 STRONG SHORT" if score <= -2 else "🟡 NEUTRAL"
            target_p = last_p + (stop_dist * 2.0) if score > 0 else last_p - (stop_dist * 2.0)
            stop_p = last_p - stop_dist if score > 0 else last_p + stop_dist

            # DASHBOARD
            m1, m2, m3 = st.columns(3)
            m1.metric("Price", f"${last_p:.2f}", f"{dev:+.2f}% VWAP")
            m2.metric("Signal", signal); m3.metric("Suggested Size", f"{suggested_size} Contracts")

            # CHART
            fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
            fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
            fig.add_hline(y=target_p, line_dash="dot", line_color="green", annotation_text="Target")
            fig.add_hline(y=stop_p, line_dash="dot", line_color="red", annotation_text="Stop")
            fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=40,b=0))
            st.plotly_chart(fig, use_container_width=True)

            # AI VERDICT
            st.divider()
            if st.button("🧠 Generate AI Prediction Verdict", use_container_width=True, type="primary"):
                if not active_google_key: st.error("Add Gemini Key")
                else:
                    client = genai.Client(api_key=active_google_key)
                    prompt = f"Analyze {target_label}: Price ${last_p}, Signal {signal}, Dev {dev:.2f}%, RS {rs_lead:+.2f}%. Verdict/Confidence."
                    resp = client.models.generate_content(model='gemini-2.0-flash-exp', contents=prompt)
                    st.info(f"### 🎯 AI Verdict\n{resp.text}")

            # EXECUTION
            st.divider()
            ex1, ex2 = st.columns(2)
            if ex1.button("✅ HIT TARGET", use_container_width=True, type="primary"):
                st.session_state.wins += 1; st.session_state.total_pnl += (risk_amt * 2.0); st.balloons()
            if ex2.button("❌ HIT STOP", use_container_width=True):
                st.session_state.losses += 1; st.session_state.total_pnl -= risk_amt
            st.write(f"**Session:** Wins: {st.session_state.wins} | P&L: `${st.session_state.total_pnl:+,.2f}`")

    except Exception as e: st.error(f"⚠️ Error: {str(e)}")

main_monitor()
