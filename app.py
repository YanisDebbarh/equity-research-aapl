import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from models.dcf_model import DCFModel, DCFAssumptions

st.set_page_config(
    page_title="Equity Research Dashboard",
    page_icon="📊",
    layout="wide"
)

# ── SIDEBAR ──────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Model Controls")
    ticker = st.text_input("Ticker", value="AAPL").upper()
    st.subheader("📈 Growth Assumptions")
    g1 = st.slider("Growth Y+1", 0.0, 0.30, 0.07, 0.01, format="%.0f%%")
    g2 = st.slider("Growth Y+2", 0.0, 0.30, 0.08, 0.01, format="%.0f%%")
    g3 = st.slider("Growth Y+3", 0.0, 0.20, 0.07, 0.01, format="%.0f%%")
    g4 = st.slider("Growth Y+4", 0.0, 0.20, 0.06, 0.01, format="%.0f%%")
    g5 = st.slider("Growth Y+5", 0.0, 0.20, 0.05, 0.01, format="%.0f%%")
    st.subheader("💰 FCF & Discount")
    fcf_m = st.slider("FCF Margin", 0.10, 0.40, 0.26, 0.01, format="%.0f%%")
    beta  = st.slider("Beta", 0.5, 2.5, 1.25, 0.05)
    tgr   = st.slider("Terminal Growth", 0.01, 0.05, 0.03, 0.005)
    run   = st.button("🚀 Run Valuation", type="primary", use_container_width=True)
# ── DATA FETCH ───────────────────────────────────
@st.cache_data(ttl=3600)
def fetch(ticker):
    s    = yf.Ticker(ticker)
    info = s.info
    hist = s.history(period="2y")
    return info, hist

info, hist = fetch(ticker)
current_price = info.get('currentPrice', 0)
shares        = info.get('sharesOutstanding', 0) / 1e6
net_cash      = (info.get('totalCash',0) - info.get('totalDebt',0)) / 1e6
base_rev      = info.get('totalRevenue', 0) / 1e6

# ── DCF ──────────────────────────────────────────
a = DCFAssumptions(
    revenue_growth_rates=[g1,g2,g3,g4,g5],
    fcf_margins=[fcf_m]*5,
    terminal_growth_rate=tgr,
    beta=beta,
    shares_outstanding_m=shares,
    net_cash_m=net_cash,
)
model   = DCFModel(base_rev, a)
results = model.run()
dcf_price = results['intrinsic_price']
upside    = (dcf_price / current_price - 1) * 100
rating    = "BUY" if upside > 10 else "SELL" if upside < -10 else "HOLD"

# ── HEADER ───────────────────────────────────────
st.title(f"📊 {info.get('longName','...')} ({ticker})")
st.caption(f"{info.get('sector','')} · {info.get('industry','')}")
st.divider()

# ── SECTION 0 : EXECUTIVE SUMMARY ────────────────
st.subheader("0️⃣ Executive Summary")
st.info(f"""
As of **{pd.Timestamp.now().strftime('%B %Y')}**, **{info.get('longName','...')} ({ticker})**
appears **{'undervalued' if upside > 0 else 'overvalued'}** by ~**{abs(upside):.0f}%**,
with a DCF target price of **${dcf_price:.0f}** vs current price of **${current_price:.0f}**.
We initiate coverage with a **{rating}** rating.
""")

c1,c2,c3,c4 = st.columns(4)
c1.metric("Current Price", f"${current_price:.2f}")
c2.metric("DCF Target",    f"${dcf_price:.2f}", f"{upside:+.1f}%")
c3.metric("WACC",          f"{results['wacc']:.2%}")
c4.metric("Rating",        rating)
st.divider()

# ── PRICE CHART ──────────────────────────────────
st.subheader("📈 Price History")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=hist.index, y=hist['Close'],
    fill='tozeroy', line=dict(color='#3498db', width=2)
))
fig.add_hline(y=dcf_price, line_dash='dash',
              line_color='green',
              annotation_text=f"DCF Target ${dcf_price:.0f}")
fig.add_hline(y=current_price, line_dash='dot',
              line_color='red',
              annotation_text=f"Current ${current_price:.0f}")
fig.update_layout(height=350, template='plotly_white')
st.plotly_chart(fig, use_container_width=True)

# ── FCF PROJECTION ───────────────────────────────
st.subheader("💡 DCF — FCF Projection")
proj = model._projection
st.dataframe(proj.round(2), hide_index=True, use_container_width=True)
st.caption("⚠️ For educational purposes only. Not investment advice.")
