"""Dependency-free SVG charts from the measured artifacts (results/final/*).

    python3 -m lab.plots
Writes results/final/pareto.svg (quality vs cost-per-resolved frontier) and
results/final/tokens-by-call.svg (billed input+output tokens per generation
call index for a few operating points) so the ledger data is visible as
graphs without any plotting library.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIN = ROOT / "results" / "final"
RUNS = ROOT / "results" / "runs"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _svg(w: int, h: int, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">'
            f"<rect width='{w}' height='{h}' fill='white'/>{body}</svg>")


def pareto_svg(points: list[dict]) -> str:
    W, H, L, B, T, R = 720, 420, 70, 40, 30, 30
    plot_w, plot_h = W - L - R, H - B - T
    costs = [p["cost_per_resolved_case"] for p in points if p["cost_per_resolved_case"]]
    cmin, cmax = min(costs), max(costs)
    lmin, lmax = math.log10(cmin), math.log10(cmax)
    qmin, qmax = 0.60, 0.90

    def x(q: float) -> float:
        return L + (q - qmin) / (qmax - qmin) * plot_w

    def y(c: float) -> float:
        return T + (lmax - math.log10(c)) / (lmax - lmin) * plot_h

    body = []
    # grid + labels
    for i in range(7):
        q = qmin + (qmax - qmin) * i / 6
        body.append(f'<line x1="{x(q)}" y1="{T}" x2="{x(q)}" y2="{T + plot_h}" '
                    f'stroke="#eee"/>')
        body.append(f'<text x="{x(q)}" y="{T + plot_h + 16}" font-size="10" '
                    f'text-anchor="middle">{q:.2f}</text>')
    for j in range(6):
        c = 10 ** (lmin + (lmax - lmin) * j / 5)
        body.append(f'<line x1="{L}" y1="{y(c)}" x2="{L + plot_w}" y2="{y(c)}" '
                    f'stroke="#eee"/>')
        body.append(f'<text x="{L - 6}" y="{y(c) + 4}" font-size="10" '
                    f'text-anchor="end">${c:.5f}</text>')
    body.append(f'<text x="{L + plot_w / 2}" y="{H - 4}" font-size="11" '
                f'text-anchor="middle">quality (exact goal match)</text>')
    body.append(f'<text x="14" y="{T + plot_h / 2}" font-size="11" '
                f'transform="rotate(-90 14 {T + plot_h / 2})" '
                f'text-anchor="middle">$ per resolved case (log)</text>')
    # floor + cost-bar guide lines
    for (q, c, color, dash) in ((0.853, None, "#c33", "4 3"), (None, cmin * 10, "#3a3", "4 3")):
        if q is not None:
            body.append(f'<line x1="{x(q)}" y1="{T}" x2="{x(q)}" y2="{T + plot_h}" '
                        f'stroke="{color}" stroke-dasharray="{dash}"/>')
        if c is not None:
            body.append(f'<line x1="{L}" y1="{y(c)}" x2="{L + plot_w}" y2="{y(c)}" '
                        f'stroke="{color}" stroke-dasharray="{dash}"/>')
    # points
    for p in points:
        if not p["cost_per_resolved_case"]:
            continue
        px, py = x(p["quality"]), y(p["cost_per_resolved_case"])
        color = "#b44" if p.get("rejected") else "#26b"
        body.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{color}"/>')
        body.append(f'<text x="{px + 7}" y="{py - 6}" font-size="9">{_esc(p["label"])}</text>')
    return _svg(W, H, "".join(body))


def tokens_svg(sets: list[tuple[str, list[float]]]) -> str:
    W, H, L, B, T = 720, 360, 60, 46, 26
    plot_w = W - L - 20
    n_groups = max(len(v) for _, v in sets)
    allv = [v for _, v in sets]
    peak = max(max(v) for v in allv)
    group_w = plot_w / n_groups
    bw = min(26.0, group_w * 0.7 / len(sets))
    colors = ["#26b", "#3a3", "#b44"]
    body = []
    for g in range(n_groups):
        cx = L + group_w * g + group_w / 2
        for k, (name, vals) in enumerate(sets):
            if g >= len(vals):
                continue
            v = vals[g]
            bar_h = v / peak * (H - T - B)
            bx = cx - bw * len(sets) / 2 + bw * k
            body.append(f'<rect x="{bx:.1f}" y="{H - B - bar_h:.1f}" width="{bw - 2}" '
                        f'height="{bar_h:.1f}" fill="{colors[k % 3]}"/>')
        body.append(f'<text x="{cx}" y="{H - B + 14}" font-size="9" '
                    f'text-anchor="middle">call {g}</text>')
    for k, (name, _) in enumerate(sets):
        body.append(f'<rect x="{L}" y="{T + k * 14}" width="10" height="10" '
                    f'fill="{colors[k % 3]}"/>')
        body.append(f'<text x="{L + 14}" y="{T + k * 14 + 9}" font-size="10">{_esc(name)}</text>')
    body.append(f'<text x="{L + plot_w / 2}" y="{H - 6}" font-size="11" '
                f'text-anchor="middle">generation call index within a case</text>')
    body.append(f'<text x="14" y="{T + plot_w / 2}" font-size="11" '
                f'transform="rotate(-90 14 {T + plot_w / 2})" '
                f'text-anchor="middle">billed tokens (in+out), run total</text>')
    return _svg(W, H, "".join(body))


def _call_index_tokens(directory: Path) -> list[float]:
    rows = [json.loads(l) for l in (directory / "ledger.jsonl").read_text().splitlines()
            if l.strip() and json.loads(l)["stage"] == "generate"]
    by_case: dict[str, list[float]] = {}
    for r in rows:
        by_case.setdefault(r["case_id"], []).append(r["input_tokens"] + r["output_tokens"])
    agg: dict[int, float] = {}
    for vals in by_case.values():
        for i, v in enumerate(vals):
            agg[i] = agg.get(i, 0.0) + v
    return [agg[i] for i in range(max(agg) + 1)]


def main() -> int:
    FIN.mkdir(parents=True, exist_ok=True)
    points = [json.loads(l) for l in (FIN / "pareto.jsonl").read_text().splitlines() if l.strip()]
    (FIN / "pareto.svg").write_text(pareto_svg(points), encoding="utf-8")
    sets = []
    for name in ("prune-nano-pc", "prune-nano-ladderNS-verify-pc", "shipped-prefixcache"):
        d = RUNS / name
        if (d / "ledger.jsonl").exists():
            sets.append((name.replace("prune-", "").replace("-pc", " +pc"), _call_index_tokens(d)))
    if sets:
        (FIN / "tokens-by-call.svg").write_text(tokens_svg(sets), encoding="utf-8")
    print(f"wrote {FIN / 'pareto.svg'} and {FIN / 'tokens-by-call.svg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
