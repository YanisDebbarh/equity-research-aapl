import yfinance as yf
import pandas as pd
import numpy as np
import time

SECTOR_DEFAULTS = {
    'Technology':            {'growth': 0.10, 'margin': 0.25, 'tgr': 0.03},
    'Consumer Cyclical':     {'growth': 0.07, 'margin': 0.08, 'tgr': 0.025},
    'Consumer Defensive':    {'growth': 0.04, 'margin': 0.10, 'tgr': 0.02},
    'Healthcare':            {'growth': 0.08, 'margin': 0.15, 'tgr': 0.025},
    'Financial Services':    {'growth': 0.06, 'margin': 0.20, 'tgr': 0.02},
    'Industrials':           {'growth': 0.05, 'margin': 0.10, 'tgr': 0.02},
    'Energy':                {'growth': 0.03, 'margin': 0.12, 'tgr': 0.015},
    'Communication Services':{'growth': 0.07, 'margin': 0.18, 'tgr': 0.025},
    'Real Estate':           {'growth': 0.04, 'margin': 0.30, 'tgr': 0.02},
    'Utilities':             {'growth': 0.03, 'margin': 0.15, 'tgr': 0.015},
    'Basic Materials':       {'growth': 0.04, 'margin': 0.10, 'tgr': 0.02},
    'DEFAULT':               {'growth': 0.06, 'margin': 0.12, 'tgr': 0.025},
}

FALLBACK = {
    'revenue_ltm'        : 0,
    'ebit_margin_avg'    : 0.15,
    'capex_pct_avg'      : 0.05,
    'nwc_pct_avg'        : 0.02,
    'tax_rate'           : 0.21,
    'revenue_growth_hist': 0.07,
}


class DCFAdvanced:

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.stock  = yf.Ticker(ticker)
        self.info   = {}
        for attempt in range(3):
            try:
                data = self.stock.info
                if data and isinstance(data, dict):
                    self.info = data
                    break
            except Exception:
                if attempt < 2:
                    time.sleep(3)

    # ── SECTOR DEFAULTS ──────────────────────────────
    def get_sector_defaults(self):
        try:
            sector = self.info.get('sector', 'DEFAULT')
            if not sector:
                sector = 'DEFAULT'
            return SECTOR_DEFAULTS.get(sector, SECTOR_DEFAULTS['DEFAULT'])
        except Exception:
            return SECTOR_DEFAULTS['DEFAULT']

    # ── HISTORICAL DATA ──────────────────────────────
    def get_historical_data(self):
        try:
            income  = self.stock.financials.T
            balance = self.stock.balance_sheet.T
            cf      = self.stock.cashflow.T

            def safe(df, *keys):
                for k in keys:
                    if k in df.columns:
                        return pd.to_numeric(df[k], errors='coerce')
                return pd.Series([np.nan] * len(df), index=df.index)

            revenue = safe(income, 'Total Revenue')
            ebit    = safe(income, 'EBIT', 'Operating Income')
            tax_exp = safe(income, 'Tax Provision', 'Income Tax Expense')
            pretax  = safe(income, 'Pretax Income')
            capex   = safe(cf, 'Capital Expenditure')
            curr_a  = safe(balance, 'Current Assets')
            curr_l  = safe(balance, 'Current Liabilities')
            cash    = safe(balance,
                          'Cash And Cash Equivalents',
                          'Cash Cash Equivalents And Short Term Investments')

            nwc         = curr_a - cash - curr_l
            tax_rate    = (tax_exp / pretax).clip(0.10, 0.35).mean()
            if pd.isna(tax_rate):
                tax_rate = 0.21

            ebit_margin = (ebit / revenue).clip(0, 0.60)
            capex_pct   = (capex.abs() / revenue).clip(0, 0.20)
            delta_nwc   = nwc.diff(-1)
            nwc_pct     = (delta_nwc / revenue).clip(-0.10, 0.10)
            rev_growth  = revenue.pct_change(-1).mean()
            if pd.isna(rev_growth):
                rev_growth = 0.07

            return {
                'revenue_ltm'        : float(revenue.iloc[0] / 1e6),
                'ebit_margin_avg'    : float(ebit_margin.mean()),
                'capex_pct_avg'      : float(capex_pct.mean()),
                'nwc_pct_avg'        : float(nwc_pct.mean()),
                'tax_rate'           : float(tax_rate),
                'revenue_growth_hist': float(rev_growth),
            }

        except Exception:
            try:
                rev = (self.info.get('totalRevenue', 0) or 0) / 1e6
            except Exception:
                rev = 0
            result = FALLBACK.copy()
            result['revenue_ltm'] = rev
            return result

    # ── WACC ─────────────────────────────────────────
    def compute_wacc(self, rfr=0.045, erp=0.055):
        try:
            beta     = float(self.info.get('beta', 1.2) or 1.2)
            ke       = rfr + beta * erp
            interest = abs(float(self.info.get('interestExpense', 0) or 0))
            debt     = float(self.info.get('totalDebt', 1) or 1)
            kd_pre   = max(0.02, min(0.10, interest / debt))
            hist     = self.get_historical_data()
            t        = hist['tax_rate']
            kd       = kd_pre * (1 - t)
            mkt_cap  = float(self.info.get('marketCap', 1) or 1)
            we       = mkt_cap / (mkt_cap + debt)
            wd       = debt    / (mkt_cap + debt)
            wacc     = max(0.06, min(0.15, we * ke + wd * kd))
        except Exception:
            ke, kd, we, wd, t = 0.11, 0.03, 0.85, 0.15, 0.21
            wacc = 0.10

        self._results = {
            'wacc'          : wacc,
            'cost_of_equity': ke,
            'cost_of_debt'  : kd,
            'weight_equity' : we,
            'weight_debt'   : wd,
            'tax_rate'      : t,
        }
        return wacc

    # ── UFCF PROJECTION ──────────────────────────────
    def project_ufcf(self, growth_rates, ebit_margin,
                     capex_pct, nwc_pct, tax_rate, base_revenue):
        revenue = base_revenue
        rows    = []
        for i, g in enumerate(growth_rates):
            revenue = revenue * (1 + g)
            ebit    = revenue * ebit_margin
            nopat   = ebit * (1 - tax_rate)
            capex   = revenue * capex_pct
            d_nwc   = revenue * nwc_pct
            ufcf    = nopat - capex - d_nwc
            rows.append({
                'year'     : f'Y+{i+1}',
                'revenue_m': round(revenue, 1),
                'ebit_m'   : round(ebit, 1),
                'nopat_m'  : round(nopat, 1),
                'capex_m'  : round(capex, 1),
                'ufcf_m'   : round(ufcf, 1),
            })
        self._projection = pd.DataFrame(rows)
        return self._projection

    # ── DISCOUNT ─────────────────────────────────────
    def discount(self, wacc, tgr):
        proj    = self._projection
        pv_list = []
        for i, row in proj.iterrows():
            pv_list.append(row['ufcf_m'] / (1 + wacc) ** (i + 1))

        terminal = proj['ufcf_m'].iloc[-1]
        tv       = terminal * (1 + tgr) / (wacc - tgr)
        pv_tv    = tv / (1 + wacc) ** len(proj)
        pv_total = sum(pv_list)
        ev       = pv_total + pv_tv

        self._projection['pv_ufcf_m'] = pv_list
        self._results.update({
            'pv_ufcf_total_m'   : pv_total,
            'pv_terminal_m'     : pv_tv,
            'enterprise_value_m': ev,
            'tv_pct_of_ev'      : pv_tv / ev if ev > 0 else 0,
        })
        return self._results

    # ── EQUITY PER SHARE ─────────────────────────────
    def equity_per_share(self):
        try:
            ev     = self._results['enterprise_value_m']
            cash   = (self.info.get('totalCash', 0) or 0) / 1e6
            debt   = (self.info.get('totalDebt', 0) or 0) / 1e6
            shares = (self.info.get('sharesOutstanding', 1) or 1) / 1e6
            equity = ev + cash - debt
            price  = equity / shares if shares > 0 else 0
        except Exception:
            price  = 0
            equity = 0

        self._results['equity_value_m']  = equity
        self._results['intrinsic_price'] = price
        return price

    # ── RUN ALL ──────────────────────────────────────
    def run(self, growth_rates, ebit_margin=None,
            capex_pct=None, nwc_pct=None,
            tgr=0.03, rfr=0.045, erp=0.055):
        hist        = self.get_historical_data()
        ebit_margin = ebit_margin if ebit_margin else hist['ebit_margin_avg']
        capex_pct   = capex_pct   if capex_pct   else hist['capex_pct_avg']
        nwc_pct     = nwc_pct     if nwc_pct     else hist['nwc_pct_avg']
        tax_rate    = hist['tax_rate']
        base_rev    = hist['revenue_ltm']
        wacc        = self.compute_wacc(rfr, erp)
        self.project_ufcf(growth_rates, ebit_margin,
                          capex_pct, nwc_pct, tax_rate, base_rev)
        self.discount(wacc, tgr)
        return self.equity_per_share(), self._results
