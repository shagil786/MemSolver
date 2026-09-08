"""Pinned list prices for the lab's budget-class model tiers.

OP-03 only allows budget-class models: small hosted models in a provider's
mini/nano/Flash/Haiku tier, or open-weight models up to about 35B parameters.
The old small/standard/large table (up to $15/$75) is NOT budget class and is
gone. The three tiers below are placeholders for concrete budget models; the
prices are what the simulated gateway charges, so the ledger numbers are
computed at pinned list prices exactly like the real pipeline.

    nano    ≈ cheap open-weight (~4-8B) or nano tier     $0.10 / $0.40 per 1M
    mini    = gpt-4.1-mini-2025-04-14 (the pinned Harbour  $0.40 / $1.60 per 1M
              reference model, from MODELS.md)
    strong  ≈ top-of-budget open-weight (~32B) or flash  $1.50 / $6.00 per 1M

"small" / "standard" / "large" remain as aliases so the legacy reference
simulator keeps working; they resolve to nano / mini / strong.
"""

from __future__ import annotations

# USD per 1M uncached tokens (input, output), pinned.
PRICES_PER_1M: dict[str, dict[str, float]] = {
    "nano": {"input": 0.10, "output": 0.40},
    "mini": {"input": 0.40, "output": 1.60},
    "strong": {"input": 1.50, "output": 6.00},
}

TIERS: tuple[str, ...] = ("nano", "mini", "strong")

# Legacy reference-simulator aliases -> canonical budget tiers.
ALIASES: dict[str, str] = {
    "small": "nano",
    "standard": "mini",
    "large": "strong",
}


def resolve(model_or_alias: str) -> str:
    """Map an alias or canonical tier name to a canonical tier."""
    if model_or_alias in PRICES_PER_1M:
        return model_or_alias
    if model_or_alias in ALIASES:
        return ALIASES[model_or_alias]
    raise ValueError(
        f"Unknown tier/model: {model_or_alias!r}. Known: "
        f"{list(PRICES_PER_1M)} (aliases: {ALIASES})"
    )


# Real provider model ids the recording gateway can bill at pinned list prices
# (prices from the challenge's MODELS.md / public list prices).
REAL_MODELS: dict[str, dict] = {
    "gpt-4.1-mini-2025-04-14": {"input": 0.40, "output": 1.60, "tier": "mini"},
    "gpt-4.1-nano-2025-04-14": {"input": 0.10, "output": 0.40, "tier": "nano"},
    "gpt-5-mini-2025-08-07":   {"input": 0.25, "output": 2.00, "tier": "mini"},
}


def real_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Ledger cost for a real provider model at pinned list prices."""
    info = REAL_MODELS.get(model_id, {"input": 0.50, "output": 1.50, "tier": "mini"})
    cost = (input_tokens / 1_000_000.0) * info["input"] + (output_tokens / 1_000_000.0) * info["output"]
    return round(cost, 9)


def real_tier(model_id: str) -> str:
    return REAL_MODELS.get(model_id, {}).get("tier", "mini")


def cost_for(tier: str, input_tokens: int, output_tokens: int) -> float:
    """Exact cost at pinned list prices = in/1M*in_price + out/1M*out_price."""
    model = resolve(tier)
    prices = PRICES_PER_1M[model]
    cost = (
        (input_tokens / 1_000_000.0) * prices["input"]
        + (output_tokens / 1_000_000.0) * prices["output"]
    )
    return round(cost, 9)
