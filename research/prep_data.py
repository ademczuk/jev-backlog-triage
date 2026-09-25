"""Build the calibration sets from public, human-labelled datasets. Nothing internal."""
import json
import random
from pathlib import Path

from datasets import load_dataset

OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)
N = 400
rng = random.Random(20260923)


def sample(rows, n):
    rows = list(rows)
    rng.shuffle(rows)
    return rows[:n]


sst = load_dataset("stanfordnlp/sst2", split="validation")
with open(OUT / "sst2.jsonl", "w", encoding="utf-8") as f:
    for i, r in enumerate(sample(sst, N)):
        f.write(json.dumps({"id": f"sst2-{i}", "text": r["sentence"], "label": bool(r["label"])}) + "\n")

irony = load_dataset("cardiffnlp/tweet_eval", "irony", split="test")
with open(OUT / "irony.jsonl", "w", encoding="utf-8") as f:
    for i, r in enumerate(sample(irony, N)):
        f.write(json.dumps({"id": f"irony-{i}", "text": r["text"], "label": bool(r["label"])}) + "\n")

# The HF entry is a loader script newer `datasets` refuses; this CSV is what it wraps.
import csv, io, urllib.request
BANK_URL = "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data/test.csv"
bank = list(csv.DictReader(io.StringIO(urllib.request.urlopen(BANK_URL, timeout=60).read().decode("utf-8"))))
names = sorted({r["category"] for r in bank})
assert len(names) == 77, len(names)
with open(OUT / "banking77.labels.json", "w", encoding="utf-8") as f:
    json.dump(names, f)
with open(OUT / "banking77.jsonl", "w", encoding="utf-8") as f:
    for i, r in enumerate(sample(bank, N)):
        f.write(json.dumps({"id": f"bank-{i}", "text": r["text"], "label": r["category"]}) + "\n")

for p in sorted(OUT.glob("*.jsonl")):
    rows = [json.loads(l) for l in p.open(encoding="utf-8")]
    labels = [r["label"] for r in rows]
    top = max(set(map(str, labels)), key=lambda x: sum(str(l) == x for l in labels))
    print(p.name, len(rows), "majority:", top, sum(str(l) == top for l in labels))
