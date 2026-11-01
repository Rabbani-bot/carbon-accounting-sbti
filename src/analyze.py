"""Build the corporate GHG inventory, SBTi target tracking, LMDI decomposition, tables and figures."""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT.parent / "common"))
import carbon as cb  # noqa: E402
import style  # noqa: E402

FIG, OUT, DATA = ROOT / "outputs" / "figures", ROOT / "outputs", ROOT / "data"
NOTE = "Mohammad Rabbani | github.com/Rabbani-bot"
GJ = {"electricity_kWh": 0.0036, "natural_gas_m3": 0.0373, "diesel_L": 0.0386, "lpg_L": 0.0255}
P = style.PALETTE


def main():
    style.apply()
    for d in (FIG, DATA): d.mkdir(parents=True, exist_ok=True)
    d = cb.generate()
    d["activity"].round(2).to_csv(DATA / "activity_monthly.csv", index=False)
    s1 = cb.scope1(d["activity"], d["refrigerants"]); s2 = cb.scope2(d["activity"], d["instruments"])
    s3 = d["scope3"]
    y = pd.DataFrame({"Scope 1": s1.scope1.groupby("year").sum(), "Scope 2 (location)": s2.location_t.groupby("year").sum(),
                      "Scope 2 (market)": s2.market_t.groupby("year").sum(), "Scope 3": s3.groupby("year").tco2e.sum()})
    y["Total (market)"] = y["Scope 1"] + y["Scope 2 (market)"] + y["Scope 3"]
    prod = d["activity"].groupby("year").production_t.sum()
    y["Production (t)"] = prod; y["Revenue ($M)"] = pd.Series(d["revenue"])
    y["S1+2 intensity (t/t fabric)"] = (y["Scope 1"] + y["Scope 2 (market)"]) / prod
    y["Total intensity (t/$M)"] = y["Total (market)"] / y["Revenue ($M)"]
    y.round(2).to_csv(OUT / "table1_inventory_by_year.csv")
    s1.groupby("year").sum().round(1).to_csv(OUT / "table2_scope1_by_source.csv")
    s2.round(1).to_csv(OUT / "table3_scope2_dual_reporting.csv")

    # Scope 3 screening table (2025)
    s3y = s3[s3.year == 2025].set_index("category").tco2e
    scr = pd.DataFrame([dict(category=c, name=n, method=m, data_quality=q, relevant=r, tco2e=float(s3y.get(c, 0.0)))
                        for c, n, m, q, r in cb.SCOPE3])
    scr["share_%"] = 100 * scr.tco2e / scr.tco2e.sum()
    scr.round(2).to_csv(OUT / "table4_scope3_screening_2025.csv", index=False)

    # SBTi targets (base 2022, near-term 2030)
    s12_base = y.loc[2022, "Scope 1"] + y.loc[2022, "Scope 2 (market)"]
    s3_base = y.loc[2022, "Scope 3"]
    yrs = np.arange(2022, 2031)
    path12, path3 = cb.sbti_pathway(s12_base, yrs, 0.042), cb.sbti_pathway(s3_base, yrs, 0.025)
    s12 = y["Scope 1"] + y["Scope 2 (market)"]
    tgt = pd.DataFrame({"year": y.index, "S1+2 actual": s12.values, "S1+2 pathway": path12[:4],
                        "S3 actual": y["Scope 3"].values, "S3 pathway": path3[:4]})
    tgt["S1+2 gap %"] = 100 * (tgt["S1+2 actual"] / tgt["S1+2 pathway"] - 1)
    tgt["S3 gap %"] = 100 * (tgt["S3 actual"] / tgt["S3 pathway"] - 1)
    tgt.round(1).to_csv(OUT / "table5_sbti_tracking.csv", index=False)
    # linear trend projection to 2030
    proj = {}
    for k, series in [("S1+2", s12), ("S3", y["Scope 3"])]:
        b = np.polyfit(series.index, series.values, 1)
        proj[k] = float(np.polyval(b, 2030))

    # LMDI on energy-related Scope 1+2 (location-based, refrigerants excluded), 2022 -> 2025
    lm, lm_inputs = lmdi_inputs(d["activity"], s1, s2)
    pd.DataFrame([lm]).T.rename(columns={0: "tCO2e"}).round(1).to_csv(OUT / "table6_lmdi_decomposition.csv")

    mc = cb.monte_carlo_scope3(s3[s3.year == 2025])
    res = {"inventory_2025": {k: float(v) for k, v in y.loc[2025].items()},
           "change_2022_2025_pct": {k: float(100 * (y.loc[2025, k] / y.loc[2022, k] - 1)) for k in ["Scope 1", "Scope 2 (market)", "Scope 3", "Total (market)", "S1+2 intensity (t/t fabric)"]},
           "scope3_share_of_total_2025_pct": float(100 * y.loc[2025, "Scope 3"] / y.loc[2025, "Total (market)"]),
           "cat1_share_of_scope3_pct": float(scr.set_index("category").loc[1, "share_%"]),
           "sbti": {"S1+2 base": float(s12_base), "S1+2 2030 target": float(path12[-1]), "S1+2 2025 gap %": float(tgt["S1+2 gap %"].iloc[-1]),
                    "S1+2 2030 projection": proj["S1+2"], "S3 base": float(s3_base), "S3 2030 target": float(path3[-1]),
                    "S3 2025 gap %": float(tgt["S3 gap %"].iloc[-1]), "S3 2030 projection": proj["S3"]},
           "lmdi": lm, "scope3_mc_2025": {"P5": float(np.percentile(mc, 5)), "median": float(np.median(mc)), "P95": float(np.percentile(mc, 95))}}

    fig_overview(y); fig_pareto(scr); fig_dual(s2); fig_heatmap(d["activity"])
    fig_sbti(y, yrs, path12, path3, proj); fig_lmdi(lm); fig_uncertainty(mc, y, s1, s2); fig_intensity(y)
    (OUT / "results.json").write_text(json.dumps(res, indent=2))
    return res


def lmdi_inputs(act, s1, s2):
    a = act.groupby(["year", "site"]).sum(numeric_only=True)
    energy = sum(a[k] * f for k, f in GJ.items())
    emis = s1.drop(columns=["refrigerants", "scope1"]).sum(axis=1) + s2.location_t
    sites = list(cb.SITES)
    g = lambda yr, ser: ser.xs(yr, level="year").reindex(sites).to_numpy()
    q0, q1 = a.production_t.xs(2022, level="year").sum(), a.production_t.xs(2025, level="year").sum()
    p0, p1 = g(2022, a.production_t), g(2025, a.production_t)
    e0, e1 = g(2022, emis), g(2025, emis)
    en0, en1 = g(2022, energy), g(2025, energy)
    lm = cb.lmdi(e0, e1, q0, q1, p0 / q0, p1 / q1, en0 / p0, en1 / p1, e0 / en0, e1 / en1)
    return lm, None


def fig_overview(y):
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(y)); bottom = np.zeros(len(y))
    for k, c in [("Scope 1", P[0]), ("Scope 2 (market)", P[1]), ("Scope 3", P[2])]:
        ax.bar(x, y[k] / 1000, bottom=bottom, color=c, width=0.6, label=k, edgecolor="white"); bottom += y[k].to_numpy() / 1000
    loc_tot = (y["Scope 1"] + y["Scope 2 (location)"] + y["Scope 3"]) / 1000
    ax.scatter(x, loc_tot, marker="_", s=900, color="#222", lw=2, label="Total with location-based Scope 2", zorder=5)
    for i, t in enumerate(bottom):
        ax.text(i, t + 3, f"{t:.1f}k", ha="center", fontweight="semibold")
    ax.set_xticks(x); ax.set_xticklabels(y.index); ax.set_ylabel("kt CO2e")
    ax.set_title("Corporate GHG inventory, market-based (GHG Protocol)")
    ax.legend(fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4)
    style.footnote(fig, NOTE); fig.savefig(FIG / "01_inventory_overview.png"); plt.close(fig)


def fig_pareto(scr):
    s = scr.sort_values("tco2e", ascending=False)
    fig, ax = plt.subplots(figsize=(12, 5.4))
    cmap = {1: "#1a9850", 2: "#91cf60", 3: "#fee08b", 4: "#fc8d59", 5: "#d73027"}
    labels = [f"C{c} {n[:30]}" for c, n in zip(s.category, s.name)]
    ax.bar(range(len(s)), s.tco2e / 1000, color=[cmap[q] if r else "#DDD" for q, r in zip(s.data_quality, s.relevant)], edgecolor="#555", lw=0.5)
    ax2 = ax.twinx(); ax2.plot(range(len(s)), s["share_%"].cumsum(), color="#222", marker="o", ms=4); ax2.set_ylim(0, 105)
    ax2.axhline(95, color="#999", ls=":"); ax2.text(len(s) - 0.5, 96, "95% coverage", ha="right", fontsize=8, color="#555")
    ax2.set_ylabel("Cumulative share (%)"); ax2.grid(False); ax2.spines["right"].set_visible(True)
    ax.set_xticks(range(len(s))); ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=8.5); ax.set_ylabel("kt CO2e (2025)")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=cmap[q], label=f"DQ {q}") for q in range(1, 6)] + [Patch(color="#DDD", label="not relevant")],
              title="Data quality (1 best)", fontsize=8, title_fontsize=8, ncol=2, loc="center right")
    ax.set_title("Scope 3 screening, all 15 categories: Pareto by size, coloured by data quality")
    style.footnote(fig, NOTE); fig.savefig(FIG / "02_scope3_pareto.png"); plt.close(fig)


def fig_dual(s2):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    sites = list(cb.SITES); w = 0.38
    for ax, yr in zip(axes, [2022, 2025]):
        d = s2.xs(yr, level="year").reindex(sites)
        x = np.arange(len(sites))
        ax.bar(x - w / 2, d.location_t / 1000, w, color=P[6], label="Location-based")
        ax.bar(x + w / 2, d.market_t / 1000, w, color=P[1], label="Market-based")
        for i, r in enumerate(d.itertuples()):
            ax.text(i + w / 2, r.market_t / 1000 + 0.3, f"RE {r.re_share:.0%}", ha="center", fontsize=8.5)
        ax.set_xticks(x); ax.set_xticklabels(sites); ax.set_title(str(yr))
    axes[0].set_ylabel("kt CO2e"); axes[0].legend(fontsize=9)
    fig.suptitle("Scope 2 dual reporting: residual-mix factors can make market-based HIGHER without instruments (see Chemnitz 2022)",
                 x=0.01, ha="left", fontweight="semibold", fontsize=11.5)
    style.footnote(fig, NOTE); fig.tight_layout(); fig.savefig(FIG / "03_scope2_dual.png"); plt.close(fig)


def fig_heatmap(act):
    a = act.copy()
    a["t"] = sum(a[f] * ef for f, ef in cb.FUEL_EF.items()) / 1000 + a.electricity_kWh * a.site.map(lambda s: cb.SITES[s]["grid"]) / 1000
    a["ym"] = a.year.astype(str) + "-" + a.month.astype(str).str.zfill(2)
    piv = a.pivot_table(index="site", columns="ym", values="t", aggfunc="sum").reindex(list(cb.SITES))
    fig, ax = plt.subplots(figsize=(13, 3.4))
    im = ax.imshow(piv.to_numpy() / 1000, aspect="auto", cmap="YlGnBu")
    ax.set_yticks(range(3)); ax.set_yticklabels(piv.index); ax.grid(False)
    ax.set_xticks(range(0, 48, 3)); ax.set_xticklabels(piv.columns[::3], rotation=45, ha="right", fontsize=8)
    for k in (12, 24, 36): ax.axvline(k - 0.5, color="white", lw=2)
    fig.colorbar(im, ax=ax, label="kt CO2e / month", pad=0.01)
    ax.set_title("Monthly energy emissions by site (Scope 1 fuels + Scope 2 location-based): seasonality and trend")
    style.footnote(fig, NOTE); fig.savefig(FIG / "04_monthly_heatmap.png"); plt.close(fig)


def fig_sbti(y, yrs, path12, path3, proj):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    for ax, actual, path, k, rate in [(axes[0], y["Scope 1"] + y["Scope 2 (market)"], path12, "S1+2", "4.2%/yr (1.5°C)"),
                                       (axes[1], y["Scope 3"], path3, "S3", "2.5%/yr (well-below 2°C)")]:
        ax.plot(yrs, path / 1000, color=P[5], lw=2.2, ls="--", label=f"SBTi linear pathway {rate}")
        ax.fill_between(yrs, path / 1000, path[0] / 1000 * 1.05, color=P[3], alpha=0.06)
        ax.plot(actual.index, actual / 1000, color=P[0], marker="o", lw=2.2, label="Actual")
        ax.plot([actual.index[-1], 2030], [actual.iloc[-1] / 1000, proj[k] / 1000], color=P[0], ls=":", lw=1.8, label="Linear trend projection")
        ax.scatter(2030, path[-1] / 1000, marker="*", s=200, color=P[5], zorder=5)
        ax.annotate(f"2030 target {path[-1]/1000:.1f}k\nprojection {proj[k]/1000:.1f}k", (2030, path[-1] / 1000), xytext=(-150, 40),
                    textcoords="offset points", fontsize=9, arrowprops=dict(arrowstyle="-", color="#999"))
        ax.set_title(f"{'Scope 1+2 (market-based)' if k == 'S1+2' else 'Scope 3'}"); ax.set_ylabel("kt CO2e"); ax.legend(fontsize=8.5, loc="lower left")
    fig.suptitle("Science-based target tracking (base year 2022, near-term 2030)", x=0.01, ha="left", fontweight="semibold")
    style.footnote(fig, NOTE); fig.tight_layout(); fig.savefig(FIG / "05_sbti_tracking.png"); plt.close(fig)


def fig_lmdi(lm):
    keys = ["Activity", "Structure", "Energy intensity", "Carbon factor"]
    fig, ax = plt.subplots(figsize=(10, 5))
    start = 0.0; xs = ["2022"] + keys + ["2025"]
    ax.bar(0, 0, color="white")
    cum = 0
    for i, k in enumerate(keys, start=1):
        v = lm[k] / 1000
        ax.bar(i, v, bottom=cum if v > 0 else cum + v, color=P[3] if v > 0 else P[5], width=0.6)
        ax.text(i, cum + max(v, 0) + 0.15, f"{v:+.2f}k", ha="center", fontweight="semibold")
        cum += v
    ax.bar(len(keys) + 1, cum, color=P[0] if cum < 0 else P[3], width=0.6)
    ax.text(len(keys) + 1, max(cum, 0) + 0.15, f"net {cum:+.2f}k", ha="center", fontweight="semibold")
    ax.axhline(0, color="#222", lw=1)
    ax.set_xticks(range(len(xs))); ax.set_xticklabels(["", *keys, "Net change"]); ax.set_xlim(0.4, len(keys) + 1.6)
    ax.set_ylabel("Change in kt CO2e, 2022 to 2025")
    ax.set_title("LMDI decomposition (location-based): efficiency offsets growth, but electrification on fossil grids raises carbon per GJ\n(additive LMDI-I, exact with no residual)")
    style.footnote(fig, NOTE); fig.savefig(FIG / "06_lmdi_waterfall.png"); plt.close(fig)


def fig_uncertainty(mc, y, s1, s2):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [1.3, 1]})
    axes[0].hist(mc / 1000, bins=60, color=P[2], alpha=0.85)
    for q, ls in [(5, ":"), (50, "-"), (95, ":")]:
        v = np.percentile(mc, q) / 1000; axes[0].axvline(v, color="#222", ls=ls); axes[0].text(v, axes[0].get_ylim()[1] * 0.92, f" P{q}\n {v:.1f}k", fontsize=8.5)
    axes[0].set_xlabel("Scope 3 2025 (kt CO2e)"); axes[0].set_title("Scope 3 Monte Carlo (10,000 runs; spread set by data quality)")
    sc = {"Scope 1": (y.loc[2025, "Scope 1"], 0.05), "Scope 2 (market)": (y.loc[2025, "Scope 2 (market)"], 0.07),
          "Scope 3": (np.median(mc), None)}
    names = list(sc); vals = [sc[k][0] / 1000 for k in names]
    lo = [vals[0] * 0.05 * 1.96, vals[1] * 0.07 * 1.96, (np.median(mc) - np.percentile(mc, 2.5)) / 1000]
    hi = [vals[0] * 0.05 * 1.96, vals[1] * 0.07 * 1.96, (np.percentile(mc, 97.5) - np.median(mc)) / 1000]
    axes[1].barh(names, vals, xerr=[lo, hi], color=[P[0], P[1], P[2]], capsize=5)
    for i, (v, l, h) in enumerate(zip(vals, lo, hi)):
        axes[1].text(v + h + 1, i, f"±{100*(l+h)/2/v:.0f}%", va="center", fontsize=9)
    axes[1].set_xlabel("kt CO2e (95% interval)"); axes[1].set_title("Uncertainty by scope, 2025"); axes[1].invert_yaxis()
    style.footnote(fig, NOTE); fig.tight_layout(); fig.savefig(FIG / "07_uncertainty.png"); plt.close(fig)


def fig_intensity(y):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.3))
    for ax, k, c, unit in [(axes[0], "S1+2 intensity (t/t fabric)", P[0], "t CO2e per t fabric"), (axes[1], "Total intensity (t/$M)", P[4], "t CO2e per $M revenue")]:
        ax.plot(y.index, y[k], marker="o", color=c, lw=2.4)
        for xx, v in zip(y.index, y[k]): ax.text(xx, v, f"  {v:.2f}" if v < 10 else f"  {v:.0f}", fontsize=9, va="bottom")
        ch = 100 * (y[k].iloc[-1] / y[k].iloc[0] - 1)
        ax.set_title(f"{unit}: {ch:+.1f}% since 2022"); ax.set_xticks(y.index)
    fig.suptitle("Intensity metrics: physical and economic", x=0.01, ha="left", fontweight="semibold")
    style.footnote(fig, NOTE); fig.tight_layout(); fig.savefig(FIG / "08_intensity.png"); plt.close(fig)


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
