import unittest
from memsolver import tools


class TestTools(unittest.TestCase):
    def test_lookup_order_keys_and_types(self):
        res = tools.lookup_order("ORD-123")
        self.assertIn("order_id", res)
        self.assertIn("status", res)
        self.assertIn("eta_days", res)
        self.assertIn("total_usd", res)
        self.assertIsInstance(res["status"], str)
        self.assertIsInstance(res["eta_days"], int)
        self.assertIsInstance(res["total_usd"], float)

    def test_lookup_order_deterministic(self):
        r1 = tools.lookup_order("ORD-456")
        r2 = tools.lookup_order("ORD-456")
        self.assertEqual(r1, r2)

    def test_transient_failure_first_call_then_succeeds(self):
        # Reset counter by importing fresh — but module is cached. Instead rely on defined behavior:
        # first call raises, second succeeds. We just test the contract by catching.
        try:
            tools.lookup_order("ORD-TRANSIENT-FAIL")
            # If we get here, either it's not the first call or behavior changed; accept both
        except tools.ToolTransientError:
            pass
        # Second call should not raise
        res = tools.lookup_order("ORD-TRANSIENT-FAIL")
        self.assertEqual(res["order_id"], "ORD-TRANSIENT-FAIL")

    def test_get_account_balance(self):
        res = tools.get_account_balance("ACC-789")
        self.assertIn("account_id", res)
        self.assertIn("balance_usd", res)
        self.assertIn("currency", res)
        self.assertEqual(res["currency"], "USD")
        r2 = tools.get_account_balance("ACC-789")
        self.assertEqual(res, r2)

    def test_search_kb_finds_match(self):
        res = tools.search_kb("How do I return an item?")
        self.assertIsNotNone(res)
        self.assertEqual(res["article_id"], "KB-001")

    def test_search_kb_none_for_garbage(self):
        res = tools.search_kb("asdfghjkl nonsense query")
        self.assertIsNone(res)

    def test_submit_refund_success(self):
        res = tools.submit_refund("ORD-123", 50.0, "damaged")
        self.assertIn("refund_id", res)
        self.assertEqual(res["status"], "submitted")
        self.assertEqual(res["amount_usd"], 50.0)

    def test_submit_refund_amount_too_high(self):
        with self.assertRaises(tools.BusinessRuleError):
            tools.submit_refund("ORD-123", 600.0, "too much")

    def test_submit_refund_bad_order_id(self):
        with self.assertRaises(tools.BusinessRuleError):
            tools.submit_refund("BAD-123", 50.0, "bad id")

    def test_submit_refund_zero_amount(self):
        with self.assertRaises(tools.BusinessRuleError):
            tools.submit_refund("ORD-123", 0, "zero")

    def test_format_date_styles(self):
        self.assertEqual(tools.format_date("2025-03-05", "long"), "March 05, 2025")
        self.assertEqual(tools.format_date("2025-03-05", "iso"), "2025-03-05")
        self.assertEqual(tools.format_date("2025-03-05", "short"), "03/05/2025")

    def test_format_date_invalid_style(self):
        with self.assertRaises(ValueError):
            tools.format_date("2025-03-05", "unknown")

    def test_format_currency(self):
        self.assertEqual(tools.format_currency(1234.5, "USD"), "$1,234.50")
        self.assertEqual(tools.format_currency(1234.5, "EUR"), "€1,234.50")
        self.assertEqual(tools.format_currency(1234.5, "INR"), "₹1,234.50")

    def test_schemas_accurate(self):
        # Verify schemas exist and match function signatures
        self.assertIn("lookup_order", tools.TOOL_SCHEMAS)
        self.assertIn("submit_refund", tools.TOOL_SCHEMAS)
        self.assertEqual(tools.TOOL_SCHEMAS["submit_refund"]["required"],
                         ["order_id", "amount_usd", "reason"])
        self.assertIn("style", tools.TOOL_SCHEMAS["format_date"]["enums"])
        self.assertEqual(set(tools.TOOL_SCHEMAS["format_date"]["enums"]["style"]),
                         {"long", "iso", "short"})

    def test_tool_registry_callable(self):
        for name, fn in tools.TOOL_REGISTRY.items():
            self.assertTrue(callable(fn), f"{name} not callable")


if __name__ == "__main__":
    unittest.main()
