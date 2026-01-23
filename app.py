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
if 'wins' not in st.session_state:
    st.session_state.update({'wins': 0, 'losses': 0, 'total_pnl': 0.0})

# --- 2. DATA ENGINES ---
@st.cache_data(ttl=60)
def get_comprehensive_data(target):
    """Fetches macro and technical data with nan-protection"""
    try:
        tickers = ["XLK", "XLU", "XLF", "^TNX", "^VIX", "NQ=F", "ES=F", target]
        data = yf.download(tickers, period="2d", interval="5m", progress=False, multi_level_index=False)['Close']
        
        vix = data["^VIX"].iloc[-1]
        tnx = data["^TNX"].iloc[-1]
        rs_ratio = data["NQ=F"] / data["ES=F"]
        rs_lead = ((rs_ratio.iloc[-1] - rs_ratio.iloc[0]) / rs_ratio.iloc[0]) * 100
        
        sectors = {k: ((data[v].iloc[-1] - data[v].iloc[0]) / data[v].iloc[0]) * 100 
                   for k, v in {"Tech": "XLK", "Def": "XLU", "Fin": "XLF"}.items()}
        
        is_clean = not (np.isnan(vix) or np.isnan(tnx) or np.isnan(rs_lead))
        return data, sectors, vix, tnx, rs_lead, is_clean
    except: return None, {}, 0.0, 0.0, 0.0, False

def get_tf_trend(symbol, interval):
    """Calculates SMA trend alignment"""
    try:
        d = yf.download(symbol, period="2d", interval=interval, progress=False, multi_level_index=False)['Close']
        return "🟢" if d.rolling(9).mean().iloc[-1] > d.rolling(21).mean().iloc[-1] else "🔴"
    except: return "⚪"

# --- 3. AI ANALYST ENGINE ---
def get_full_ai_report(label, last_p, dev, atr, vix_v, tnx_v, sect, conf, api_key):
    """Generates structured deep-dive report (Fixed Arguments)"""
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        Elite Quant Analyst Report for {label} (${last_p:.2f}). 
        Confidence: {conf:.0f}%. Metrics: VWAP Dev {dev:.2f}%, ATR {atr:.2f}, VIX {vix_v:.1f}.
        Provide: 1. VERDICT, 2. CONFIDENCE, 3. KEY QUANT FACTORS, 4. RISK ASSESSMENT, 5. TRADE GUIDANCE.
        """
        resp = client.models.generate_content(model='gemini-2.0-flash-exp', contents=prompt)
        return resp.text
    except Exception as e: return f"AI Error: {e}"

# --- 4. SIDEBAR & RISK ---
st.sidebar.title("🛡️ Risk Management")
active_google_key = st.secrets.get("GEMINI_API_KEY", "") or st.sidebar.text_input("Gemini API Key:", type="password")

asset_map = {"NQ=F (Nasdaq)": "NQ=F", "ES=F (S&P 500)": "ES=F"}
target_label = st.sidebar.selectbox("Market Asset", list(asset_map.keys()))
target_symbol = asset_map[target_label]

# Data Integrity Shield
data_all, sectors, vix, tnx, rs_lead, data_is_clean = get_comprehensive_data(target_symbol)
if not data_is_clean:
    st.session_state.integrity_error_count += 1
    if st.session_state.integrity_error_count >= 3:
        st.cache_data.clear()
        st.session_state.integrity_error_count = 0
        st.rerun()
    st.sidebar.error(f"⚠️ Sync Lag ({st.session_state.integrity_error_count}/3)")
else:
    st.sidebar.success("✅ Data Integrity: 100%")

st.sidebar.divider()
st.sidebar.subheader("🔥 Trend Heatmap")
c1, c2, c3 = st.sidebar.columns(3)
c1.metric("1m", get_tf_trend(target_symbol, "1m"))
c2.metric("5m", get_tf_trend(target_symbol, "5m"))
c3.metric("15m", get_tf_trend(target_symbol, "15m"))

# --- 5. MAIN INTERFACE ---
st.title("🚀 NQ & ES Quantitative Trading Platform")

@st.fragment(run_every=60)
def main_monitor():
    try:
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        tp = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
        df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
        
        last_p, last_atr = df['Close'].iloc[-1], df['ATR'].iloc[-1]
        last_vol = df['Volume'].iloc[-1]
        dev = ((last_p - df['VWAP'].iloc[-1]) / df['VWAP'].iloc[-1]) * 100
        
        # RSI Calculation
        delta = df['Close'].diff()
        gain, loss = delta.where(delta > 0, 0).rolling(14).mean(), -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
        
        # Weighted Confidence
        conf_score = (max(0, 100-(vix*2.5)) * 0.4) + (rsi * 0.3) + (min(100, 50+(rs_lead*10)) * 0.3)

        # REVERSAL VOLUME FILTER
        if last_vol > 400 and last_p > df['Open'].iloc[-1]:
            st.toast("🟢 HIGH CONVICTION BUYING!", icon="🚀")
            st.success(f"Reversal Volume confirmed: {last_vol} contracts on Green Bar.")

        # Metric Row
        m1, m2, m3 = st.columns(3)
        m1.metric("Price", f"${last_p:.2f}", f"{dev:+.2f}% VWAP")
        m2.metric("Confidence", f"{conf_score:.0f}%")
        m3.metric("RSI (14)", f"{rsi:.1f}")

        # Charting
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
        fig.update_layout(height=450, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # AI PREDICTION REPORT
        st.divider()
        if st.button("🧠 Generate Full Prediction Report", use_container_width=True, type="primary"):
            if not active_google_key: st.error("Add Gemini Key")
            else:
                with st.spinner("Generating Analyst Deep-Dive..."):
                    report = get_full_ai_report(target_label, last_p, dev, last_atr, vix, sectors, tnx, conf_score, active_google_key)
                    st.info("### 🎯 AI Quantitative Prediction Report")
                    st.markdown(report)

    except Exception as e: st.error(f"Monitor Error: {e}")

main_monitor()
