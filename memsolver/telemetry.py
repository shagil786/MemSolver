"""Telemetry dataclasses and JSONL I/O."""

from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class ModelCallRecord:
    tier: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost: float
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RequestTelemetry:
    request_id: str
    case_id: str
    route: str
    model: str
    model_calls: int
    input_tokens: int
    output_tokens: int
    retries: int
    retry_reasons: list[str]
    escalations: int
    cache_hit: bool
    success: bool
    latency_ms: float
    cost: float
    calls: list[ModelCallRecord]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["calls"] = [c.to_dict() for c in self.calls]
        return d


def write_jsonl(path: Path, records: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.to_dict() if hasattr(r, "to_dict") else r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
