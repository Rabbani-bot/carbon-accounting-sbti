"""GHG Protocol inventory for a modelled textile manufacturer ("Indus Weave Ltd", 3 sites), 2022-2025.

Activity data generated with a fixed seed. Emission factors are rounded representative values of the kind
published by DEFRA/DESNZ, IPCC AR6 and national grid operators; they are representative, not an
official factor set. Methods follow the GHG Protocol Corporate Standard, Scope 2 Guidance (dual
reporting) and Scope 3 Standard, with SBTi near-term cross-sector pathway rates.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

SEED = 42
YEARS = [2022, 2023, 2024, 2025]
BASE_YEAR = 2022
SITES = {  # production share, grid EF (location, kg/kWh), residual-mix EF (market, kg/kWh)
    "Faisalabad (PK)": dict(grid=0.42, residual=0.47),
    "Izmir (TR)": dict(grid=0.44, residual=0.50),
    "Chemnitz (DE)": dict(grid=0.38, residual=0.62),
}
FUEL_EF = {"natural_gas_m3": 2.02, "diesel_L": 2.68, "lpg_L": 1.56}      # kg CO2e per unit, combustion
REFRIG_GWP = {"R-410A": 2256, "R-134a": 1530, "R-32": 771}             # AR6 GWP100
SCOPE3 = [  # category, method, data-quality score (1 best - 5 worst), relevant?
    (1, "Purchased goods & services", "hybrid (supplier + spend)", 3, True),
    (2, "Capital goods", "spend-based", 4, True),
    (3, "Fuel- & energy-related activities", "average-data (WTT, T&D)", 2, True),
    (4, "Upstream transport & distribution", "distance-based", 3, True),
    (5, "Waste generated in operations", "waste-type", 3, True),
    (6, "Business travel", "distance-based", 2, True),
    (7, "Employee commuting", "survey extrapolation", 4, True),
    (8, "Upstream leased assets", "n/a", 5, False),
    (9, "Downstream transport & distribution", "distance-based", 4, True),
    (10, "Processing of sold products", "average-data", 4, True),
    (11, "Use of sold products", "indirect (laundering)", 5, True),
    (12, "End-of-life of sold products", "waste-type", 4, True),
    (13, "Downstream leased assets", "n/a", 5, False),
    (14, "Franchises", "n/a", 5, False),
    (15, "Investments", "n/a", 5, False),
]
DQ_GSD = {1: 1.05, 2: 1.10, 3: 1.25, 4: 1.50, 5: 2.00}   # pedigree-style uncertainty per data-quality score


def generate(seed: int = SEED) -> dict:
    """Monthly activity data by site for 2022-2025, with a decarbonisation programme from 2023."""
    rng = np.random.default_rng(seed)
    rows = []
    base_prod = {"Faisalabad (PK)": 1100, "Izmir (TR)": 750, "Chemnitz (DE)": 400}   # t fabric / month
    for y in YEARS:
        t = y - BASE_YEAR
        for site, prod0 in base_prod.items():
            growth = (1.06 if site == "Faisalabad (PK)" else 1.02) ** t
            eff = 0.965 ** t                                       # energy-efficiency programme
            for m in range(1, 13):
                season = 1 + 0.08 * np.sin(2 * np.pi * (m - 3) / 12)
                prod = prod0 * growth * season * rng.normal(1, 0.03)
                heat_season = 1 + (0.25 if site == "Chemnitz (DE)" else 0.08) * np.cos(2 * np.pi * (m - 1) / 12)
                electrification = 1 - 0.07 * t if site != "Faisalabad (PK)" else 1 - 0.03 * t
                rows.append(dict(year=y, month=m, site=site, production_t=prod,
                                 electricity_kWh=prod * 1450 * eff * (2 - electrification) * rng.normal(1, 0.02),
                                 natural_gas_m3=prod * 310 * eff * electrification * heat_season * rng.normal(1, 0.03),
                                 diesel_L=prod * 6.0 * (0.9 ** t) * rng.normal(1, 0.08),
                                 lpg_L=prod * 1.2 * rng.normal(1, 0.1)))
    act = pd.DataFrame(rows)
    # refrigerant top-ups (kg) by year and site - mass-balance method
    ref = pd.DataFrame([dict(year=y, site=s, gas=g, kg=max(0, rng.normal(mu, mu * 0.25)))
                        for y in YEARS for s in SITES for g, mu in [("R-410A", 14), ("R-134a", 9), ("R-32", 3 + 2 * (y - 2022))]])
    # renewable electricity instruments (share of site consumption): PPA/RECs ramping up
    instr = pd.DataFrame([dict(year=y, site=s, re_share=v) for y in YEARS for s, v in
                          zip(SITES, [min(0.05 + 0.10 * (y - 2022), 1), min(0.10 * (y - 2022), 1), min(0.30 + 0.20 * (y - 2022), 1)])])
    revenue_musd = {2022: 182.0, 2023: 195.5, 2024: 207.3, 2025: 221.0}
    # Scope 3 annual totals (t CO2e), base and trend
    s3_base = {1: 61500, 2: 4200, 3: 3900, 4: 6800, 5: 900, 6: 650, 7: 1300, 9: 5400, 10: 2900, 11: 7200, 12: 2600}
    s3_trend = {1: -0.035, 4: -0.02, 6: 0.04, 9: -0.01}
    s3 = pd.DataFrame([dict(year=y, category=c, tco2e=v * (1 + s3_trend.get(c, 0.0)) ** (y - 2022)
                            * (1.03 ** (y - 2022)) * rng.normal(1, 0.02)) for y in YEARS for c, v in s3_base.items()])
    return dict(activity=act, refrigerants=ref, instruments=instr, revenue=revenue_musd, scope3=s3)


def scope1(act: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    a = act.groupby(["year", "site"])[list(FUEL_EF)].sum()
    out = pd.DataFrame({f: a[f] * ef / 1000 for f, ef in FUEL_EF.items()})
    r = ref.assign(t=lambda d: d.kg * d.gas.map(REFRIG_GWP) / 1000).groupby(["year", "site"]).t.sum()
    out["refrigerants"] = r
    out["scope1"] = out.sum(axis=1)
    return out


def scope2(act: pd.DataFrame, instr: pd.DataFrame) -> pd.DataFrame:
    """Dual reporting. Location: grid average. Market: contractual instruments at 0, remainder at residual mix."""
    e = act.groupby(["year", "site"]).electricity_kWh.sum().to_frame()
    e = e.join(instr.set_index(["year", "site"]))
    grid = e.index.get_level_values("site").map(lambda s: SITES[s]["grid"])
    resid = e.index.get_level_values("site").map(lambda s: SITES[s]["residual"])
    e["location_t"] = e.electricity_kWh * np.asarray(grid) / 1000
    e["market_t"] = e.electricity_kWh * (1 - e.re_share) * np.asarray(resid) / 1000
    return e


def sbti_pathway(base: float, years, rate: float, base_year: int = BASE_YEAR) -> np.ndarray:
    """Linear absolute-contraction pathway: base * (1 - rate * (year - base_year))."""
    return base * (1 - rate * (np.asarray(years) - base_year))


def lmdi(e0, e1, q0, q1, s0, s1, i0, i1, f0, f1) -> dict:
    """Additive LMDI-I decomposition of E = Q * S_i * I_i * F_i summed over sites.
    Q activity (total production), S structure (site share), I energy intensity (GJ/t), F carbon factor (t/GJ).
    Inputs other than Q are arrays over sites. Result sums exactly to E1 - E0."""
    e0, e1 = np.asarray(e0, float), np.asarray(e1, float)
    L = np.where(np.isclose(e0, e1), e0, (e1 - e0) / (np.log(e1) - np.log(e0)))
    comp = {"Activity": np.sum(L * np.log(q1 / q0)), "Structure": np.sum(L * np.log(np.asarray(s1) / np.asarray(s0))),
            "Energy intensity": np.sum(L * np.log(np.asarray(i1) / np.asarray(i0))),
            "Carbon factor": np.sum(L * np.log(np.asarray(f1) / np.asarray(f0)))}
    comp["Total"] = float(e1.sum() - e0.sum())
    return {k: float(v) for k, v in comp.items()}


def monte_carlo_scope3(s3_year: pd.DataFrame, n: int = 10000, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    dq = {c: d for c, _, _, d, _ in SCOPE3}
    tot = np.zeros(n)
    for _, r in s3_year.iterrows():
        g = DQ_GSD[dq[int(r.category)]]
        # lognormal with median adjusted so the mean equals the point estimate
        tot += r.tco2e * rng.lognormal(-0.5 * np.log(g) ** 2, np.log(g), n)
    return tot
