import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DCFAssumptions:
    forecast_years: int = 5
    revenue_growth_rates: list = field(
        default_factory=lambda: [0.08, 0.08, 0.07, 0.06, 0.05]
    )
    fcf_margins: list = field(
        default_factory=lambda: [0.26, 0.27, 0.27, 0.28, 0.28]
    )
    terminal_growth_rate: float = 0.03
    risk_free_rate: float = 0.045
    equity_risk_premium: float = 0.055
    beta: float = 1.25
    cost_of_debt: float = 0.035
    tax_rate: float = 0.21
    weight_equity: float = 0.85
    weight_debt: float = 0.15
    shares_outstanding_m: float = 15_400.0
    net_cash_m: float = 55_000.0


class DCFModel:
    def __init__(self, base_revenue_m, assumptions=None):
        self.base_revenue_m = base_revenue_m
        self.a = assumptions or DCFAssumptions()
        self._results = {}

    def compute_wacc(self):
        a = self.a
        cost_of_equity = a.risk_free_rate + a.beta * a.equity_risk_premium
        after_tax_cod  = a.cost_of_debt * (1 - a.tax_rate)
        wacc = a.weight_equity * cost_of_equity + a.weight_debt * after_tax_cod
        self._results['wacc'] = wacc
        self._results['cost_of_equity'] = cost_of_equity
        return wacc

    def project_fcf(self):
        a = self.a
        revenue = self.base_revenue_m
        rows = []
        for i in range(a.forecast_years):
            revenue = revenue * (1 + a.revenue_growth_rates[i])
            fcf     = revenue * a.fcf_margins[i]
            rows.append({
                'year'       : f'Y+{i+1}',
                'revenue_m'  : revenue,
                'fcf_margin' : a.fcf_margins[i],
                'fcf_m'      : fcf,
            })
        self._projection = pd.DataFrame(rows)
        return self._projection

    def discount(self, wacc):
        proj    = self._projection
        pv_fcfs = []
        for i, row in proj.iterrows():
            pv_fcfs.append(row['fcf_m'] / (1 + wacc) ** (i + 1))

        terminal_fcf = proj['fcf_m'].iloc[-1]
        g  = self.a.terminal_growth_rate
        tv = terminal_fcf * (1 + g) / (wacc - g)
        pv_tv = tv / (1 + wacc) ** self.a.forecast_years

        self._projection['pv_fcf_m'] = pv_fcfs
        self._results.update({
            'pv_fcf_total_m'    : sum(pv_fcfs),
            'pv_terminal_m'     : pv_tv,
            'enterprise_value_m': sum(pv_fcfs) + pv_tv,
            'tv_pct_of_ev'      : pv_tv / (sum(pv_fcfs) + pv_tv),
        })

    def equity_value_per_share(self):
        ev    = self._results['enterprise_value_m']
        eq    = ev + self.a.net_cash_m
        price = eq / self.a.shares_outstanding_m
        self._results['equity_value_m']  = eq
        self._results['intrinsic_price'] = price
        return price

    def run(self):
        wacc = self.compute_wacc()
        self.project_fcf()
        self.discount(wacc)
        self.equity_value_per_share()
        return self._results

    def summary(self):
        r = self._results
        print("=" * 45)
        print("  DCF VALUATION SUMMARY")
        print("=" * 45)
        print(f"  WACC            : {r['wacc']:.2%}")
        print(f"  PV of FCFs      : ${r['pv_fcf_total_m']/1e3:,.1f}B")
        print(f"  PV Terminal Val : ${r['pv_terminal_m']/1e3:,.1f}B")
        print(f"  TV % of EV      : {r['tv_pct_of_ev']:.1%}")
        print(f"  Enterprise Value: ${r['enterprise_value_m']/1e3:,.1f}B")
        print(f"  Equity Value    : ${r['equity_value_m']/1e3:,.1f}B")
        print(f"  Intrinsic Price : ${r['intrinsic_price']:.2f}")
        print("=" * 45)


# TEST
if __name__ == "__main__":
    model = DCFModel(base_revenue_m=391_035)
    model.run()
    model.summary()

