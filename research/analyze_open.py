"""jev against the open decision models run locally on CPU, same rows, same question wording, P(true)
against the label. Telco and Bank are clean for every model; SST-2 and irony are flagged where a
model's published training data covers them. Descriptive: PROTOCOL.md's verdict is jev's alone.
"""
import json
import statistics
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import cross_val_predict

from analyze_tabular import baselines, load, metrics

RES = Path(__file__).parent / "results"
# model -> tag per set family; jev's tabular tag merges its retry file through analyze_tabular.load
TAGS = {"jev": {"tab": "r1", "text": "a"}, "laya (choice)": {"tab": "layac", "text": "layac"},
        "laya (noul)": {"tab": "laya1", "text": "laya1"},
        "kev-0.8b": {"tab": "kev1", "text": "kev1"}, "so1 (Qwen3.5-2B)": {"text": "so1a"}}
# SST-5 shares SST-2's sentences
CONTAMINATED = {"sst2": {"laya (choice)", "laya (noul)", "kev-0.8b"}, "irony": set()}
NOTE = {"sst2": "laya and kev-0.8b trained on SST-5 (same source sentences)",
        "irony": "kev-0.8b card lists no TweetEval (the Kev-4B/9B README does); laya lists none"}


def ok_rows(name, tag):
    return {r["id"]: r for r in load(name, tag) if "error" not in r}


def platt(p, y):
    x = np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4))).reshape(-1, 1)
    return cross_val_predict(LogisticRegression(), x, y.astype(int), cv=5, method="predict_proba")[:, 1]


def line(name, p, y, ms):
    m = metrics(p, y)
    pm = metrics(platt(p, y), y)
    return (f"  {name:<17} n {m['n']:>3}  acc {m['accuracy']:.3f}  Brier {m['brier']:.4f}  BSS {m['brier_skill']:+.3f}  "
            f"ECE_sweep {m['ece_sweep']:.3f}  AUC {roc_auc_score(y, p):.3f}  mean P {p.mean():.3f}  "
            f"| Platt: Brier {pm['brier']:.4f} ECE_sweep {pm['ece_sweep']:.3f}  | median ms {int(np.median(ms)) if ms else -1}")


def compare(set_, fam, extra=""):
    rows = {m: ok_rows(set_, t[fam]) for m, t in TAGS.items() if fam in t}
    rows = {m: r for m, r in rows.items() if r}
    ids = sorted(set.intersection(*(set(r) for r in rows.values())))
    y = np.array([1.0 if rows["jev"][i]["label"] in (True, 1) else 0.0 for i in ids])
    print(f"\n==== {set_}: {len(ids)} rows common to {', '.join(rows)}; majority {max(y.mean(), 1 - y.mean()):.3f} {extra}====")
    ps = {}
    for m, r in rows.items():
        p = np.array([r[i]["answer"]["probability"] for i in ids], float)
        ps[m] = p
        flag = "  [CONTAMINATED]" if m in CONTAMINATED.get(set_, ()) else ""
        print(line(m, p, y, [r[i]["ms"] for i in ids if "ms" in r[i]]) + flag)
    for m, p in ps.items():
        if m != "jev":
            print(f"  decision agreement jev vs {m}: {np.mean((p >= .5) == (ps['jev'] >= .5)):.3f}")
    return ps


for s in ("telco", "bank"):
    for k, m in baselines(s).items():
        print(f"  [{s}] free {k:<20} acc {m['accuracy']:.3f}  Brier {m['brier']:.4f}  BSS {m['brier_skill']:+.3f}  ECE_sweep {m['ece_sweep']:.3f}")
    compare(s, "tab", "(clean for all models) ")

for m, tag in (("laya (choice)", "layac"), ("laya (noul)", "laya1"), ("kev-0.8b", "kev1")):
    hostile = ok_rows("telco_hostile", tag)
    base = ok_rows("telco", tag)
    pairs = [(base[h[:-2]], hostile[h]) for h in hostile if h[:-2] in base]
    if pairs:
        ch = sum((c["answer"]["probability"] >= .5) != (h["answer"]["probability"] >= .5) for c, h in pairs)
        sh = statistics.mean(h["answer"]["probability"] - c["answer"]["probability"] for c, h in pairs)
        print(f"\n  hostile, {m}: decision changed on {ch} of {len(pairs)} ({ch / len(pairs):.0%}), mean shift in P(churn) {sh:+.3f}"
              f"  (jev: 12 of 50, 24%, -0.065)")

for s in ("sst2", "irony"):
    compare(s, "text", f"({NOTE[s]}) ")

# PROTOCOL-HARNESS.md T1 and T3, descriptive for the open models (Laya asked as choice).
from analyze_harness import DATA, jl, load as hload, routed_accuracy  # noqa: E402

HTAGS = {"jev": "h1", "laya (choice)": "layac", "kev-0.8b": "kev1"}
for s in ("routing", "injection"):
    ev = jl(DATA / f"{s}.jsonl")
    got = {m: hload(s, t)[0] for m, t in HTAGS.items()}
    got = {m: r for m, r in got.items() if len(r) > len(ev) * 0.9}
    ids = [r["id"] for r in ev if all(r["id"] in g for g in got.values())]
    rows = {r["id"]: r for r in ev}
    y = np.array([float(rows[i]["label"]) for i in ids])
    print(f"\n==== harness {s}: {len(ids)} rows common to {', '.join(got)} ====")
    for m, g in got.items():
        p = np.array([g[i]["answer"]["probability"] for i in ids])
        out = f"  {m:<14} AUC {roc_auc_score(y, p):.3f}  mean P {p.mean():.3f}"
        if s == "routing":
            ys = np.array([float(rows[i]["strong_correct"]) for i in ids])
            a, _ = routed_accuracy(list(p), y, ys, np.zeros(len(ids)), np.zeros(len(ids)), 0.5)
            out += f"  f=0.5 routed acc {a:.3f} (random {0.5 * y.mean() + 0.5 * ys.mean():.3f})"
        else:
            neg = np.sort(p[y == 0])[::-1]
            t = neg[3] + 1e-9 if len(neg) > 3 else 0.0
            out += (f"  at 0.5: FN {int(((p < .5) & (y == 1)).sum())}/{int(y.sum())}, FP {int(((p >= .5) & (y == 0)).sum())}/{int((1 - y).sum())}"
                    f"  at FP<=3: FN {int(((p < t) & (y == 1)).sum())}  median ms {int(np.median([g[i]['ms'] for i in ids]))}")
        print(out)
