import unittest
from memsolver import pricing


class TestPricing(unittest.TestCase):
    def test_nano_tier_cost(self):
        # Pinned: nano $0.10 input / $0.40 output per 1M
        self.assertEqual(pricing.cost_for("nano", 1_000_000, 0), 0.10)
        self.assertEqual(pricing.cost_for("nano", 0, 1_000_000), 0.40)
        self.assertEqual(pricing.cost_for("nano", 500_000, 500_000), 0.25)

    def test_mini_tier_cost(self):
        # Pinned: gpt-4.1-mini reference price $0.40 / $1.60 per 1M
        self.assertEqual(pricing.cost_for("mini", 1_000_000, 0), 0.40)
        self.assertEqual(pricing.cost_for("mini", 0, 1_000_000), 1.60)
        self.assertEqual(pricing.cost_for("mini", 500_000, 500_000), 1.00)

    def test_strong_tier_cost(self):
        # Pinned: strong budget $1.50 input / $6.00 output per 1M
        self.assertEqual(pricing.cost_for("strong", 1_000_000, 0), 1.50)
        self.assertEqual(pricing.cost_for("strong", 0, 1_000_000), 6.00)

    def test_legacy_aliases_resolve_to_budget_tiers(self):
        # The reference simulator's small/standard/large -> nano/mini/strong
        self.assertEqual(pricing.resolve("small"), "nano")
        self.assertEqual(pricing.resolve("standard"), "mini")
        self.assertEqual(pricing.resolve("large"), "strong")
        self.assertEqual(pricing.cost_for("small", 1_000_000, 0), 0.10)
        self.assertEqual(pricing.cost_for("large", 1_000_000, 0), 1.50)

    def test_all_tiers_are_budget_class(self):
        # OP-03 bar: no tier may exceed budget-class pricing.
        for model in pricing.TIERS:
            self.assertIn(model, pricing.PRICES_PER_1M)
            self.assertLessEqual(pricing.PRICES_PER_1M[model]["input"], 1.50)
            self.assertLessEqual(pricing.PRICES_PER_1M[model]["output"], 6.00)

    def test_unknown_tier_raises(self):
        with self.assertRaises(ValueError):
            pricing.cost_for("gpt-5", 100, 100)
        with self.assertRaises(ValueError):
            pricing.resolve("unknown")


if __name__ == "__main__":
    unittest.main()
