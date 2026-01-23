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
def get_sector_performance():
    sectors = {"Tech (XLK)": "XLK", "Defensive (XLU)": "XLU", "Finance (XLF)": "XLF"}
    perf = {}
    for name, ticker in sectors.items():
        try:
            d = yf.download(ticker, period="1d", interval="5m", progress=False, multi_level_index=False)
            if not d.empty and len(d) > 1:
                perf[name] = ((d['Close'].iloc[-1] - d['Open'].iloc[0]) / d['Open'].iloc[0]) * 100
            else: perf[name] = 0.0
        except: perf[name] = 0.0
    return perf

@st.cache_data(ttl=60)
def get_vix_level():
    try:
        vix = yf.download("^VIX", period="1d", interval="1m", progress=False, multi_level_index=False)
        return float(vix['Close'].iloc[-1]) if not vix.empty else 0.0
    except: return 0.0

# --- 2. PERSISTENT STATE ---
defaults = {'wins': 0, 'losses': 0, 'trade_log': [], 'total_pnl': 0.0}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 3. SIDEBAR: RISK & AUTH ---
st.sidebar.title("🛡️ Risk Management")
active_google_key = st.secrets.get("GEMINI_API_KEY", "")
if not active_google_key:
    active_google_key = st.sidebar.text_input("Google AI Key:", type="password")

account_size = st.sidebar.number_input("Account Balance ($)", value=50000, step=1000)
risk_pct = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.0, step=0.1) / 100
target_rr = st.sidebar.number_input("Target R:R Ratio", value=2.0, step=0.5)

st.sidebar.divider()
st.sidebar.subheader("🌍 Market Pulse")
sectors = get_sector_performance()
for s, p in sectors.items():
    st.sidebar.metric(s, f"{p:.2f}%")

vix = get_vix_level()
st.sidebar.metric("VIX Fear Gauge", f"{vix:.1f}")

# Performance Reset
if st.sidebar.button("🔄 Reset Session", use_container_width=True):
    for key in defaults: st.session_state[key] = defaults[key]
    st.rerun()

# --- 4. ANALYTICS FUNCTIONS ---
def calculate_vwap_metrics(df):
    if df.empty or len(df) < 21: return None
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
    df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
    last_price = df['Close'].iloc[-1]
    last_vwap = df['VWAP'].iloc[-1]
    deviation_pct = ((last_price - last_vwap) / last_vwap) * 100
    df['Momentum'] = df['Close'].pct_change(5) * 100
    return df, deviation_pct

def generate_signal(df, deviation):
    if df is None: return "⚪ NO SIGNAL"
    last_mom = df['Momentum'].iloc[-1]
    if deviation > 0.3 and last_mom > 0: return "🟢 STRONG LONG"
    elif deviation < -0.3 and last_mom < 0: return "🔴 STRONG SHORT"
    else: return "🟡 NEUTRAL"

# --- 5. MAIN INTERFACE ---
st.title("🚀 NQ & ES Quantitative Trading Platform")
asset_map = {"NQ=F (Nasdaq)": "NQ=F", "ES=F (S&P 500)": "ES=F"}
target_label = st.selectbox("Select Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

@st.fragment(run_every=60)
def main_monitor():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        metrics_data = calculate_vwap_metrics(df)
        
        if metrics_data:
            df, dev = metrics_data
            last_p = df['Close'].iloc[-1]
            last_atr = df['ATR'].iloc[-1]
            
            # Risk Logic
            stop_dist = max(last_atr * 0.5, 0.25)
            risk_amt = account_size * risk_pct
            tick_value = 20 if "NQ" in target_symbol else 50
            suggested_contracts = max(1, int(risk_amt / (stop_dist * tick_value)))
            
            target_price = last_p + (stop_dist * target_rr) if dev > 0 else last_p - (stop_dist * target_rr)
            stop_price = last_p - stop_dist if dev > 0 else last_p + stop_dist
            signal = generate_signal(df, dev)

            # METRICS DISPLAY
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.metric("Current Price", f"${last_p:.2f}", f"{dev:+.2f}% VWAP")
            with m2: st.metric("Signal", signal)
            with m3: st.metric("Size", f"{suggested_contracts} Contracts")
            with m4:
                win_rate = (st.session_state.wins / (st.session_state.wins + st.session_state.losses) * 100) if (st.session_state.wins + st.session_state.losses) > 0 else 0
                st.metric("Win Rate", f"{win_rate:.1f}%")

            # CHART
            fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price")])
            fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
            fig.add_hline(y=target_price, line_dash="dot", line_color="green", annotation_text="Target")
            fig.add_hline(y=stop_price, line_dash="dot", line_color="red", annotation_text="Stop")
            fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig, use_container_width=True)

            # --- PREDICTION BUTTON RESTORED ---
            st.divider()
            if st.button("🤖 Generate AI Prediction Verdict", use_container_width=True):
                if not active_google_key: st.warning("Add Google Key in Sidebar")
                else:
                    client = genai.Client(api_key=active_google_key)
                    prompt = f"""
                    AI Verdict for {target_label}:
                    - Technical: {signal} | VWAP Dev: {dev:.2f}% | ATR: {last_atr:.2f}
                    - Context: VIX {vix:.1f} | Tech {sectors.get('Tech (XLK)', 0):.2f}%
                    
                    1. Confidence %
                    2. 5-Tier Verdict (Strong/Weak Short, Wait, Strong/Weak Long)
                    3. Technical Alignment breakdown.
                    """
                    response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                    st.info("### 🤖 AI Prediction Analysis")
                    st.markdown(response.text)

            # LOGGING
            st.subheader("📊 Trade Management")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ HIT TARGET", use_container_width=True):
                    st.session_state.wins += 1; st.session_state.total_pnl += (risk_amt * target_rr); st.balloons()
            with c2:
                if st.button("❌ HIT STOP", use_container_width=True):
                    st.session_state.losses += 1; st.session_state.total_pnl -= risk_amt

    except Exception as e: st.error(f"System Error: {e}")

main_monitor()
