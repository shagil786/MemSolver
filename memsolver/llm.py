"""Simulated LLM with deterministic seeded RNG and a real-client stub."""

from __future__ import annotations
import json
import math
import random
import zlib
from dataclasses import dataclass
from typing import Protocol, Any

from memsolver import pricing
from memsolver import simconfig


@dataclass(frozen=True)
class ModelCall:
    tier: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost: float
    purpose: str


class ModelClient(Protocol):
    def complete(self, messages: list[dict], tier: str, max_tokens: int, rng: random.Random,
                 difficulty_hint: str, purpose: str) -> ModelCall: ...


class SimulatedLLM:
    """Deterministic simulated LLM for reproducible evaluation."""

    def count_input_tokens(self, messages: list[dict]) -> int:
        """Chars/4 heuristic on JSON-serialized messages."""
        total = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        return math.ceil(total / 4.0)

    def complete(self, messages: list[dict], tier: str, max_tokens: int, rng: random.Random,
                 difficulty_hint: str, purpose: str) -> ModelCall:
        prof = simconfig.profile(tier, difficulty_hint)
        input_tokens = self.count_input_tokens(messages)
        out_lo, out_hi = prof["out_tokens"]
        output_tokens = rng.randint(out_lo, out_hi)
        if output_tokens > max_tokens:
            output_tokens = max_tokens
        lat_lo, lat_hi = prof["latency_ms"]
        latency_ms = rng.randint(lat_lo, lat_hi)
        cost = pricing.cost_for(tier, input_tokens, output_tokens)
        return ModelCall(
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost=cost,
            purpose=purpose,
        )


class OpenAICompatClient:
    """
    Stub for a real OpenAI-compatible provider.
    To plug a real provider:
    - Set OPENAI_BASE_URL and OPENAI_API_KEY in environment
    - Use openai.OpenAI(base_url=..., api_key=...) or httpx to POST /chat/completions
    - Map response.usage.prompt_tokens -> input_tokens, response.usage.completion_tokens -> output_tokens
    - tier maps to model name (e.g. "gpt-4o-mini", "gpt-4o", "gpt-4.1")
    - cost via pricing.cost_for(tier, input_tokens, output_tokens)
    - latency = response.headers.get("x-response-time") or wall-clock
    - raise on HTTP errors or missing usage
    """
    def complete(self, *a, **kw) -> ModelCall:
        raise NotImplementedError(
            "OpenAICompatClient is a stub. Implement by calling a real provider "
            "and mapping usage/cost per the comments above."
        )


def seeded_rng(case_id: str, tier: str, attempt: int, purpose: str = "gen") -> random.Random:
    """Stable hash-derived RNG so identical (case_id, tier, attempt, purpose) -> identical draws."""
    # CRC32 gives 32 bits; fold with a fixed constant for domain separation
    key = f"{case_id}|{tier}|{attempt}|{purpose}".encode()
    seed = zlib.crc32(key) ^ 0x5EED
    return random.Random(seed)
