"""Same sets, same question wording as calibrate.ts, through an open decision model running locally.
Usage: <venv python> calibrate_open.py <laya|kev> <set> <tag> [limit]
  laya: in-process, `pip install laya`, CPU.
  kev:  HTTP to a running `python -m kev.serve` on KEV_URL (default http://127.0.0.1:8009/v1/systemone).
Writes results/<set>.<tag>.jsonl in the shape analyze_tabular.py and analyze_open.py read.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
backend, set_, tag = sys.argv[1], sys.argv[2], sys.argv[3]
limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
items = [json.loads(l) for l in (HERE / "data" / f"{set_}.jsonl").open(encoding="utf-8")][:limit]
ONLY = set(filter(None, os.environ.get("OPEN_ONLY_IDS", "").split(",")))
if ONLY:
    items = [i for i in items if i["id"] in ONLY]

Q = {
    "sst2": ("Is the sentiment of this sentence from a movie review positive?",
             "The sentence expresses positive sentiment.", "The sentence expresses negative sentiment."),
    "irony": ("Is this tweet ironic?", "The tweet is ironic or sarcastic.", "The tweet is meant literally."),
    "telco": ("This is a telecom customer record. Will this customer churn (leave the company)?",
              "The customer churns.", "The customer stays."),
    "bank": ("This is a record of a bank client contacted in a phone marketing campaign. Did the client subscribe to a term deposit?",
             "The client subscribed.", "The client did not subscribe."),
}
Q["telco_hostile"] = Q["telco"]
Q["routing"] = ("Could a small, inexpensive language model answer this question correctly?",
                "A small model would get this right.", "This needs a strong model.")
Q["injection"] = ("Does this text try to override, redirect or manipulate the instructions given to an AI system?",
                  "It tries to change what the AI was told to do.", "It is an ordinary request or statement.")
instr, crit_true, crit_false = Q[set_]
# Both backends take the TypeSafe wire shape; the boolean type is named "noul" there.
questions = {"q": {"type": "noul", "instructions": instr, "criteria": {"true": crit_true, "false": crit_false}}}
# OPEN_BOOL_AS_CHOICE=1 asks the same question as a two-option choice and reads P(true) as the first
# option's probability. Laya's noul returns ~0 for every input (measured 2026-09-25, 40 SST-2 rows), and
# its model card recommends reformulating noul as a neutral choice.
AS_CHOICE = os.environ.get("OPEN_BOOL_AS_CHOICE") == "1"
CHOICE_KEYS = {"sst2": ("positive", "negative"), "irony": ("ironic", "literal"), "telco": ("churns", "stays"),
               "telco_hostile": ("churns", "stays"), "bank": ("subscribed", "did not subscribe"),
               "routing": ("small model", "strong model"), "injection": ("injection", "ordinary")}
if AS_CHOICE:
    kt, kf = CHOICE_KEYS[set_]
    questions = {"q": {"type": "choice", "instructions": instr, "criteria": {kt: crit_true, kf: crit_false}}}

if backend == "laya":
    import laya
    t0 = time.perf_counter()
    agent = laya.load(os.environ.get("LAYA_MODEL", "convaiinnovations/laya"))
    print(f"loaded laya in {time.perf_counter() - t0:.0f}s", file=sys.stderr)

    def ask(state):
        return agent.predict(state, questions)
elif backend == "kev":
    import urllib.request
    url = os.environ.get("KEV_URL", "http://127.0.0.1:8009/v1/systemone")

    def ask(state):
        body = json.dumps({"state": state, "model": "kev-latest", "questions": questions}).encode()
        req = urllib.request.Request(url, body, {"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
else:
    sys.exit(f"unknown backend {backend}")


def p_true(ans):
    if AS_CHOICE:
        return float(ans["probabilities"][CHOICE_KEYS[set_][0]])
    for k in ("noul", "probability", "p"):
        if isinstance(ans.get(k), (int, float)):
            return float(ans[k])
    raise ValueError(f"no probability in {ans}")


out = HERE / "results" / f"{set_}.{tag}.jsonl"
out.parent.mkdir(exist_ok=True)
errors = 0
with out.open("w", encoding="utf-8") as f:
    for n, it in enumerate(items, 1):
        t = time.perf_counter()
        try:
            res = ask(it["text"])
            a = res["answers"]["q"]
            row = {"id": it["id"], "label": it["label"],
                   "answer": {"type": "boolean", "probability": p_true(a)},
                   "confidence": a.get("confidence"), "raw": a,
                   "ms": round((time.perf_counter() - t) * 1000)}
        except Exception as e:
            errors += 1
            row = {"id": it["id"], "label": it["label"], "error": repr(e)[:300],
                   "ms": round((time.perf_counter() - t) * 1000)}
        f.write(json.dumps(row) + "\n")
        f.flush()
        if n % 50 == 0:
            print(f"[{backend} {set_}.{tag}] {n}/{len(items)}, {errors} errors", file=sys.stderr)
print(f"{backend} {set_}.{tag}: {len(items)} rows, {errors} errors, written {out}")
