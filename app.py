import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, time
import pytz

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
            else:
                perf[name] = 0.0
        except Exception:
            perf[name] = 0.0
    return perf

@st.cache_data(ttl=60)
def get_vix_level():
    """Fetch current VIX for risk context"""
    try:
        vix = yf.download("^VIX", period="1d", interval="1m", progress=False, multi_level_index=False)
        return float(vix['Close'].iloc[-1]) if not vix.empty else 0.0
    except:
        return 0.0

# --- 2. PERSISTENT STATE ---
defaults = {'wins': 0, 'losses': 0, 'trade_log': [], 'total_pnl': 0.0}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 3. SIDEBAR: RISK & UTILITIES ---
st.sidebar.title("🛡️ Risk Management")
account_size = st.sidebar.number_input("Account Balance ($)", value=50000, step=1000)
risk_pct = st.sidebar.slider("Risk per Trade (%)", 0.5, 5.0, 1.0, step=0.1) / 100
target_rr = st.sidebar.number_input("Target R:R Ratio", value=2.0, step=0.5)

st.sidebar.divider()
st.sidebar.subheader("🌍 Market Pulse")
sectors = get_sector_performance()
for s, p in sectors.items():
    delta_color = "normal" if p >= 0 else "inverse"
    st.sidebar.metric(s, f"{p:.2f}%", delta=f"{abs(p):.2f}%", delta_color=delta_color)

vix = get_vix_level()
vix_status = "🟢 Low" if vix < 15 else "🟡 Elevated" if vix < 25 else "🔴 High"
st.sidebar.metric("VIX Fear Gauge", f"{vix:.1f}", vix_status)

# Market Hours Check
est = pytz.timezone('US/Eastern')
now_est = datetime.now(est).time()
is_rth = time(9, 30) <= now_est <= time(16, 0)
session_badge = "🟢 RTH" if is_rth else "🔵 ETH"
st.sidebar.info(f"Session: {session_badge}")

# Performance Reset
if st.sidebar.button("🔄 Reset Session", use_container_width=True):
    for key in defaults:
        st.session_state[key] = defaults[key]
    st.rerun()

# --- 4. ANALYTICS FUNCTIONS ---
def calculate_vwap_metrics(df):
    """Calculate VWAP and deviation metrics"""
    if df.empty or len(df) < 21:
        return None
    
    # VWAP calculation
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()
    
    # Volatility and deviation
    df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
    last_price = df['Close'].iloc[-1]
    last_vwap = df['VWAP'].iloc[-1]
    deviation_pct = ((last_price - last_vwap) / last_vwap) * 100
    
    # Momentum (5-period rate of change)
    df['Momentum'] = df['Close'].pct_change(5) * 100
    
    return df, deviation_pct

def generate_signal(df, deviation):
    """Generate trading signal based on VWAP deviation and momentum"""
    if df is None or deviation is None:
        return "⚪ NO SIGNAL", "#808080"
    
    last_mom = df['Momentum'].iloc[-1]
    
    # Signal logic
    if deviation > 0.3 and last_mom > 0:
        return "🟢 LONG BIAS", "#00ff00"
    elif deviation < -0.3 and last_mom < 0:
        return "🔴 SHORT BIAS", "#ff0000"
    else:
        return "🟡 NEUTRAL", "#ffff00"

# --- 5. MAIN INTERFACE ---
st.title("🚀 NQ & ES Quantitative Trading Platform")

col1, col2 = st.columns([2, 1])
with col1:
    asset_map = {"NQ=F (Nasdaq Futures)": "NQ=F", "ES=F (S&P 500 Futures)": "ES=F"}
    target_label = st.selectbox("Select Market Asset", list(asset_map.keys()))
    target_symbol = asset_map[target_label]
with col2:
    auto_refresh = st.checkbox("Auto-refresh (60s)", value=True)

@st.fragment(run_every=60 if auto_refresh else None)
def main_monitor():
    try:
        # Fetch market data
        df = yf.download(target_symbol, period="2d", interval="5m", progress=False, multi_level_index=False)
        
        if df.empty or len(df) < 21:
            st.warning("⏳ Waiting for sufficient market data...")
            return
        
        # Calculate metrics
        metrics = calculate_vwap_metrics(df)
        if metrics is None:
            st.warning("⚠️ Unable to calculate metrics")
            return
            
        df, dev = metrics
        last_p = df['Close'].iloc[-1]
        last_atr = df['ATR'].iloc[-1]
        
        # Position Sizing
        stop_dist = last_atr * 0.5  # Half ATR stop
        risk_amt = account_size * risk_pct
        tick_value = 20 if "NQ" in target_symbol else 50
        suggested_contracts = max(1, int(risk_amt / (stop_dist * tick_value)))
        
        # Target calculation
        target_dist = stop_dist * target_rr
        target_price = last_p + target_dist if dev > 0 else last_p - target_dist
        stop_price = last_p - stop_dist if dev > 0 else last_p + stop_dist
        
        # Generate signal
        signal, signal_color = generate_signal(df, dev)
        
        # --- METRICS DISPLAY ---
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Current Price", f"${last_p:.2f}", f"{dev:+.2f}% VWAP")
        with m2:
            st.metric("Signal", signal, delta_color="off")
        with m3:
            st.metric("Position Size", f"{suggested_contracts} Contracts", f"${risk_amt:.0f} risk")
        with m4:
            win_rate = (st.session_state.wins / (st.session_state.wins + st.session_state.losses) * 100) if (st.session_state.wins + st.session_state.losses) > 0 else 0
            st.metric("Win Rate", f"{win_rate:.1f}%", f"{st.session_state.wins}W / {st.session_state.losses}L")
        
        # --- TRADE LEVELS ---
        st.divider()
        t1, t2, t3 = st.columns(3)
        with t1:
            st.markdown(f"**🎯 Target:** `${target_price:.2f}`")
        with t2:
            st.markdown(f"**📍 Entry:** `${last_p:.2f}`")
        with t3:
            st.markdown(f"**🛑 Stop:** `${stop_price:.2f}`")
        
        # --- ADVANCED CHART ---
        fig = go.Figure()
        
        # Candlesticks
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="Price"
        ))
        
        # VWAP line
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['VWAP'],
            line=dict(color='cyan', width=2, dash='dash'),
            name="VWAP"
        ))
        
        # Trade levels
        fig.add_hline(y=target_price, line_dash="dot", line_color="green", annotation_text="Target")
        fig.add_hline(y=stop_price, line_dash="dot", line_color="red", annotation_text="Stop")
        
        fig.update_layout(
            height=550,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            margin=dict(l=0, r=0, t=30, b=0),
            title=f"{target_label} - 5min Chart"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Volume analysis
        recent_vol = df['Volume'].tail(20).mean()
        current_vol = df['Volume'].iloc[-1]
        vol_ratio = current_vol / recent_vol if recent_vol > 0 else 1
        
        v1, v2 = st.columns(2)
        with v1:
            st.metric("Current Volume", f"{int(current_vol):,}")
        with v2:
            vol_status = "🔥 Above Avg" if vol_ratio > 1.2 else "📊 Normal"
            st.metric("Volume Status", vol_status, f"{vol_ratio:.2f}x avg")
        
    except Exception as e:
        st.error(f"⚠️ System Error: {str(e)}")
        st.info("Try refreshing or selecting a different asset.")

main_monitor()

# --- 6. TRADE LOGGING ---
st.divider()
st.subheader("📊 Trade Management")

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button("✅ HIT TARGET", use_container_width=True, type="primary"):
        st.session_state.wins += 1
        st.session_state.total_pnl += (account_size * risk_pct * target_rr)
        st.balloons()
        st.success(f"Win logged! P&L: +${account_size * risk_pct * target_rr:.2f}")

with c2:
    if st.button("❌ HIT STOP", use_container_width=True, type="secondary"):
        st.session_state.losses += 1
        st.session_state.total_pnl -= (account_size * risk_pct)
        st.warning(f"Loss logged. P&L: -${account_size * risk_pct:.2f}")

with c3:
    total_trades = st.session_state.wins + st.session_state.losses
    st.markdown(f"""
    **Session Summary**  
    Total Trades: `{total_trades}` | Net P&L: `${st.session_state.total_pnl:+.2f}`
    """)

# --- 7. TRADE LOG TABLE ---
if st.session_state.trade_log:
    with st.expander("📋 View Trade History"):
        st.dataframe(pd.DataFrame(st.session_state.trade_log), use_container_width=True)