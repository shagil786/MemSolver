import unittest
from memsolver import simconfig


class TestSimconfig(unittest.TestCase):
    def test_profiles_exist_for_all_models_and_difficulties(self):
        for model in ("nano", "mini", "strong"):
            for diff in simconfig.DIFFICULTIES:
                prof = simconfig.profile(model, diff)
                self.assertIn("p_correct", prof)
                self.assertIn("out_tokens", prof)
                self.assertIn("latency_ms", prof)

    def test_capability_ordering(self):
        # For every difficulty, strong >= mini >= nano on plan correctness.
        for diff in simconfig.DIFFICULTIES:
            p_nano = simconfig.profile("nano", diff)["p_correct"]
            p_mini = simconfig.profile("mini", diff)["p_correct"]
            p_strong = simconfig.profile("strong", diff)["p_correct"]
            self.assertLessEqual(p_nano, p_mini)
            self.assertLessEqual(p_mini, p_strong)

    def test_difficulty_ordering(self):
        # For every model, easy >= medium >= hard on plan correctness.
        for model in ("nano", "mini", "strong"):
            pe = simconfig.profile(model, "easy")["p_correct"]
            pm = simconfig.profile(model, "medium")["p_correct"]
            ph = simconfig.profile(model, "hard")["p_correct"]
            self.assertGreaterEqual(pe, pm)
            self.assertGreaterEqual(pm, ph)

    def test_legacy_alias_resolves(self):
        self.assertEqual(simconfig.profile("small", "easy"), simconfig.profile("nano", "easy"))

    def test_unknown_difficulty_raises(self):
        with self.assertRaises(ValueError):
            simconfig.profile("mini", "trivial")


if __name__ == "__main__":
    unittest.main()
