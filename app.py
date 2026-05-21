import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from models.dcf_advanced import DCFAdvanced

st.set_page_config(
    page_title="Equity Research Dashboard",
    page_icon="📊",
    layout="wide"
)

# ── TICKER D'ABORD ───────────────────────────────────
with st.sidebar:
    st.title("⚙️ Model Controls")
    ticker = st.text_input("Ticker", value="AAPL").upper()

# ── AUTO-CALIBRATION ─────────────────────────────────
@st.cache_data(ttl=3600)
def get_calibration(ticker):
    dcf = DCFAdvanced(ticker)
    hist = dcf.get_historical_data()
    sect = dcf.get_sector_defaults()
    info = dcf.info
    return {
        'growth'     : round(max(sect['growth'],
                          hist.get('revenue_growth_hist', sect['growth'])), 2),
        'ebit_margin': round(max(sect['margin'],
                          hist.get('ebit_margin_avg', sect['margin'])), 2),
        'capex_pct'  : round(hist.get('capex_pct_avg', 0.05), 2),
        'tax_rate'   : round(hist.get('tax_rate', 0.21), 2),
        'tgr'        : sect['tgr'],
        'beta'       : round(info.get('beta', 1.2) or 1.2, 2),
        'sector'     : info.get('sector', 'N/A'),
        'revenue_ltm': hist.get('revenue_ltm', 0),
    }

cal = get_calibration(ticker)

# ── RESTE SIDEBAR ────────────────────────────────────
with st.sidebar:
    st.caption(f"📊 Sector: **{cal['sector']}** — auto-calibrated")
    
    st.subheader("📈 Revenue Growth")
    g = float(cal['growth'])
    g1 = st.slider("Y+1", 0.0, 0.40, g,        0.01, format="%.0f%%")
    g2 = st.slider("Y+2", 0.0, 0.40, g,        0.01, format="%.0f%%")
    g3 = st.slider("Y+3", 0.0, 0.30, round(g*0.90,2), 0.01, format="%.0f%%")
    g4 = st.slider("Y+4", 0.0, 0.25, round(g*0.80,2), 0.01, format="%.0f%%")
    g5 = st.slider("Y+5", 0.0, 0.20, round(g*0.70,2), 0.01, format="%.0f%%")

    st.subheader("💰 Profitability")
    ebit_m = st.slider("EBIT Margin", 0.01, 0.60,
                        float(cal['ebit_margin']), 0.01, format="%.0f%%")
    capex  = st.slider("CapEx % Rev", 0.01, 0.20,
                        float(cal['capex_pct']),   0.01, format="%.0f%%")

    st.subheader("📉 Discount Rate")
    tgr  = st.slider("Terminal Growth", 0.01, 0.05,
                      float(cal['tgr']), 0.005, format="%.1f%%")
    rfr  = st.slider("Risk-Free Rate",  0.02, 0.07, 0.045, 0.005, format="%.1f%%")
    erp  = st.slider("Equity Risk Prem",0.03, 0.08, 0.055, 0.005, format="%.1f%%")

    st.subheader("📋 Info")
    st.info(f"""
    **Tax Rate** : {cal['tax_rate']:.0%} (real)  
    **Beta**     : {cal['beta']}  
    **LTM Rev**  : ${cal['revenue_ltm']/1e3:.1f}B
    """)

# ── RUN DCF ──────────────────────────────────────────
@st.cache_data(ttl=3600)
def run_dcf(ticker, g1, g2, g3, g4, g5, ebit_m, capex, tgr, rfr, erp):
    dcf = DCFAdvanced(ticker)
    price, results = dcf.run(
        growth_rates=[g1, g2, g3, g4, g5],
        ebit_margin =ebit_m,
        capex_pct   =capex,
        tgr         =tgr,
        rfr         =rfr,
        erp         =erp,
    )
    proj = dcf._projection
    info = dcf.info
    hist = yf.Ticker(ticker).history(period="2y")
    return price, results, proj, info, hist

price, results, proj, info, hist = run_dcf(
    ticker, g1, g2, g3, g4, g5, ebit_m, capex, tgr, rfr, erp
)

current_price = info.get('currentPrice', 0)
upside = (price / current_price - 1) * 100 if current_price else 0
rating = "BUY" if upside > 10 else "SELL" if upside < -10 else "HOLD"

# ── HEADER ───────────────────────────────────────────
st.title(f"📊 {info.get('longName', ticker)} ({ticker})")
st.caption(f"{info.get('sector','')} · {info.get('industry','')}")
st.divider()

# ── EXECUTIVE SUMMARY ────────────────────────────────
st.subheader("0️⃣ Executive Summary")
st.info(f"""
As of **{pd.Timestamp.now().strftime('%B %Y')}**, 
**{info.get('longName', ticker)} ({ticker})** appears 
**{'undervalued' if upside > 0 else 'overvalued'}** 
by ~**{abs(upside):.0f}%**, with a DCF target of 
**${price:.0f}** vs current **${current_price:.0f}**.  
Rating : **{rating}**
""")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Current Price",  f"${current_price:.2f}")
c2.metric("DCF Target",     f"${price:.2f}", f"{upside:+.1f}%")
c3.metric("WACC",           f"{results.get('wacc',0):.2%}")
c4.metric("Rating",         rating)
st.divider()

# ── PRICE CHART ──────────────────────────────────────
st.subheader("📈 Price History")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=hist.index, y=hist['Close'],
    fill='tozeroy', line=dict(color='#3498db', width=2),
    name='Price'
))
fig.add_hline(y=price, line_dash='dash', line_color='green',
              annotation_text=f"DCF ${price:.0f}")
fig.add_hline(y=current_price, line_dash='dot', line_color='red',
              annotation_text=f"Current ${current_price:.0f}")
fig.update_layout(height=350, template='plotly_white')
st.plotly_chart(fig, use_container_width=True)
st.divider()

# ── DCF TABLE ────────────────────────────────────────
st.subheader("💡 DCF — UFCF Projection")
st.caption("UFCF = EBIT(1-t) - CapEx - ΔNWC")
st.dataframe(proj.round(1), hide_index=True, use_container_width=True)

# ── WACC BREAKDOWN ───────────────────────────────────
st.subheader("📊 WACC Breakdown")
w1, w2, w3, w4 = st.columns(4)
w1.metric("Cost of Equity",  f"{results.get('cost_of_equity',0):.2%}")
w2.metric("Cost of Debt",    f"{results.get('cost_of_debt',0):.2%}")
w3.metric("Weight Equity",   f"{results.get('weight_equity',0):.0%}")
w4.metric("Weight Debt",     f"{results.get('weight_debt',0):.0%}")

st.caption("⚠️ For educational purposes only. Not investment advice.")
