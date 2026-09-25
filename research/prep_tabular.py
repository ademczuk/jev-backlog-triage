"""Tabular sets per PROTOCOL.md: 600 eval rows each (seed 20260923), rest kept for the local baselines."""
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)
SEED, N = 20260923, 600

TELCO = "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
BANK = "https://archive.ics.uci.edu/static/public/222/bank+marketing.zip"


def fetch(url):
    return urllib.request.urlopen(url, timeout=120).read()


telco = pd.read_csv(io.BytesIO(fetch(TELCO)))
telco = telco.drop(columns=["customerID"])
telco["TotalCharges"] = pd.to_numeric(telco["TotalCharges"], errors="coerce")
telco["label"] = telco.pop("Churn").eq("Yes")

outer = zipfile.ZipFile(io.BytesIO(fetch(BANK)))
inner_name = next(n for n in outer.namelist() if n.endswith("bank-additional.zip"))
inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))
csv_name = next(n for n in inner.namelist() if n.endswith("bank-additional-full.csv"))
bank = pd.read_csv(io.BytesIO(inner.read(csv_name)), sep=";")
bank = bank.drop(columns=["duration"])  # UCI: known only after the call, leaks the outcome
bank["label"] = bank.pop("y").eq("yes")


def split(df, name):
    ev = df.sample(n=N, random_state=SEED)
    tr = df.drop(ev.index)
    tr.to_csv(OUT / f"{name}.train.csv", index=False)
    ev.to_csv(OUT / f"{name}.eval.csv", index=False)
    with open(OUT / f"{name}.jsonl", "w", encoding="utf-8") as f:
        for i, (_, r) in enumerate(ev.iterrows()):
            text = "\n".join(f"{k}: {v}" for k, v in r.items() if k != "label")
            f.write(json.dumps({"id": f"{name}-{i}", "text": text, "label": bool(r["label"])}) + "\n")
    print(f"{name}: full {len(df)} base {df.label.mean():.3f} | eval {len(ev)} base {ev.label.mean():.3f} | train {len(tr)}")


split(telco, "telco")
split(bank, "bank")
