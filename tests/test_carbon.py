import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import carbon as cb  # noqa: E402


class TestCarbon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = cb.generate()

    def test_fuel_and_refrigerant_maths(self):
        act = pd.DataFrame([dict(year=2022, site="X", natural_gas_m3=1000, diesel_L=100, lpg_L=0)])
        ref = pd.DataFrame([dict(year=2022, site="X", gas="R-410A", kg=2.0)])
        s1 = cb.scope1(act, ref).iloc[0]
        self.assertAlmostEqual(s1.natural_gas_m3, 2.02)
        self.assertAlmostEqual(s1.diesel_L, 0.268)
        self.assertAlmostEqual(s1.refrigerants, 2 * 2256 / 1000)

    def test_market_equals_zero_with_full_instruments(self):
        s2 = cb.scope2(self.d["activity"], self.d["instruments"].assign(re_share=1.0))
        self.assertTrue(np.allclose(s2.market_t, 0))

    def test_market_uses_residual_mix_without_instruments(self):
        s2 = cb.scope2(self.d["activity"], self.d["instruments"].assign(re_share=0.0))
        ratio = (s2.market_t / s2.location_t).xs("Chemnitz (DE)", level="site")
        self.assertTrue(np.allclose(ratio, 0.62 / 0.38))

    def test_sbti_linear_pathway(self):
        p = cb.sbti_pathway(100.0, [2022, 2030], 0.042)
        self.assertAlmostEqual(p[1], 100 * (1 - 0.336))

    def test_lmdi_is_exact(self):
        rng = np.random.default_rng(0)
        q0, q1 = 100.0, 130.0
        s0 = rng.dirichlet([2, 2, 2]); s1 = rng.dirichlet([2, 2, 2])
        i0, i1 = rng.uniform(5, 10, 3), rng.uniform(4, 9, 3)
        f0, f1 = rng.uniform(0.05, 0.08, 3), rng.uniform(0.04, 0.08, 3)
        e0, e1 = q0 * s0 * i0 * f0, q1 * s1 * i1 * f1
        r = cb.lmdi(e0, e1, q0, q1, s0, s1, i0, i1, f0, f1)
        self.assertAlmostEqual(sum(r[k] for k in ["Activity", "Structure", "Energy intensity", "Carbon factor"]), r["Total"], places=9)

    def test_scope3_mc_mean_preserving(self):
        s3 = self.d["scope3"][self.d["scope3"].year == 2025]
        mc = cb.monte_carlo_scope3(s3, n=40000)
        self.assertAlmostEqual(mc.mean() / s3.tco2e.sum(), 1.0, delta=0.01)

    def test_all_15_categories_screened(self):
        self.assertEqual(sorted(c for c, *_ in cb.SCOPE3), list(range(1, 16)))


if __name__ == "__main__":
    unittest.main()
