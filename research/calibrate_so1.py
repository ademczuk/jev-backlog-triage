"""Same calibration sets through an open-weights model via so1 (open-alternative-jev), locally, on CPU.
Usage: .venv-so1/Scripts/python calibrate_so1.py <set> <tag> [limit]
Writes results/<set>.<tag>.jsonl in the same shape as calibrate.ts, so analyze.py reads both.
"""
import json
import sys
import time
from pathlib import Path

import torch
from so1 import Choice, Decider, yes_no

MODEL = "Qwen/Qwen3.5-2B"
here = Path(__file__).parent
set_, tag = sys.argv[1], sys.argv[2]
limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
items = [json.loads(l) for l in (here / "data" / f"{set_}.jsonl").open(encoding="utf-8")][:limit]

if set_ == "sst2":
    q = yes_no("Is the sentiment of this sentence from a movie review positive?")
elif set_ == "irony":
    q = yes_no("Is this tweet ironic?")
else:
    labels = json.loads((here / "data" / "banking77.labels.json").read_text(encoding="utf-8"))
    q = Choice("Which intent best describes this message from a bank customer?", labels)

t0 = time.perf_counter()
decider = Decider.from_pretrained(MODEL, backend="hf", device_map="cpu", torch_dtype=torch.bfloat16)
print(f"loaded {MODEL} in {time.perf_counter() - t0:.0f}s", file=sys.stderr)

out = here / "results" / f"{set_}.{tag}.jsonl"
out.parent.mkdir(exist_ok=True)
with out.open("w", encoding="utf-8") as f:
    for n, it in enumerate(items, 1):
        t = time.perf_counter()
        try:
            d = decider.decide(state=it["text"], questions=[q])[0]
            probs = dict(zip(d.question.options, d.probabilities))
            if set_ in ("sst2", "irony"):
                ans = {"type": "boolean", "probability": float(probs["yes"])}
            else:
                ans = {"type": "choice", "choice": d.choice, "probabilities": {k: float(v) for k, v in probs.items()}}
            row = {"id": it["id"], "label": it["label"], "answer": ans, "confidence": float(d.confidence),
                   "ms": round((time.perf_counter() - t) * 1000)}
        except Exception as e:
            row = {"id": it["id"], "label": it["label"], "error": repr(e)[:300], "ms": round((time.perf_counter() - t) * 1000)}
        f.write(json.dumps(row) + "\n")
        f.flush()
        if n % 50 == 0:
            print(f"[{set_}.{tag}] {n}/{len(items)}", file=sys.stderr)
print(f"{set_}.{tag}: {len(items)} rows written to {out}")
