"""Simulator capability profiles per budget model and case difficulty.

These are the quality/latency/token tables the simulated gateway uses when it
decides how a given budget model handles a case of a given difficulty.

``p_correct`` is a provisional anchor for the probability that the model finds
and executes the correct plan *given a straightforward path*. Real goal success
also depends on escalation/identity handling and on recoverable tool errors, so
the true operating point is measured end to end by goal_scorer.py in the lab
(M3 calibration): the single "mini" model should land near the published
reference ballpark (~0.62-0.66 exact goal success on the case mix). Treat these
numbers as starting points to be calibrated, not as ground truth.

Difficulty axis is the published three-tier split (easy/medium/hard).
"""

from __future__ import annotations

from memsolver import pricing

DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard")

# Calibrated per-model multiplier applied to ``p_correct`` by the lab gateway.
# Values were chosen so a single model reproduces the published single-model
# anchors on the 60-case local holdout: mini (the reference/shipped model)
# lands at ~0.62-0.66 exact-goal success, strong alone stays below the 85.3%
# quality gate, and nano is both the weakest and the cheapest tier.
P_SCALE: dict[str, float] = {
    "nano": 0.55,
    "mini": 0.45,
    "strong": 0.85,
}

# model -> difficulty -> profile. p_correct: plan-correctness anchor.
# out_tokens / latency_ms are token & wall-clock ranges per completed call.
CAPABILITY: dict[str, dict[str, dict]] = {
    "nano": {
        "easy":   {"p_correct": 0.66, "out_tokens": (60, 140), "latency_ms": (180, 500)},
        "medium": {"p_correct": 0.40, "out_tokens": (80, 200), "latency_ms": (300, 900)},
        "hard":   {"p_correct": 0.22, "out_tokens": (120, 300), "latency_ms": (400, 1200)},
    },
    "mini": {
        "easy":   {"p_correct": 0.80, "out_tokens": (80, 180), "latency_ms": (300, 800)},
        "medium": {"p_correct": 0.55, "out_tokens": (120, 280), "latency_ms": (500, 1400)},
        "hard":   {"p_correct": 0.40, "out_tokens": (160, 400), "latency_ms": (700, 2200)},
    },
    "strong": {
        "easy":   {"p_correct": 0.93, "out_tokens": (100, 220), "latency_ms": (500, 1200)},
        "medium": {"p_correct": 0.70, "out_tokens": (160, 360), "latency_ms": (800, 2000)},
        "hard":   {"p_correct": 0.60, "out_tokens": (200, 500), "latency_ms": (1000, 2800)},
    },
}


def profile(model_or_alias: str, difficulty: str) -> dict:
    """Capability profile for a canonical/aliased model and a difficulty."""
    model = pricing.resolve(model_or_alias)
    if difficulty not in DIFFICULTIES:
        raise ValueError(
            f"Unknown difficulty: {difficulty!r}. Known: {list(DIFFICULTIES)}"
        )
    return CAPABILITY[model][difficulty]
