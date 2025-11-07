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

# === Paper Mode Toggle ===
paper_mode = st.sidebar.checkbox("Paper Mode", value=True, key="paper_mode")
bubble_class =
