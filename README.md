# 📊 Equity Research — Apple Inc. (AAPL)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Rating](https://img.shields.io/badge/Rating-SELL-red)
![Status](https://img.shields.io/badge/Coverage-Initiated-green)

> **Blended Target Price : $203 | Current : $299 | Downside : -32%**

---

## 📋 Overview

Professional-grade equity research report on Apple Inc. built 
entirely in Python. Covers the full sell-side workflow from 
raw data collection to final recommendation.

**Initiated Coverage : May 2026 | Rating : SELL | TP : $203**

---

## 💡 Key Results

| Metric | Value |
|--------|-------|
| DCF Intrinsic Value | $163.54 |
| Comps-Implied Price | $242.46 |
| Blended Target Price | $203.00 |
| Current Price | $298.97 |
| Upside / (Downside) | -32.1% |
| Rating | **SELL** |
| WACC | 9.22% |
| Monte Carlo Median | $162 |
| P(Undervalued) | 4.6% |

---

## 🏗️ Methodology

| Section | Method | Output |
|---------|--------|--------|
| Data Collection | yfinance API | Raw CSV files |
| Financial Analysis | Pandas + Matplotlib | KPI charts |
| DCF Model | WACC + Gordon Growth | Intrinsic price |
| Comps Analysis | EV/EBITDA, P/E, EV/Sales | Peer price |
| Sensitivity | WACC × TGR heatmap | Price range |
| Monte Carlo | 10,000 simulations | Distribution |

---

## ⚙️ Technologies

- **yfinance** — Market data & financials
- **pandas / numpy** — Data manipulation
- **matplotlib / plotly** — Charts
- **streamlit** — Live dashboard
- **scipy** — Monte Carlo distributions

---

## 🚀 Quick Start

```bash
git clone https://github.com/YanisDebbarh/equity-research-aapl
cd equity-research-aapl
pip install -r requirements.txt
streamlit run app.py
