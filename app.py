import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.trend import MACD
import plotly.graph_objects as go
from datetime import datetime
from scipy.stats import linregress
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
auto_draw = st.sidebar.toggle("Auto-Draw Lines", value=True)
paper_mode = st.sidebar.toggle("Paper Mode", value=True)
if st.sidebar.button("Refresh"):
    st.cache_data.clear()

# === FETCH DATA ===
@st.cache_data(ttl=60)
def fetch_data():
    data = yf.download(SYMBOL, period="5d", interval=INTERVAL, progress=False)
    data['EMA_short'] = EMAIndicator(data['Close'], window=EMA_SHORT).ema_indicator()
    data['EMA_long'] = EMAIndicator(data['Close'], window=EMA_LONG).ema_indicator()
    data['RSI'] = RSIIndicator(data['Close'], window=14).rsi()
    macd = MACD(data['Close'])
    data['MACD'] = macd.macd()
    data['MACD_signal'] = macd.macd_signal()
    return data

data = fetch_data()

# === GENERATE SIGNAL ===
def get_signal(data):
    latest = data.iloc[-2]
    current = data.iloc[-1]
    hour = current.name.hour
    if not (8 <= hour <= 17): return None

    trend_up = (current['EMA_short'] > current['EMA_long']) and (latest['EMA_short'] <= latest['EMA_long'])
    rsi_ok = 30 < current['RSI'] < 70
    macd_bull = current['MACD'] > current['MACD_signal'] and current['MACD'] > 0
    score = (1 if trend_up else 0) + (0.5 if rsi_ok else 0) + (0.5 if macd_bull else 0)
    
    if score >= 2.0:
        atr = (current['High'] - current['Low']) * 1.5
        sl = current['Close'] - atr
        tp = current['Close'] + (current['Close'] - sl) * 2.5
        return {
            'action': 'BUY', 'price': current['Close'], 'sl': sl, 'tp': tp,
            'confidence': score/3, 'time': current.name
        }
    return None

signal = get_signal(data)

# === CHART ===
def plot_chart(data, signal, auto_draw):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'],
                                 low=data['Low'], close=data['Close'], name='Gold'))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA_short'], line=dict(color='cyan'), name='EMA 9'))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA_long'], line=dict(color='magenta'), name='EMA 21'))

    if signal and auto_draw:
        color = 'lime' if signal['action'] == 'BUY' else 'red'
        fig.add_trace(go.Scatter(x=[signal['time']], y=[signal['price']],
                                 mode='markers', marker=dict(symbol='triangle-up', size=18, color=color),
                                 name=signal['action']))
        fig.add_hline(y=signal['price'], line_color=color, annotation_text=f"Entry: ${signal['price']:.1f}")
        fig.add_hline(y=signal['sl'], line_dash='dash', line_color='red', annotation_text=f"SL: ${signal['sl']:.1f}")
        fig.add_hline(y=signal['tp'], line_dash='dash', line_color='lime', annotation_text=f"TP: ${signal['tp']:.1f}")
        base = data['Low'].tail(20).min()
        fig.add_hline(y=base, line_dash='dot', line_color='blue', annotation_text="Base")

    fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark")
    return fig

# === LAYOUT ===
col1, col2 = st.columns([3,1])
with col1:
    st.plotly_chart(plot_chart(data, signal, auto_draw), use_container_width=True)

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
