# Corporate GHG inventory and SBTi target tracking (GHG Protocol)

> **Model case study.** "Indus Weave Ltd" is a hypothetical 3-site textile manufacturer with simulated activity data. Emission factors are rounded representative values (DEFRA/DESNZ-style fuel factors, IPCC AR6 GWPs, typical grid and residual-mix factors), not an official factor set.

## Scope and methods
| Element | Method |
|---|---|
| Boundary | Operational control; 3 sites (Pakistan, Türkiye, Germany); 2022 (base year) to 2025; monthly activity data |
| Scope 1 | Stationary and mobile combustion (natural gas, diesel, LPG). Refrigerant leakage by mass balance with AR6 GWPs (R-410A 2256, R-134a 1530, R-32 771) |
| Scope 2 | **Dual reporting**. Location-based uses the grid average. Market-based applies PPA/REC instruments at zero and residual-mix factors to the rest |
| Scope 3 | All 15 categories screened, each with a calculation method, a relevance decision and a 1–5 data-quality score |
| Targets | SBTi near-term linear contraction: Scope 1+2 at 4.2%/yr (1.5°C); Scope 3 at 2.5%/yr (well-below 2°C) |
| Decomposition | Additive LMDI-I (activity, site structure, energy intensity, carbon factor). Exact, with no residual |
| Uncertainty | Monte Carlo on Scope 3; the lognormal spread for each category comes from its data-quality score, with mean preserved |

## Key results (model case study)
| Metric | 2022 | 2025 | Change |
|---|---|---|---|
| Scope 1 (t CO2e) | 17,391 | 14,985 | −13.8% |
| Scope 2 market-based | 18,071 | 12,485 | −30.9% |
| Scope 2 location-based | 16,412 | 18,884 | +15.1% |
| Scope 3 | 96,285 | 99,076 | +2.9% |
| Total (market-based) | 131,747 | 126,547 | −3.9% |
| S1+2 intensity (t per t fabric) | 1.31 | 0.91 | −30.4% |
| Total intensity (t per $M) | 724 | 573 | −20.9% |

**Findings**
- Scope 3 is 78% of the footprint. Category 1 (purchased goods) alone is 61% of Scope 3. The top 7 categories reach about 95% coverage.
- **Scope 1+2 is ahead of its SBTi pathway** (11% below it in 2025; the trend projects 14.2 kt against a 2030 target of 23.5 kt). **Scope 3 is off-track** (11% above its pathway; the trend projects 103.9 kt against a 77.0 kt target). Supplier engagement on Category 1 is the priority.
- Market-based and location-based Scope 2 diverge. Electrification raised location-based emissions, while contractual renewables cut market-based emissions. In Chemnitz in 2022, the market-based figure exceeds the location-based one because the residual mix is dirtier than the grid average.
- LMDI, 2022→2025: production growth adds 3.6 kt, efficiency removes 5.4 kt, and a higher carbon factor (electricity replacing gas on fossil grids) adds 1.8 kt. The net change is +0.02 kt.
- The Scope 3 95% interval is 76.7–127.1 kt. Its uncertainty (about ±25%) dwarfs that of Scopes 1 and 2.

## Figures (`outputs/figures/`)
1. Inventory overview (market-based, with the location-based total marked)
2. Scope 3 Pareto with data-quality colouring
3. Scope 2 dual reporting by site
4. Monthly emissions heatmap
5. SBTi trajectories and projections
6. LMDI waterfall
7. Uncertainty by scope
8. Intensity metrics

Tables 1–6 cover the inventory, Scope 1 sources, Scope 2 dual reporting, Scope 3 screening, SBTi tracking and LMDI. Activity data are in `data/activity_monthly.csv`.

## Validation
Seven tests check:
- the factor arithmetic;
- that market-based Scope 2 is zero with 100% instruments and equals the residual-mix ratio with none;
- the SBTi pathway maths;
- that LMDI is exact;
- that the Monte Carlo preserves the mean;
- that all 15 categories are screened.

```bash
python src/analyze.py && python -m pytest tests
```

## Links
- Kaggle notebook: https://www.kaggle.com/rabbani0123 (runnable copy of `notebook.ipynb`)
- Author: Mohammad Rabbani | Sustainability Data Analyst & Research Assistant

## License
MIT
