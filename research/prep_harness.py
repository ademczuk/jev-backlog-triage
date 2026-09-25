"""Sample the three harness sets (PROTOCOL-HARNESS.md). Seed 20260925. Needs the raw files in RAW:
  routerbench_0shot.pkl (withmartian/routerbench, license unstated: NOT committed, regenerate from here)
  pi_train.parquet, pi_test.parquet (deepset/prompt-injections, Apache-2.0)
  plugin_des.json, all_clean_data.csv (HowieHwong/MetaTool, MIT)
"""
import json
import os
from pathlib import Path

import pandas as pd

SEED = 20260925
RAW = Path(os.environ.get("HARNESS_RAW", "C:/Projects/_scratch/jev-open/harness"))
OUT = Path(__file__).parent / "data"
CHEAP, STRONG = "gpt-3.5-turbo-1106", "gpt-4-1106-preview"
FAMILIES = r"^(mmlu-|arc-challenge$|hellaswag$|winogrande$)"


def dump(rows, name):
    with (OUT / name).open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{name}: {len(rows)} rows")


# T1 routing: 125 eval rows per family, both labels strictly 0/1; the rest is the baseline training pool.
d = pd.read_pickle(RAW / "routerbench_0shot.pkl")
d = d[d.eval_name.str.match(FAMILIES) & d[CHEAP].isin([0.0, 1.0]) & d[STRONG].isin([0.0, 1.0])].copy()
d["family"] = d.eval_name.str.replace(r"^mmlu-.*", "mmlu", regex=True)
ev = d.groupby("family", group_keys=False).apply(lambda g: g.sample(125, random_state=SEED))
tr = d.drop(ev.index)
row = lambda r: {"id": f"route-{r.sample_id}", "text": r.prompt, "label": bool(r[CHEAP]),
                 "strong_correct": bool(r[STRONG]), "family": r.family,
                 "cheap_cost": float(r[f"{CHEAP}|total_cost"]), "strong_cost": float(r[f"{STRONG}|total_cost"])}
dump([row(r) for _, r in ev.iterrows()], "routing.jsonl")
dump([row(r) for _, r in tr.iterrows()], "routing.train.jsonl")

# T2 tool selection: 2 queries per tool, 199 tools; the remaining queries are the trained-baseline pool.
tools = json.loads((RAW / "plugin_des.json").read_text(encoding="utf-8"))
canon = {k.lower(): k for k in tools}
q = pd.read_csv(RAW / "all_clean_data.csv").dropna()
q["tool"] = q.Tool.str.lower().map(canon)
q = q.dropna(subset=["tool"]).drop_duplicates("Query")
ev = q.groupby("tool", group_keys=False).apply(lambda g: g.sample(min(2, len(g)), random_state=SEED))
tr = q.drop(ev.index)
dump([{"id": f"tool-{i}", "text": r.Query, "label": r.tool} for i, r in ev.iterrows()], "tools.jsonl")
dump([{"id": f"tool-{i}", "text": r.Query, "label": r.tool} for i, r in tr.iterrows()], "tools.train.jsonl")
(OUT / "tools.options.json").write_text(json.dumps(tools, ensure_ascii=False, indent=0), encoding="utf-8")

# T3 injection gate: the published test split whole; the train split is the baseline training pool.
for split, name in (("test", "injection.jsonl"), ("train", "injection.train.jsonl")):
    p = pd.read_parquet(RAW / f"pi_{split}.parquet")
    dump([{"id": f"inj-{split}-{i}", "text": r.text, "label": bool(r.label)} for i, r in p.iterrows()], name)
