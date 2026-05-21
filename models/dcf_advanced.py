"""
models/dcf_advanced.py
──────────────────────
DCF institutionnel avec données réelles yfinance
UFCF = EBIT(1-t) - CapEx - ΔNWC
"""
import yfinance as yf
import pandas as pd
import numpy as np


SECTOR_DEFAULTS = {
    'Technology':           {'growth': 0.10, 'margin': 0.25, 'tgr': 0.03},
    'Consumer Cyclical':    {'growth': 0.07, 'margin': 0.08, 'tgr': 0.025},
    'Consumer Defensive':   {'growth': 0.04, 'margin': 0.10, 'tgr': 0.02},
    'Healthcare':           {'growth': 0.08, 'margin': 0.15, 'tgr': 0.025},
    'Financial Services':   {'growth': 0.06, 'margin': 0.20, 'tgr': 0.02},
    'Industrials':          {'growth': 0.05, 'margin': 0.10, 'tgr': 0.02},
    'Energy':               {'growth': 0.03, 'margin': 0.12, 'tgr': 0.015},
    'Communication Services':{'growth': 0.07, 'margin': 0.18, 'tgr': 0.025},
    'Real Estate':          {'growth': 0.04, 'margin': 0.30, 'tgr': 0.02},
    'Utilities':            {'growth': 0.03, 'margin': 0.15, 'tgr': 0.015},
    'Basic Materials':      {'growth': 0.04, 'margin': 0.10, 'tgr': 0.02},
    'DEFAULT':              {'growth': 0.06, 'margin': 0.12, 'tgr': 0.025},
}


class DCFAdvanced:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.stock  = yf.Ticker(ticker)
        self.info   = self.stock.info
        self._results = {}

    # ── SECTOR DEFAULTS ──────────────────────────────
    def get_sector_defaults(self) -> dict:
        sector = self.info.get('sector', 'DEFAULT')
        return SECTOR_DEFAULTS.get(sector, SECTOR_DEFAULTS['DEFAULT'])

    # ── HISTORICAL FINANCIALS ────────────────────────
    def get_historical_data(self) -> dict:
        try:
            income = self.stock.financials.T
            balance= self.stock.balance_sheet.T
            cf     = self.stock.cashflow.T

            def safe(df, *keys):
                for k in keys:
                    if k in df.columns:
                        return pd.to_numeric(df[k], errors='coerce')
                return pd.Series([np.nan]*len(df), index=df.index)

            revenue  = safe(income, 'Total Revenue')
            ebit     = safe(income, 'EBIT', 'Operating Income')
            tax_exp  = safe(income, 'Tax Provision', 'Income Tax Expense')
            pretax   = safe(income, 'Pretax Income')
            capex    = safe(cf, 'Capital Expenditure')
            curr_a   = safe(balance, 'Current Assets')
            curr_l   = safe(balance, 'Current Liabilities')
            cash     = safe(balance, 'Cash And Cash Equivalents',
                           'Cash Cash Equivalents And Short Term Investments')

            # NWC = Current Assets - Cash - Current Liabilities
            nwc = curr_a - cash - curr_l

            # Effective tax rate
            tax_rate = (tax_exp / pretax).clip(0.10, 0.35).mean()
            if pd.isna(tax_rate): tax_rate = 0.21

            # EBIT Margin
            ebit_margin = (ebit / revenue).clip(0, 0.60)

            # CapEx % Revenue
            capex_pct = (capex.abs() / revenue).clip(0, 0.20)

            # ΔNWC
            delta_nwc = nwc.diff(-1)  # YoY change
            nwc_pct   = (delta_nwc / revenue).clip(-0.10, 0.10)

            return {
                'revenue_ltm'    : revenue.iloc[0] / 1e6,
                'ebit_margin_avg': float(ebit_margin.mean()),
                'capex_pct_avg'  : float(capex_pct.mean()),
                'nwc_pct_avg'    : float(nwc_pct.mean()),
                'tax_rate'       : float(tax_rate),
                'revenue_growth_hist': float(revenue.pct_change(-1).mean()),
            }
        except Exception as e:
            return {
                'revenue_ltm'    : self.info.get('totalRevenue',0)/1e6,
                'ebit_margin_avg': 0.15,
                'capex_pct_avg'  : 0.05,
                'nwc_pct_avg'    : 0.02,
                'tax_rate'       : 0.21,
                'revenue_growth_hist': 0.07,
            }

    # ── WACC PRÉCIS ──────────────────────────────────
    def compute_wacc(self, rfr=0.045, erp=0.055) -> float:
        info = self.info
        beta = info.get('beta', 1.2) or 1.2

        # Cost of equity (CAPM)
        ke = rfr + beta * erp

        # Cost of debt réel
        interest = abs(info.get('interestExpense', 0) or 0)
        debt      = info.get('totalDebt', 1) or 1
        kd_pretax = interest / debt if debt > 0 else 0.04
        kd_pretax = max(0.02, min(0.10, kd_pretax))

        # Tax rate
        hist = self.get_historical_data()
        t    = hist['tax_rate']
        kd   = kd_pretax * (1 - t)

        # Capital structure
        mkt_cap = info.get('marketCap', 1) or 1
        we = mkt_cap / (mkt_cap + debt)
        wd = debt    / (mkt_cap + debt)

        wacc = we * ke + wd * kd
        wacc = max(0.06, min(0.15, wacc))

        self._results['wacc']           = wacc
        self._results['cost_of_equity'] = ke
        self._results['cost_of_debt']   = kd
        self._results['weight_equity']  = we
        self._results['weight_debt']    = wd
        self._results['tax_rate']       = t
        return wacc

    # ── UFCF PROJECTION ──────────────────────────────
    def project_ufcf(
        self,
        growth_rates: list,
        ebit_margin : float,
        capex_pct   : float,
        nwc_pct     : float,
        tax_rate    : float,
        base_revenue: float,
    ) -> pd.DataFrame:

        revenue = base_revenue
        rows    = []
        for i, g in enumerate(growth_rates):
            revenue  = revenue * (1 + g)
            ebit     = revenue * ebit_margin
            nopat    = ebit * (1 - tax_rate)
            capex    = revenue * capex_pct
            d_nwc    = revenue * nwc_pct
            ufcf     = nopat - capex - d_nwc
            rows.append({
                'year'       : f'Y+{i+1}',
                'revenue_m'  : round(revenue, 1),
                'ebit_m'     : round(ebit, 1),
                'nopat_m'    : round(nopat, 1),
                'capex_m'    : round(capex, 1),
                'ufcf_m'     : round(ufcf, 1),
            })
        self._projection = pd.DataFrame(rows)
        return self._projection

    # ── DISCOUNT ─────────────────────────────────────
    def discount(self, wacc: float, tgr: float) -> dict:
        proj    = self._projection
        pv_ufcf = []
        for i, row in proj.iterrows():
            pv = row['ufcf_m'] / (1 + wacc) ** (i + 1)
            pv_ufcf.append(pv)

        terminal_ufcf = proj['ufcf_m'].iloc[-1]
        tv    = terminal_ufcf * (1 + tgr) / (wacc - tgr)
        pv_tv = tv / (1 + wacc) ** len(proj)

        self._projection['pv_ufcf_m'] = pv_ufcf
        pv_total = sum(pv_ufcf)
        ev       = pv_total + pv_tv

        self._results.update({
            'pv_ufcf_total_m'   : pv_total,
            'pv_terminal_m'     : pv_tv,
            'enterprise_value_m': ev,
            'tv_pct_of_ev'      : pv_tv / ev if ev > 0 else 0,
        })
        return self._results

    # ── EQUITY PER SHARE ─────────────────────────────
    def equity_per_share(self) -> float:
        info    = self.info
        ev      = self._results['enterprise_value_m']
        cash    = (info.get('totalCash', 0) or 0) / 1e6
        debt    = (info.get('totalDebt', 0) or 0) / 1e6
        shares  = (info.get('sharesOutstanding', 1) or 1) / 1e6
        equity  = ev + cash - debt
        price   = equity / shares if shares > 0 else 0
        self._results['equity_value_m']  = equity
        self._results['intrinsic_price'] = price
        self._results['shares_m']        = shares
        return price

    # ── RUN ALL ──────────────────────────────────────
    def run(
        self,
        growth_rates: list,
        ebit_margin : float = None,
        capex_pct   : float = None,
        nwc_pct     : float = None,
        tgr         : float = 0.03,
        rfr         : float = 0.045,
        erp         : float = 0.055,
    ) -> dict:
        hist = self.get_historical_data()

        ebit_margin = ebit_margin or hist['ebit_margin_avg']
        capex_pct   = capex_pct   or hist['capex_pct_avg']
        nwc_pct     = nwc_pct     or hist['nwc_pct_avg']
        tax_rate    = hist['tax_rate']
        base_rev    = hist['revenue_ltm']

        wacc = self.compute_wacc(rfr, erp)
        self.project_ufcf(growth_rates, ebit_margin,
                          capex_pct, nwc_pct, tax_rate, base_rev)
        self.discount(wacc, tgr)
        return self.equity_per_share(), self._results
