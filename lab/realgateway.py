"""Recording pass-through gateway for testing on a real LLM provider.

The agent is pointed at this gateway exactly as it is pointed at the
simulator; the gateway forwards each /chat/completions call to a real
OpenAI-compatible provider and records the REAL response usage in the same
ledger format, billed at pinned list prices. The simulated controller is never
involved, so what you measure is the actual model on the actual agent.

The provider key travels with the agent's own request (harbour.llm adds
``Authorization: Bearer`` from ``LLM_API_KEY``), so no extra credential is
needed here. X-Harbour-* headers are read for attribution and stripped before
forwarding.

Run with lab.worker --real-url https://api.openai.com/v1 (see worker.py).
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from memsolver import pricing

_HEADERS_TO_DROP = ("x-harbour-case-id", "x-harbour-difficulty", "x-harbour-family")


class RealGateway:
    """A stateless, recording reverse proxy that also keeps per-case totals."""

    def __init__(self, real_base_url: str, ledger_path: str | Path) -> None:
        self.real_base = real_base_url.rstrip("/")
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._totals: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    def totals_for(self, case_id: str) -> dict[str, float]:
        with self._lock:
            return dict(self._totals.get(case_id, {"input_tokens": 0, "output_tokens": 0,
                                                   "cost_usd": 0.0, "latency_ms": 0.0,
                                                   "calls": 0}))

    # -- forwarding ----------------------------------------------------------

    def forward(self, body: dict, headers: dict) -> tuple[int, dict]:
        model = body.get("model", "")
        case_id = (headers.get("X-Harbour-Case-Id")
                   or headers.get("x-harbour-case-id") or "anonymous")
        forward_headers = {k: v for k, v in headers.items()
                           if k.lower() not in _HEADERS_TO_DROP
                           and k.lower() not in ("content-length", "host")}
        payload = json.dumps(body).encode("utf-8")
        started = time.time()
        try:
            req = urllib.request.Request(
                f"{self.real_base}/chat/completions", data=payload,
                headers=forward_headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8", "replace") or "{}")
        except (urllib.error.URLError, TimeoutError) as exc:
            return 502, {"error": {"message": str(exc)}}

        latency_ms = (time.time() - started) * 1000.0
        usage = raw.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        cost = pricing.real_cost(model, input_tokens, output_tokens)
        row = {
            "case_id": case_id,
            "model": model,
            "tier": pricing.real_tier(model),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_input_tokens": 0,
            "cost_usd": cost,
            "stage": "generate",
            "attempt": 0,
            "step": 0,
            "cache_hit": False,
            "latency_ms": round(latency_ms, 1),
        }
        with self._lock:
            with self.ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            acc = self._totals.setdefault(case_id, {"input_tokens": 0, "output_tokens": 0,
                                                    "cost_usd": 0.0, "latency_ms": 0.0,
                                                    "calls": 0})
            acc["input_tokens"] += input_tokens
            acc["output_tokens"] += output_tokens
            acc["cost_usd"] += cost
            acc["latency_ms"] += latency_ms
            acc["calls"] += 1
        return 200, raw


class _Handler(BaseHTTPRequestHandler):
    gateway: RealGateway = None

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path in ("/healthz", "/readyz"):
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ValueError:
            self._send(400, {"error": "invalid JSON body"})
            return
        code, reply = self.gateway.forward(body, {k: v for k, v in self.headers.items()})
        self._send(code, reply)

    def log_message(self, *args: Any) -> None:
        pass


def make_server(gateway: RealGateway, host: str = "127.0.0.1",
                port: int = 0) -> ThreadingHTTPServer:
    handler = type("RealGatewayHandler", (_Handler,), {"gateway": gateway})
    return ThreadingHTTPServer((host, port), handler)
