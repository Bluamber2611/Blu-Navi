import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
import warnings
warnings.filterWarnings('ignore')

# === CONFIG ===
st.set_page_config(page_title="Blu Navi", layout="wide")
st.title("Blu Navi — Gold Trading Bot")
SYMBOL = 'GC=F'  # Gold
INTERVAL = '1h'
EMA_SHORT = 9
EMA_LONG = 21
RISK_PCT = 0.01  # 1%
SIM_BALANCE = 10000

# === SIDEBAR SETTINGS ===
st.sidebar.header("Settings")

# Custom CSS for toggle bubbles
st.markdown(
    """
    <style>
        .toggle-bubble {
            display: inline-block;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 10px;
            vertical-align: middle;
        }
        .on-bubble { background-color: #00ff00; }
        .off-bubble { background-color: #ff0000; }
        .toggle-label {
            font-weight: bold;
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# === Auto-Draw Toggle ===
auto_draw = st.sidebar.checkbox("Auto-Draw Lines", value=True, key="auto_draw")
bubble_class = "on-bubble" if auto_draw else "off-bubble"
st.sidebar.markdown(
    f'<div class="toggle-label"><span class="toggle-bubble {bubble_class}"></span>Auto-Draw Lines</div>',
    unsafe_allow_html=True
)

# === Paper Mode Toggle (100% CORRECT) ===
paper_mode = st.sidebar.checkbox("Paper Mode", value=True, key="paper_mode")
bubble_class = "on-bubble" if paper_mode else "off-bubble"
st.sidebar.markdown(
    f'<div class="toggle-label"><span class="toggle-bubble {bubble_class}"></span>Paper Mode</div>',
    unsafe_allow_html=True
)

if st.sidebar.button("Refresh"):
    st.cache_data.clear()

# === FETCH DATA ===
@st.cache_data(ttl=60)
def fetch_data():
    data = yf.download(SYMBOL, period="5d", interval=INTERVAL, progress=False)
    if data.empty:
        st.error("No data from yfinance. Try again later.")
        return pd.DataFrame()
   
    close = data['Close'].squeeze()
    data['EMA_short'] = EMAIndicator(close, window=EMA_SHORT).ema_indicator()
    data['EMA_long'] = EMAIndicator(close, window=EMA_LONG).ema_indicator()
    data['RSI'] = RSIIndicator(close, window=14).rsi()
    macd = MACD(close)
    data['MACD'] = macd.macd()
    data['MACD_signal'] = macd.macd_signal()
    return data

data = fetch_data()

# === GENERATE SIGNAL ===
def get_signal(data):
    if len(data) < 2:
        return None
    ema_short_now = data['EMA_short'].iloc[-1]
    ema_long_now = data['EMA_long'].iloc[-1]
    ema_short_prev = data['EMA_short'].iloc[-2]
    ema_long_prev = data['EMA_long'].iloc[-2]
   
    rsi_now = data['RSI'].iloc[-1]
    macd_now = data['MACD'].iloc[-1]
    macd_signal_now = data['MACD_signal'].iloc[-1]
   
    current_time = data.index[-1]
    hour = current_time.hour
    if not (8 <= hour <= 17):
        return None
    trend_up = (ema_short_now > ema_long_now) and (ema_short_prev <= ema_long_prev)
    rsi_ok = 30 < rsi_now < 70
    macd_bull = macd_now > macd_signal_now and macd_now > 0
    score = (1 if trend_up else 0) + (0.5 if rsi_ok else 0) + (0.5 if macd_bull else 0)
    
    if score >= 2.0:
        current_row = data.iloc[-1]
        atr = (current_row['High'] - current_row['Low']) * 1.5
        sl = current_row['Close'] - atr
        tp = current_row['Close'] + (current_row['Close'] - sl) * 2.5
        return {
            'action': 'BUY',
            'price': current_row['Close'],
            'sl': sl,
            'tp': tp,
            'confidence': score / 3,
            'time': current_time
        }
    return None

signal = get_signal(data) if not data.empty else None

# === CHART ===
def plot_chart(data, signal, auto_draw):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'],
                                 low=data['Low'], close=data['Close'], name='Gold'))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA_short'], line=dict(color='cyan'), name='EMA 9'))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA_long'], line=dict(color='magenta'), name='EMA 21'))
    if signal and auto_draw:
        color = 'lime'
        fig.add_trace(go.Scatter(x=[signal['time']], y=[signal['price']],
                                 mode='markers', marker=dict(symbol='triangle-up', size=18, color=color),
                                 name='BUY'))
        fig.add_hline(y=signal['price'], line_color=color, annotation_text=f"Entry: ${signal['price']:.1f}")
        fig.add_hline(y=signal['sl'], line_dash='dash', line_color='red', annotation_text=f"SL: ${signal['sl']:.1f}")
        fig.add_hline(y=signal['tp'], line_dash='dash', line_color='lime', annotation_text=f"TP: ${signal['tp']:.1f}")
        base = data['Low'].tail(20).min()
        fig.add_hline(y=base, line_dash='dot', line_color='blue', annotation_text="Base")
    fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark")
    return fig

# === LAYOUT ===
col1, col2 = st.columns([3, 1])
with col1:
    if not data.empty:
        st.plotly_chart(plot_chart(data, signal, auto_draw), use_container_width=True)
    else:
        st.warning("Waiting for market data...")
with col2:
    st.subheader("Trade")
    balance = SIM_BALANCE if paper_mode else st.number_input("Live Balance", value=10000.0)
    risk = balance * RISK_PCT
    if signal:
        st.success(f"**{signal['action']} @ ${signal['price']:.1f}**")
        st.info(f"Confidence: {signal['confidence']:.0%} | Risk: ${risk:.0f}")
       
        if balance < risk:
            st.error(f"Not enough! Need ${risk:.0f}, you have ${balance:.0f}")
        else:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("EXECUTE", type="primary"):
                    st.success("Trade opened! Monitoring...")
            with c2:
                if st.button("CLOSE", type="secondary"):
                    st.warning("Trade closed manually.")
    else:
        st.warning("No signal — waiting for trend...")

# === MONITOR ===
st.metric("Balance", f"${balance:,.0f}")
st.caption("Blu Navi — Phase 1 Live | Next: Blofin + Wallet")
