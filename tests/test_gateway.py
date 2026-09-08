"""Unit tests for the simulated gateway (lab/gateway.py)."""

import json
import tempfile
import unittest
from pathlib import Path

from lab.gateway import SimGateway
from memsolver import pricing

CASES = Path(__file__).resolve().parent.parent / "vendor" / "challenge" / "cases.jsonl"


def _msg_for(case_id: str) -> tuple[str, list[dict]]:
    for line in CASES.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["case_id"] == case_id:
            return case_id, [
                {"role": "system", "content": "You are Harbour."},
                {"role": "user", "content": f"Case {case_id}. Customer {row['customer_id']}."
                                            f" Loan {row.get('loan_id')}.\n"
                                            f"Customer message:\n{row['message']}"},
            ]
    raise KeyError(case_id)


class TestGateway(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _gw(self, cache=True):
        return SimGateway(CASES, self.ledger, "test-seed", cache=cache)

    def test_completion_shape_and_ledger(self):
        gw = self._gw()
        case_id, msgs = _msg_for("c_0001")
        reply = gw.complete("mini", msgs, 800, case_id)
        # OpenAI wire shape that harbour.llm._normalise expects
        self.assertIn("choices", reply)
        self.assertIn("usage", reply)
        self.assertGreater(reply["usage"]["prompt_tokens"], 0)
        self.assertIn("content", reply["choices"][0]["message"])
        # content is a parseable action object
        action = json.loads(reply["choices"][0]["message"]["content"])
        self.assertIn("tool", action)

        rows = [json.loads(l) for l in self.ledger.read_text().splitlines()]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["case_id"], case_id)
        self.assertEqual(row["model"], "mini")
        expected = pricing.cost_for("mini", row["input_tokens"], row["output_tokens"])
        self.assertAlmostEqual(row["cost_usd"], expected, places=9)
        self.assertFalse(row["cache_hit"])

    def test_deterministic(self):
        gw = self._gw()
        case_id, msgs = _msg_for("c_0001")
        r1 = gw.complete("mini", msgs, 800, case_id)
        gw2 = self._gw()
        r2 = gw2.complete("mini", msgs, 800, case_id)
        self.assertEqual(r1["choices"][0]["message"]["content"],
                         r2["choices"][0]["message"]["content"])

    def test_cache_hit_is_free(self):
        gw = self._gw(cache=True)
        case_id, msgs = _msg_for("c_0001")
        gw.complete("mini", msgs, 800, case_id)
        gw.complete("mini", msgs, 800, case_id)  # identical request -> cache hit
        rows = [json.loads(l) for l in self.ledger.read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1]["cache_hit"])
        self.assertEqual(rows[1]["cost_usd"], 0.0)
        self.assertGreater(rows[0]["cost_usd"], 0.0)

    def test_unknown_model_rejected(self):
        gw = self._gw()
        case_id, msgs = _msg_for("c_0001")
        with self.assertRaises(ValueError):
            gw.complete("gpt-5", msgs, 800, case_id)


if __name__ == "__main__":
    unittest.main()


class TestPrefixCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _gw(self):
        return SimGateway(CASES, self.ledger, "test-seed", cache=False, prefix_cache=True)

    def test_growing_conversation_bills_only_new_suffix(self):
        gw = self._gw()
        case_id, msgs = _msg_for("c_0001")
        gw.complete("mini", msgs, 800, case_id)
        grown = msgs + [
            {"role": "assistant", "content": '{"tool": "verify_identity", "args": {}}'},
            {"role": "user", "content": "Result of verify_identity: true"},
        ]
        gw.complete("mini", grown, 800, case_id)
        rows = [json.loads(l) for l in self.ledger.read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        r2 = rows[1]
        self.assertGreater(r2["cached_input_tokens"], 0)
        # billed input tokens are what we pay for (total minus cached prefix)
        total = max(1, sum(len(str(m.get("content") or "")) for m in grown) // 4)
        self.assertEqual(r2["input_tokens"], total - r2["cached_input_tokens"])
        expected = pricing.cost_for("mini", r2["input_tokens"], r2["output_tokens"])
        self.assertAlmostEqual(r2["cost_usd"], expected, places=9)


class TestVerifyBranch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_marker_returns_verify_decision_deterministically(self):
        gw = SimGateway(CASES, self.ledger, "test-seed", cache=False)
        case_id, msgs = _msg_for("c_0001")
        msgs = msgs + [{"role": "user", "content":
                        "[HARBOUR_VERIFY gen=mini] Reply {\"verify\": \"ok\"} or "
                        "{\"verify\": \"redo\"}."}]
        r1 = gw.complete("strong", msgs, 80, case_id)
        gw2 = SimGateway(CASES, Path(self.tmp.name) / "ledger2.jsonl", "test-seed",
                         cache=False)
        r2 = gw2.complete("strong", msgs, 80, case_id)
        c1 = json.loads(r1["choices"][0]["message"]["content"])
        c2 = json.loads(r2["choices"][0]["message"]["content"])
        self.assertIn(c1["verify"], ("ok", "redo"))
        self.assertEqual(c1, c2)
        rows = [json.loads(l) for l in self.ledger.read_text().splitlines()]
        self.assertEqual(rows[0]["stage"], "verify")
