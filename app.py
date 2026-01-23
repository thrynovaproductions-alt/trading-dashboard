import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
from google import genai

# --- 1. CORE CONFIG & PERSISTENT MEMORY ---
st.set_page_config(layout="wide", page_title="NQ & ES Quant Pro", initial_sidebar_state="expanded")

if 'error_strikes' not in st.session_state:
    st.session_state.update({
        'error_strikes': 0, 
        'wins': 0, 'losses': 0, 'total_pnl': 0.0,
        'pattern_memory': [] 
    })

# --- 2. ANALYTICS & AI ENGINE ---
def get_full_ai_report(label, last_p, dev, atr, rsi, vix, tnx, tech, defen, fin, conf, api_key):
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""Elite Report for {label} (${last_p:.2f}). Conf: {conf:.0f}%. VIX: {vix:.1f}. RSI: {rsi:.1f}. 
        Sector Perf: Tech {tech:.2f}%, Def {defen:.2f}%, Fin {fin:.2f}%.
        Provide: 1. VERDICT, 2. KEY FACTORS, 3. RISK ASSESSMENT, 4. TRADE GUIDANCE."""
        resp = client.models.generate_content(model='gemini-2.0-flash-exp', contents=prompt)
        return resp.text
    except Exception as e: return f"AI Error: {e}"

def capture_pattern(df, reason):
    fig = go.Figure(data=[go.Candlestick(x=df.index[-30:], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(template="plotly_dark", showlegend=False, margin=dict(l=5, r=5, t=5, b=5), height=150)
    snapshot = {"time": datetime.now().strftime("%H:%M"), "fig": fig, "reason": reason, "price": df['Close'].iloc[-1]}
    st.session_state.pattern_memory = ([snapshot] + st.session_state.pattern_memory)[:3]

# --- 3. DATA & SIDEBAR ---
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

st.sidebar.title("🛡️ Risk Management")
key = st.sidebar.text_input("Gemini API Key:", type="password")
target_sym = st.sidebar.selectbox("Asset", ["NQ=F", "ES=F"])

data_pulse, sects, vix, tnx, rs_lead, is_clean = fetch_pulse(target_sym)

if not is_clean:
    st.session_state.error_strikes += 1
    if st.session_state.error_strikes >= 3:
        st.cache_data.clear(); st.session_state.error_strikes = 0; st.rerun()
    st.sidebar.error(f"⚠️ Sync Lag ({st.session_state.error_strikes}/3)")
else:
    st.session_state.error_strikes = 0; st.sidebar.success("✅ Data Integrity: 100%")

# --- 4. MAIN MONITOR ---
st.title("🚀 NQ & ES Quantitative Trading Platform")

@st.fragment(run_every=60)
def main_monitor():
    df = yf.download(target_sym, period="2d", interval="5m", progress=False)
    if df.empty: return

    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
    
    # --- HARDENED INDEXING FOR LINE 95 ---
    last_p = float(df['Close'].iloc[-1])
    last_vol = int(df['Volume'].iloc[-1])
    last_vwap = float(df['VWAP'].iloc[-1])
    dev = ((last_p - last_vwap) / last_vwap) * 100
    
    delta = df['Close'].diff()
    g = delta.where(delta > 0, 0).rolling(14).mean()
    l = -delta.where(delta < 0, 0).rolling(14).mean()
    rsi_val = float((100 - (100 / (1 + (g / l)))).iloc[-1])
    
    conf = (max(0, 100-(vix*2.5))*0.4) + (rsi_val*0.3) + (min(100, 50+(rs_lead*10))*0.3)

    m1, m2, m3 = st.columns(3)
    m1.metric("Price", f"${last_p:.2f}", f"{dev:+.2f}% VWAP")
    m2.metric("Confidence", f"{conf:.0f}%")
    m3.metric("RSI", f"{rsi_val:.1f}")
    
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='cyan', dash='dash'), name="VWAP"))
    fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig, use_container_width=True)

    if last_vol > 1000: capture_pattern(df, "Volume Climax")

    if st.session_state.pattern_memory:
        st.divider(); st.subheader("🧠 Visual Pattern Memory")
        cols = st.columns(3)
        for i, snap in enumerate(st.session_state.pattern_memory):
            with cols[i]:
                st.caption(f"🕒 {snap['time']} | {snap['reason']}")
                st.plotly_chart(snap['fig'], use_container_width=True, key=f"mem_{i}")

    if st.button("🧠 Generate Full Prediction Report", use_container_width=True, type="primary"):
        if not key: st.error("Add Gemini Key")
        else:
            with st.spinner("Analyzing..."):
                atr = float((df['High'].rolling(14).max() - df['Low'].rolling(14).min()).iloc[-1])
                report = get_full_ai_report(target_sym, last_p, dev, atr, rsi_val, vix, tnx, sects['Tech'], sects['Def'], sects['Fin'], conf, key)
                st.info("### 🎯 AI Quantitative Prediction Report")
                st.markdown(report)

main_monitor()
