import json
import tempfile
import unittest
from pathlib import Path

from memsolver.telemetry import ModelCallRecord, RequestTelemetry, write_jsonl, read_jsonl


class TestTelemetry(unittest.TestCase):

    def test_model_call_to_dict(self):
        call = ModelCallRecord(tier="small", input_tokens=100, output_tokens=200,
                               latency_ms=500, cost=0.00012, purpose="gen")
        d = call.to_dict()
        self.assertEqual(d["tier"], "small")
        self.assertEqual(d["output_tokens"], 200)
        self.assertEqual(d["cost"], 0.00012)
        self.assertEqual(d["purpose"], "gen")

    def test_request_telemetry_json_roundtrip(self):
        t = RequestTelemetry(
            request_id="req-1", case_id="c-1", route="cheap", model="m1",
            model_calls=3, input_tokens=44, output_tokens=13, retries=1,
            retry_reasons=["transient"], escalations=0, cache_hit=False, success=True,
            latency_ms=100.0, cost=0.25,
            calls=[ModelCallRecord(tier="small", input_tokens=50, output_tokens=12,
                                   latency_ms=50, cost=0.25, purpose="gen")],
        )
        loaded = json.loads(json.dumps(t.to_dict()))
        self.assertEqual(loaded["request_id"], "req-1")
        self.assertEqual(loaded["case_id"], "c-1")
        self.assertEqual(loaded["model_calls"], 3)
        self.assertEqual(loaded["calls"][0]["purpose"], "gen")

    def test_jsonl_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub" / "t.jsonl"
            recs = [
                RequestTelemetry(request_id="r1", case_id="c1", route="r", model="small",
                                 model_calls=27, input_tokens=36, output_tokens=31, retries=0,
                                 retry_reasons=[], escalations=743, cache_hit=False, success=True,
                                 latency_ms=99.9, cost=0.414,
                                 calls=[ModelCallRecord(tier="small", input_tokens=77, output_tokens=23,
                                       latency_ms=51, cost=0.49, purpose="gen")]),
                RequestTelemetry(request_id="r2", case_id="c2", route="r2", model="standard",
                                 model_calls=348, input_tokens=539, output_tokens=451, retries=9,
                                 retry_reasons=["malformed"], escalations=572, cache_hit=False,
                                 success=False, latency_ms=561.2, cost=1.6,
                                 calls=[]),
            ]
            write_jsonl(p, recs)
            out = read_jsonl(p)
            self.assertEqual(len(out), 2)
            self.assertEqual(out[0]["request_id"], "r1")
            self.assertEqual(out[0]["model_calls"], 27)
            self.assertIn("malformed", out[1]["retry_reasons"])


if __name__ == "__main__":
    unittest.main()
