"""OP-03 lab gateway: a simulated budget-model provider behind LLM_BASE_URL.

Speaks just enough of the OpenAI chat-completions wire format for
``harbour.llm`` to talk to it, and is the *only* cost measurement in the lab:
every completion lands one line in the ledger at pinned list prices, exactly
like the graded gateway ledger. ``harbour.llm`` never sees its own spend.

Behaviour is a deterministic pure function of the request: which model handles
the case (``model``), what the transcript says (``messages``), and which case
it is (``X-Harbour-Case-Id`` header).  Case difficulty/family come from the
published case file so the simulated capability can depend on difficulty
without the model "seeing" the label.

Run:
    python -m lab.gateway --cases vendor/challenge/cases.jsonl \\
        --ledger results/<run>/ledger.jsonl --seed op03-lab-v1 --port 8123
Prints one JSON line ``{"port": N}`` when ready.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memsolver import pricing, simconfig
from lab import plans


def _usage_tokens(messages: list[dict]) -> int:
    chars = sum(len(str(m.get("content") or "")) for m in messages)
    return max(1, chars // 4)


def _content_tokens(content: str) -> int:
    return max(1, len(content) // 4)


class SimGateway:
    """Stateful-but-deterministic provider front end for the controller."""

    def __init__(self, cases_path: str | Path, ledger_path: str | Path,
                 world_seed: str, cache: bool = True) -> None:
        self.world_seed = world_seed
        self.cache_enabled = cache
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._cases: dict[str, dict] = {}
        if cases_path:
            for line in Path(cases_path).read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    self._cases[row["case_id"]] = row
        self._cache: dict[tuple[str, str, int], dict] = {}
        self._totals: dict[str, dict[str, float]] = {}
        # RLock: complete() holds the lock while _ledger_row() takes it again.
        self._lock = threading.RLock()

    def totals_for(self, case_id: str) -> dict[str, float]:
        """In-memory ledger totals per case (input/output tokens, cost, latency)."""
        with self._lock:
            return dict(self._totals.get(case_id, {"input_tokens": 0, "output_tokens": 0,
                                                   "cost_usd": 0.0, "latency_ms": 0.0,
                                                   "calls": 0}))

    # -- case context -------------------------------------------------------

    def ctx_for(self, case_id: str, messages: list[dict]) -> plans.CaseCtx:
        row = self._cases.get(case_id)
        if row is None:
            # graceful default so the gateway is usable without a case file
            first = ""
            for m in messages:
                if m.get("role") == "user":
                    first = str(m.get("content") or "")
                    break
            return plans.CaseCtx(case_id, "cu_0001", None, "fee_waiver", "easy", first)
        return plans.CaseCtx(
            case_id=row["case_id"],
            customer_id=row["customer_id"],
            loan_id=row.get("loan_id"),
            family=row["family"],
            difficulty=row["difficulty"],
            message=row["message"],
        )

    # -- completion ---------------------------------------------------------

    def complete(self, model: str, messages: list[dict], max_tokens: int,
                 case_id: str) -> dict:
        model = pricing.resolve(model)  # aliases/unknowns raise -> 400 upstream
        ctx = self.ctx_for(case_id, messages)
        override = os.environ.get("LLM_LAB_P_OVERRIDE")
        if override:
            p_correct = float(override)
        else:
            base = simconfig.profile(model, ctx.difficulty)["p_correct"]
            scale = float(os.environ.get(f"LLM_LAB_P_SCALE_{model.upper()}")
                          or os.environ.get("LLM_LAB_P_SCALE")
                          or str(simconfig.P_SCALE.get(model, 1.0)))
            p_correct = min(0.999, base * scale)
        attempt = plans._attempt_index(messages)
        step = len(plans._assistant_tools(messages))

        key = (model, json.dumps(messages, sort_keys=True), int(max_tokens))
        with self._lock:
            if self.cache_enabled and key in self._cache:
                cached = self._cache[key]
                row = self._ledger_row(case_id, model, messages, cached["content"],
                                       cached["output_tokens"], latency_ms=5,
                                       cache_hit=True, step=step, attempt=attempt)
                return self._openai_reply(model, cached["content"], row)

            action = plans.next_action(messages, ctx, model, self.world_seed, p_correct)
            content = json.dumps(action)
            output_tokens = min(_content_tokens(content), int(max_tokens))

            latency_ms = self._latency(model, ctx, attempt, step)
            row = self._ledger_row(case_id, model, messages, content, output_tokens,
                                   latency_ms=latency_ms, cache_hit=False,
                                   step=step, attempt=attempt)
            if self.cache_enabled:
                self._cache[key] = {"content": content, "output_tokens": output_tokens}
            return self._openai_reply(model, content, row)

    # -- pieces -------------------------------------------------------------

    def _latency(self, model: str, ctx: plans.CaseCtx, attempt: int, step: int) -> int:
        prof = simconfig.profile(model, ctx.difficulty)
        lo, hi = prof["latency_ms"]
        r = plans._hash01(ctx.case_id, model, str(attempt), str(step), "lat", self.world_seed)
        return int(lo + r * (hi - lo))

    def _ledger_row(self, case_id: str, model: str, messages: list[dict],
                    content: str, output_tokens: int, latency_ms: int,
                    cache_hit: bool, step: int, attempt: int) -> dict:
        input_tokens = _usage_tokens(messages)
        # A self-hosted cache is free (OP-03): a cache hit bills nothing.
        cost = 0.0 if cache_hit else pricing.cost_for(model, input_tokens, output_tokens)
        row = {
            "case_id": case_id,
            "model": model,
            "tier": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "stage": "generate",
            "attempt": attempt,
            "step": step,
            "cache_hit": bool(cache_hit),
            "latency_ms": latency_ms,
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
        return row

    @staticmethod
    def _openai_reply(model: str, content: str, row: dict) -> dict:
        return {
            "model": model,
            "choices": [
                {
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": row["input_tokens"],
                "completion_tokens": row["output_tokens"],
                "total_tokens": row["input_tokens"] + row["output_tokens"],
            },
        }


class _Handler(BaseHTTPRequestHandler):
    gateway: SimGateway = None  # set by factory

    # -- helpers ------------------------------------------------------------

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    # -- routes -------------------------------------------------------------

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
            body = self._read_body()
        except ValueError:
            self._send(400, {"error": "invalid JSON body"})
            return
        model = body.get("model")
        messages = body.get("messages")
        max_tokens = int(body.get("max_completion_tokens") or body.get("max_tokens") or 800)
        if not isinstance(model, str) or not isinstance(messages, list):
            self._send(400, {"error": "model and messages are required"})
            return
        case_id = self.headers.get("X-Harbour-Case-Id") or "anonymous"
        try:
            reply = self.gateway.complete(model, messages, max_tokens, case_id)
        except ValueError as exc:
            traceback.print_exc()
            self._send(400, {"error": str(exc)})
            return
        self._send(200, reply)

    def log_message(self, *args: Any) -> None:  # silence request logging
        pass


def make_server(gateway: SimGateway, host: str = "127.0.0.1",
                port: int = 0) -> ThreadingHTTPServer:
    handler = type("GatewayHandler", (_Handler,), {"gateway": gateway})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", type=Path, default=None)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--seed", default="op03-lab-v1")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    gw = SimGateway(args.cases, args.ledger, args.seed, cache=not args.no_cache)
    server = make_server(gw, args.host, args.port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(json.dumps({"port": server.server_address[1]}), flush=True)
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
