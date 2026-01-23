import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, time
import pytz
from google import genai

# --- 1. CORE CONFIGURATION & AUTO-HEALING STATE ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Pro", initial_sidebar_state="expanded")

if 'integrity_error_count' not in st.session_state:
    st.session_state.integrity_error_count = 0
if 'wins' not in st.session_state:
    st.session_state.update({'wins': 0, 'losses': 0, 'total_pnl': 0.0, 'ai_predictions': []})

# --- 2. DATA ENGINES & CACHING ---
@st.cache_data(ttl=60)
def get_market_data(target_symbol):
    """Fetches macro and technical data with integrity checks"""
    try:
        tickers = ["XLK", "XLU", "XLF", "^TNX", "^VIX", "NQ=F", "ES=F", target_symbol]
        data = yf.download(tickers, period="2d", interval="5m", progress=False, multi_level_index=False)['Close']
        
        # Macro Metrics
        vix = data["^VIX"].iloc[-1]
        tnx = data["^TNX"].iloc[-1]
        rs_ratio = data["NQ=F"] / data["ES=F"]
        rs_lead = ((rs_ratio.iloc[-1] - rs_ratio.iloc[0]) / rs_ratio.iloc[0]) * 100
        
        # Sector Perf
        sectors = {k: ((data[v].iloc[-1] - data[v].iloc[0]) / data[v].iloc[0]) * 100 
                   for k, v in {"Tech": "XLK", "Def": "XLU", "Fin": "XLF"}.items()}
        
        is_clean = not (np.isnan(vix) or np.isnan(tnx) or np.isnan(rs_lead))
        return data, sectors, vix, tnx, rs_lead, is_clean
    except:
        return None, {}, 0.0, 0.0, 0.0, False

def get_tf_trend(symbol, interval):
    """Calculates SMA trend alignment"""
    try:
        d = yf.download(symbol, period="2d", interval=interval, progress=False, multi_level_index=False)['Close']
        return "🟢" if d.rolling(9).mean().iloc[-1] > d.rolling(21).mean().iloc[-1] else "🔴"
    except: return "⚪"

# --- 3. SIDEBAR: RISK, HEATMAP & AUTO-HEALING ---
st.sidebar.title("🛡️ Risk Management")
active_google_key = st.secrets.get("GEMINI_API_KEY", "")
if not active_google_key:
    active_google_key = st.sidebar.text_input("Gemini API Key:", type="password")

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

# Integrity & Auto-Healing
data_all, sectors, vix, tnx, rs_lead, data_is_clean = get_market_data(target_symbol)
if not data_is_clean:
    st.session_state.integrity_error_count += 1
    if st.session_state.integrity_error_count >= 3:
        st.cache_data.clear()
        st.session_state.integrity_error_count = 0
        st.rerun()
    st.sidebar.error(f"⚠️ Data Sync Poor ({st.session_state.integrity_error_count}/3)")
else:
    st.sidebar.success("✅ Data Integrity: 100%")

account_size = st.sidebar.number_input("Account Balance ($)", value=50000)
risk_pct = st.sidebar.slider("Risk (%)", 0.5, 5.0, 1.0) / 100
target_rr = st.sidebar.number_input("Target R:R", value=2.0)

# --- 4. ANALYTICS & AI FUNCTIONS ---
def get_full_ai_report(label, last_p, dev, atr, vix_v, tnx_v, sect, conf, api_key):
    """Restored full structured report engine"""
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""Elite Quant Analyst Report for {label} (${last_p:.2f}). 
        Confidence: {conf:.0f}%. Metrics: VWAP Dev {dev:.2f}%, ATR {atr:.2f}, VIX {vix_v:.1f}.
        Provide: 1. VERDICT, 2. CONFIDENCE, 3. KEY QUANT FACTORS, 4. RISK ASSESSMENT, 5. TRADE GUIDANCE."""
        resp = client.models.generate_content(model='gemini-2.0-flash-exp', contents=prompt)
        return resp.text
    except Exception as e: return f"AI Error: {e}"

# --- 5. MAIN MONITOR ---
st.title("🚀 NQ & ES Quantitative Trading Platform")
st.metric("Alpha RS Lead (NQ/ES)", f"{rs_lead:+.2f}%")

@st.fragment(run_every=60)
def main_monitor():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        if df.empty: return
        
        # Quantitative Metrics
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
        df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
        last_p, last_atr = df['Close'].iloc[-1], df['ATR'].iloc[-1]
        dev = ((last_p - df['VWAP'].iloc[-1]) / df['VWAP'].iloc[-1]) * 100
        
        # RSI & Momentum
        delta = df['Close'].diff(); gain = delta.where(delta > 0, 0).rolling(14).mean(); loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        # Confidence Score
        conf_score = (max(0, 100-(vix*2.5)) * 0.4) + (rsi * 0.3) + (min(100, 50+(rs_lead*10)) * 0.3)

        # UI Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Price", f"${last_p:.2f}", f"{dev:+.2f}% VWAP")
        m2.metric("Trend Confidence", f"{conf_score:.0f}%")
        m3.metric("RSI (14)", f"{rsi:.1f}")

        # Execution Levels
        stop_dist = max(last_atr * 0.5, 0.25)
        risk_amt = account_size * risk_pct
        tick_val = 20 if "NQ" in target_symbol else 50
        suggested_size = max(1, int(risk_amt / (stop_dist * tick_val)))
        
        # Chart
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # RESTORED FULL REPORT BUTTON
        st.divider()
        if st.button("🧠 Generate Full Prediction Report", use_container_width=True, type="primary"):
            if not active_google_key: st.error("Add Gemini Key in Sidebar")
            else:
                with st.spinner("Analyzing Market Sentinel..."):
                    report = get_full_ai_report(target_label, last_p, dev, last_atr, vix, sectors, tnx, last_p, conf_score, active_google_key)
                    st.info("### 🎯 AI Quantitative Prediction Report")
                    st.markdown(report)

        # LOGGING
        st.divider()
        ex1, ex2 = st.columns(2)
        if ex1.button("✅ HIT TARGET", use_container_width=True):
            st.session_state.wins += 1; st.session_state.total_pnl += (risk_amt * target_rr); st.balloons()
        if ex2.button("❌ HIT STOP", use_container_width=True):
            st.session_state.losses += 1; st.session_state.total_pnl -= risk_amt

    except Exception as e: st.error(f"⚠️ Error: {e}")

main_monitor()
