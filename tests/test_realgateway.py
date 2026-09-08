"""Unit tests for the recording pass-through gateway (lab/realgateway.py)."""

import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from lab.realgateway import RealGateway, make_server
from memsolver import pricing


class _FakeProvider(BaseHTTPRequestHandler):
    seen_headers = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode() or "{}")
        type(self).seen_headers.append(dict(self.headers))
        reply = {
            "id": "chatcmpl-fake",
            "model": body.get("model"),
            "choices": [{"message": {"role": "assistant",
                                     "content": '{"tool": "lookup_loan", '
                                                '"args": {"loan_id": "ln_001"}}'},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1200, "completion_tokens": 40,
                      "total_tokens": 1240},
        }
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


class TestRealGateway(unittest.TestCase):
    def setUp(self):
        self.provider = ThreadingHTTPServer(("127.0.0.1", 0), _FakeProvider)
        threading.Thread(target=self.provider.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "ledger.jsonl"

    def tearDown(self):
        self.provider.shutdown()
        self.tmp.cleanup()

    def _roundtrip(self):
        gw = RealGateway(f"http://127.0.0.1:{self.provider.server_address[1]}/v1",
                         self.ledger)
        server = make_server(gw)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
        body = json.dumps({"model": "gpt-4.1-mini-2025-04-14",
                           "messages": [{"role": "user", "content": "hi"}]}).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json",
                     "X-Harbour-Case-Id": "c_0001"},
            method="POST")
        resp = urllib.request.urlopen(req, timeout=10)
        server.shutdown()
        return json.loads(resp.read().decode())

    def test_forwards_and_records_real_usage(self):
        reply = self._roundtrip()
        self.assertEqual(reply["model"], "gpt-4.1-mini-2025-04-14")
        rows = [json.loads(l) for l in self.ledger.read_text().splitlines()]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["case_id"], "c_0001")
        self.assertEqual(row["input_tokens"], 1200)
        self.assertEqual(row["output_tokens"], 40)
        self.assertEqual(row["tier"], "mini")
        self.assertEqual(row["cost_usd"],
                         pricing.real_cost("gpt-4.1-mini-2025-04-14", 1200, 40))
        # attribution header is read locally, not forwarded to the provider
        seen = _FakeProvider.seen_headers[-1]
        self.assertNotIn("X-Harbour-Case-Id", seen)
        self.assertNotIn("x-harbour-case-id", {k.lower(): v for k, v in seen.items()})


if __name__ == "__main__":
    unittest.main()
