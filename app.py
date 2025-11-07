import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
import warnings
import os
import requests
import json
import hmac
import hashlib
import time
from datetime import datetime
warnings.filterwarnings('ignore')

# === CONFIG ===
st.set_page_config(page_title="Blu Navi", layout="wide")
st.title("Blu Navi — Gold Trading Bot (LIVE)")

SYMBOL = 'GC=F'
INTERVAL = '1h'
EMA_SHORT = 9
EMA_LONG = 21
RISK_PCT = 0.01
SIM_BALANCE = 10000

# === SECRETS FROM RENDER ===
API_KEY = os.environ.get('BLOFIN_API_KEY')
API_SECRET = os.environ.get('BLOFIN_API_SECRET')
PASSPHRASE = os.environ.get('BLOFIN_PASSPHRASE')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# === SIDEBAR ===
st.sidebar.header("Settings")
st.markdown(
    """
    <style>
        .toggle-bubble {display: inline-block;width: 16px;height: 16px;border-radius: 50%;margin-right: 10px;vertical-align: middle;}
        .on-bubble {background-color: #00ff00;}.off-bubble {background-color: #ff0000;}
        .toggle-label {font-weight: bold;display: flex;align-items: center;margin-bottom: 15px;}
    </style>
    """,
    unsafe_allow_html=True
)

auto_draw = st.sidebar.checkbox("Auto-Draw Lines", value=True, key="auto_draw")
bubble = "on-bubble" if auto_draw else "off-bubble"
st.sidebar.markdown(f'<div class="toggle-label"><span class="toggle-bubble {bubble}"></span>Auto-Draw Lines</div>', unsafe_allow_html=True)

paper_mode = st.sidebar.checkbox("Paper Mode", value=False, key="paper_mode")
bubble = "on-bubble" if not paper_mode else "off-bubble"
st.sidebar.markdown(f'<div class="toggle-label"><span class="toggle-bubble {bubble}"></span>Live Mode</div>', unsafe_allow_html=True)

if st.sidebar.button("Refresh"):
    st.cache_data.clear()

# === TELEGRAM ALERT ===
def send_alert(message):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        try:
            requests.post(url, data=payload)
        except:
            pass

# === BLOFIN API (WITH PASSPHRASE) ===
def blofin_request(method, endpoint, params=None):
    if not API_KEY or not API_SECRET or not PASSPHRASE:
        return None
    url = f"https://www.blofin.com{endpoint}"
    timestamp = str(int(time.time() * 1000))
    if params is None:
        params = {}
    params['timestamp'] = timestamp
    query = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
    signature = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    headers = {
        'ACCESS-KEY': API_KEY,
        'ACCESS-SIGN': signature,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': PASSPHRASE,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, params=params)
        else:
            r = requests.post(url, headers=headers, data=params)
        return r.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None

def get_balance():
    if paper_mode:
        return SIM_BALANCE
    resp = blofin_request('GET', '/api/v1/account/balance')
    if resp and 'data' in resp:
        for asset in resp['data']:
            if asset['asset'] == 'USDT':
                return float(asset['available'])
    return 0.0

def place_order(side, price, size):
    if paper_mode:
        st.success(f"Paper {side} @ ${price}")
        send_alert(f"Paper {side} @ ${price}")
        return True
    params = {
        'instId': 'XAUUSDT',
        'tdMode': 'cash',
        'side': side.lower(),
        'ordType': 'limit',
        'px': str(round(price, 1)),
        'sz': str(round(size, 4))
    }
    resp = blofin_request('POST', '/api/v1/trade/order', params)
    if resp and resp.get('code') == '0':
        st.success(f"LIVE {side} EXECUTED @ ${price}")
        send_alert(f"LIVE {side} @ ${price}")
        return True
    else:
        st.error(f"Trade failed: {resp}")
        return False

# === DATA ===
@st.cache_data(ttl=60)
def fetch_data():
    data = yf.download(SYMBOL, period="5d", interval=INTERVAL, progress=False)
    if data.empty:
        st.error("No data from yfinance.")
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

# === SIGNAL ===
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
    hour = data.index[-1].hour
    if not (8 <= hour <= 17):
        return None
    trend_up = (ema_short_now > ema_long_now) and (ema_short_prev <= ema_long_prev)
    rsi_ok = 30 < rsi_now < 70
    macd_bull = macd_now > macd_signal_now and macd_now > 0
    score = (1 if trend_up else 0) + (0.5 if rsi_ok else 0) + (0.5 if macd_bull else 0)
    if score >= 2.0:
        row = data.iloc[-1]
        atr = (row['High'] - row['Low']) * 1.5
        sl = row['Close'] - atr
        tp = row['Close'] + (row['Close'] - sl) * 2.5
        return {
            'action': 'BUY',
            'price': row['Close'],
            'sl': sl,
            'tp': tp,
            'confidence': score / 3,
            'time': data.index[-1]
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
        fig.add_trace(go.Scatter(x=[signal['time']], y=[signal['price']],
                                 mode='markers', marker=dict(symbol='triangle-up', size=18, color='lime'),
                                 name='BUY'))
        fig.add_hline(y=signal['price'], line_color='lime', annotation_text=f"Entry: ${signal['price']:.1f}")
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
    balance = get_balance()
    risk = balance * RISK_PCT
    if signal:
        st.success(f"**{signal['action']} @ ${signal['price']:.1f}**")
        st.info(f"Confidence: {signal['confidence']:.0%} | Risk: ${risk:.0f}")
        size = risk / (signal['price'] - signal['sl'])
        if balance < risk:
            st.error(f"Not enough! Need ${risk:.0f}, you have ${balance:.0f}")
        else:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("EXECUTE", type="primary"):
                    place_order('BUY', signal['price'], size)
            with c2:
                if st.button("CLOSE", type="secondary"):
                    st.warning("Manual close (not implemented)")
    else:
        st.warning("No signal — waiting for trend...")

st.metric("Live Balance", f"${balance:,.0f}")
st.caption("Blu Navi — Phase 2 LIVE | Blofin + Wallet + Alerts")
