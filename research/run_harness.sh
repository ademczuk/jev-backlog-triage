#!/usr/bin/env bash
# PROTOCOL-HARNESS.md run: every set once, serially, then one retry pass over failed rows.
cd "$(dirname "$0")/.." || exit 1
for s in routing tools injection; do
  JEV_CONCURRENCY=1 node --env-file-if-exists=.env.local --experimental-strip-types research/calibrate.ts "$s" h1 2>&1 | grep -v ExperimentalWarning
  echo "RC $s ${PIPESTATUS[0]}"
done
for s in routing tools injection; do
  f=research/results/$s.h1.jsonl
  ids=$(python -c "import json,sys;print(','.join(r['id'] for r in map(json.loads,open(sys.argv[1],encoding='utf-8')) if 'error' in r))" "$f")
  [ -z "$ids" ] && { echo "no failed rows in $s"; continue; }
  echo "retrying $(echo "$ids" | tr ',' '\n' | wc -l) failed rows in $s"
  JEV_CONCURRENCY=1 JEV_ONLY_IDS="$ids" node --env-file-if-exists=.env.local --experimental-strip-types research/calibrate.ts "$s" h1retry 2>&1 | grep -v ExperimentalWarning
done
echo "HARNESS-RUN-DONE"
