import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
import warnings
warnings.filterwarnings('ignore')

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

# Custom CSS for colored bubble
st.markdown("""
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
""", unsafe_allow_html=True)

# === Auto-Draw Toggle ===
auto_draw = st.sidebar.checkbox("Auto-Draw Lines", value=True, key="auto_draw")
bubble_class = "on-bubble" if auto_draw else "off-bubble"
st.sidebar.markdown(
    f'<div class="toggle-label"><span class="toggle-bubble {bubble_class}"></span>Auto-Draw Lines</div>',
    unsafe_allow_html=True
)

# === Paper Mode Toggle ===
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

    # Extract single values using .iloc
    ema_short_now = data['EMA_short'].iloc[-1]
    ema_long_now = data['EMA_long'].iloc[-1]
    ema_short_prev = data['EMA_short'].iloc[-2]
    ema_long_prev = data['EMA_long'].iloc[-2]
    
    rsi_now = data['RSI'].iloc[-1]
    macd_now = data['MACD'].iloc[-1]
    macd_signal_now = data['MACD_signal'].iloc[-1]
    
    # Get current hour
    current_time = data.index[-1]
    hour = current_time.hour
    if not (8 <= hour <= 17):
        return None

    # Signal Logic
    trend_up = (ema_short_now > ema_long_now) and (ema_short_prev <= ema_long_prev)
    rsi_ok = 30 < rsi_now < 70
    macd_bull = macd_now > macd_signal_now and macd_now > 0

    score = (1 if trend_up else 0) + (0.5 if rsi_ok else 0) + (0.5 if macd_bull else 0)

    if score >= 2.
