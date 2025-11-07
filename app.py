import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
import warnings
warnings.filterwarnings('ignore')  # ← FIXED: lowercase 'w'

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

# Custom CSS
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

# Auto-Draw Toggle
auto_draw = st.sidebar.checkbox("Auto-Draw Lines", value=True, key="auto_draw")
bubble_class = "on-bubble" if auto_draw else "off-bubble"
st.sidebar.markdown(
    f'<div class="toggle-label"><span class="toggle-bubble {bubble_class}"></span>Auto-Draw Lines</div>',
    unsafe_allow_html=True
)

# Paper Mode Toggle
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
        fig.add_hline(y=signal['
