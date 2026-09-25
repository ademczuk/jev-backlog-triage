"""Reliability analysis of the jev calibration runs. Reads results/<set>.<a|b>.jsonl."""
import json
import statistics
import sys
from pathlib import Path

RES = Path(__file__).parent / "results"
BINS = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 0.99), (0.99, 1.01)]


def load(set_, pass_):
    p = RES / f"{set_}.{pass_}.jsonl"
    return [json.loads(l) for l in p.open(encoding="utf-8")] if p.exists() else None


def predict(r):
    """Return (predicted label, stated confidence in that prediction)."""
    a = r["answer"]
    if a["type"] == "boolean":
        p = a["probability"]
        return p >= 0.5, max(p, 1 - p)
    probs = a.get("probabilities") or {}
    return a["choice"], probs.get(a["choice"], r.get("confidence") or 0.0)


def reliability(rows, title):
    ok = [r for r in rows if "error" not in r]
    errs = len(rows) - len(ok)
    pts = [(predict(r)[1], predict(r)[0] == r["label"]) for r in ok]
    acc = sum(c for _, c in pts) / len(pts)
    ece = 0.0
    print(f"\n{title}: n={len(ok)} errors={errs} accuracy={acc:.3f}")
    print(f"  {'stated':>11} {'n':>5} {'mean stated':>12} {'actual':>7} {'gap':>7}")
    for lo, hi in BINS:
        b = [(p, c) for p, c in pts if lo <= p < hi]
        if not b:
            continue
        ms = sum(p for p, _ in b) / len(b)
        ac = sum(c for _, c in b) / len(b)
        ece += len(b) / len(pts) * abs(ms - ac)
        print(f"  {lo:.2f}-{min(hi,1):.2f} {len(b):>5} {ms:>12.3f} {ac:>7.3f} {ac - ms:>+7.3f}")
    print(f"  ECE={ece:.3f}  (0 = perfectly calibrated; gap < 0 means overconfident)")
    return acc, ece


def drift(a, b, title):
    ba = {r["id"]: r for r in a if "error" not in r}
    bb = {r["id"]: r for r in b if "error" not in r}
    ids = sorted(set(ba) & set(bb))
    deltas, flips = [], 0
    for i in ids:
        pa, ca = predict(ba[i])
        pb, cb = predict(bb[i])
        flips += pa != pb
        deltas.append(abs(ca - cb))
    print(f"\n{title} run-to-run, {len(ids)} items: answer flipped on {flips}; "
          f"|confidence change| mean {statistics.mean(deltas):.3f}, max {max(deltas):.3f}, "
          f"identical on {sum(d == 0 for d in deltas)}")


def threshold_table(rows, title, ts=(0.7, 0.8, 0.9, 0.95)):
    ok = [r for r in rows if "error" not in r]
    print(f"\n{title}: act above threshold, escalate below")
    for t in ts:
        act = [r for r in ok if predict(r)[1] >= t]
        right = sum(predict(r)[0] == r["label"] for r in act)
        print(f"  t={t:.2f}: auto {len(act)}/{len(ok)} ({len(act)/len(ok):.0%}), "
              f"wrong among auto {len(act)-right} ({(len(act)-right)/max(len(act),1):.1%})")


def latency_cost(rows, title):
    ok = [r for r in rows if "error" not in r]
    ms = sorted(r["ms"] for r in ok)
    tok = sum((r.get("usage") or {}).get("inputTokens") or 0 for r in ok)
    print(f"{title}: p50 {ms[len(ms)//2]} ms, p95 {ms[int(len(ms)*0.95)]} ms (client-side, concurrency 8, incl. gateway); "
          f"input tokens {tok}, cost ${tok * 0.042 / 1e6:.4f}")


for s in sys.argv[1:] or ["sst2", "irony", "banking77"]:
    a, b = load(s, "a"), load(s, "b")
    if not a:
        print(f"\n{s}: no results yet")
        continue
    reliability(a, f"{s} pass a")
    if b:
        reliability(b, f"{s} pass b")
        drift(a, b, s)
    threshold_table(a, f"{s} pass a")
    latency_cost(a + (b or []), f"{s} both passes")
