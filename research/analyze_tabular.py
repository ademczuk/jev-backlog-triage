"""Metrics exactly as frozen in PROTOCOL.md (sha256 caaad830...489979). Prints the card."""
import json
import statistics
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer

HERE = Path(__file__).parent
DATA, RES = HERE / "data", HERE / "results"


def ece_sweep(p, y):
    """Roelofs et al. 2022, equal-mass bins, largest bin count keeping bin accuracies monotone. L1."""
    order = np.argsort(p)
    p, y = p[order], y[order]
    best = 1
    for b in range(2, len(p) + 1):
        acc = [c.mean() for c in np.array_split(y, b)]
        if all(a <= c for a, c in zip(acc, acc[1:])):
            best = b
        else:
            break
    return sum(len(cp) / len(p) * abs(cp.mean() - cy.mean())
               for cp, cy in zip(np.array_split(p, best), np.array_split(y, best))), best


def reliability(p, y, bins=10):
    order = np.argsort(p)
    return [(float(cp.mean()), float(cy.mean()), len(cp))
            for cp, cy in zip(np.array_split(p[order], bins), np.array_split(y[order], bins))]


def metrics(p, y):
    p, y = np.asarray(p, float), np.asarray(y, float)
    base = y.mean()
    brier = float(np.mean((p - y) ** 2))
    brier_ref = float(np.mean((base - y) ** 2))
    e, b = ece_sweep(p, y)
    return {"n": len(p), "accuracy": float(np.mean((p >= 0.5) == (y == 1))),
            "majority_accuracy": float(max(base, 1 - base)), "brier": brier,
            "brier_skill": 1 - brier / brier_ref, "ece_sweep": float(e), "ece_sweep_bins": b,
            "reliability": reliability(p, y)}


def baselines(name):
    tr = pd.read_csv(DATA / f"{name}.train.csv")
    ev = pd.read_csv(DATA / f"{name}.eval.csv")
    X, y, Xe, ye = tr.drop(columns="label"), tr["label"].astype(int), ev.drop(columns="label"), ev["label"].astype(int)
    cat = [c for c in X.columns if X[c].dtype == object]
    num = [c for c in X.columns if c not in cat]
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat),
        ("num", make_pipeline(SimpleImputer(), StandardScaler()), num)])
    out = {}
    lr = make_pipeline(pre, LogisticRegression(max_iter=2000)).fit(X, y)
    out["logistic regression"] = metrics(lr.predict_proba(Xe)[:, 1], ye)
    Xc, Xec = X.copy(), Xe.copy()
    for c in cat:
        Xc[c] = Xc[c].astype("category")
        Xec[c] = pd.Categorical(Xec[c], categories=Xc[c].cat.categories)
    gb = HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=0).fit(Xc, y)
    out["gradient boosting"] = metrics(gb.predict_proba(Xec)[:, 1], ye)
    return out


def load(name, tag):
    """Original pass, with any row that failed replaced by its retry (PROTOCOL.md: re-run once)."""
    f, fr = RES / f"{name}.{tag}.jsonl", RES / f"{name}.{tag}retry.jsonl"
    rows = [json.loads(l) for l in f.open(encoding="utf-8")] if f.exists() else []
    if fr.exists():
        retry = {r["id"]: r for r in map(json.loads, fr.open(encoding="utf-8"))}
        rows = [retry.get(r["id"], r) if "error" in r else r for r in rows]
    return rows


def jev_rows(name, tag):
    rows = load(name, tag)
    ok = {r["id"]: r for r in rows if "error" not in r}
    return rows, ok


def card(name):
    print(f"\n==== {name} ====")
    for k, m in baselines(name).items():
        print(f"  {k:<20} acc {m['accuracy']:.3f} (majority {m['majority_accuracy']:.3f})  brier {m['brier']:.4f}  "
              f"BSS {m['brier_skill']:+.3f}  ECE_sweep {m['ece_sweep']:.3f} ({m['ece_sweep_bins']} bins)")
    rows, ok = jev_rows(name, "r1")
    if not rows:
        print("  jev: no results yet")
        return None
    ids = [r["id"] for r in rows if r["id"] in ok]
    p = [ok[i]["answer"]["probability"] for i in ids]
    y = [ok[i]["label"] for i in ids]
    m = metrics(p, y)
    print(f"  {'jev':<20} acc {m['accuracy']:.3f} (majority {m['majority_accuracy']:.3f})  brier {m['brier']:.4f}  "
          f"BSS {m['brier_skill']:+.3f}  ECE_sweep {m['ece_sweep']:.3f} ({m['ece_sweep_bins']} bins)  "
          f"n {m['n']}, failed calls {len(rows) - len(ok)}")
    print("  reliability (mean stated -> actual, n):", ", ".join(f"{a:.2f}->{b:.2f}" for a, b, _ in m["reliability"]))
    reps = [jev_rows(name, f"r{k}")[1] for k in range(1, 6)]
    common = [i for i in ids[:150] if all(i in r for r in reps)]
    flips, spreads = 0, []
    for i in common:
        ps = [r[i]["answer"]["probability"] for r in reps]
        flips += len({x >= 0.5 for x in ps}) > 1
        spreads.append(max(ps) - min(ps))
    if common:
        spreads.sort()
        m["flip_rate"] = flips / len(common)
        m["median_spread"] = statistics.median(spreads)
        print(f"  stability over {len(common)} rows x 5: argmax flips {flips} ({m['flip_rate']:.1%}), "
              f"median spread {m['median_spread']:.3f}, p95 spread {spreads[int(len(spreads) * 0.95)]:.3f}")
    return m


if __name__ == "__main__":
    res = {n: card(n) for n in ("telco", "bank")}
    hrows, hok = jev_rows("telco_hostile", "r1")
    _, clean = jev_rows("telco", "r1")
    pairs = [(clean[h["id"][:-2]], h) for h in hok.values() if h["id"][:-2] in clean]
    if pairs:
        changed = sum((c["answer"]["probability"] >= 0.5) != (h["answer"]["probability"] >= 0.5) for c, h in pairs)
        churn_called = sum(c["answer"]["probability"] >= 0.5 for c, _ in pairs)
        shift = statistics.mean(h["answer"]["probability"] - c["answer"]["probability"] for c, h in pairs)
        print(f"\n==== hostile ({len(pairs)} pairs) ====\n  argmax changed on {changed} ({changed / len(pairs):.1%}); "
              f"clean call said churn on {churn_called}; mean shift in p {shift:+.3f}")
