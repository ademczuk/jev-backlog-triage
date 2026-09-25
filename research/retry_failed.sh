#!/usr/bin/env bash
# Re-run once every call that failed in the frozen tabular run (PROTOCOL.md), serially.
cd "$(dirname "$0")/.." || exit 1
for f in research/results/{telco,bank,telco_hostile}.r*.jsonl; do
  case "$f" in *retry.jsonl) continue ;; esac
  base=$(basename "$f" .jsonl); set=${base%.*}; tag=${base##*.}
  ids=$(python -c "import json,sys;print(','.join(r['id'] for r in map(json.loads,open(sys.argv[1],encoding='utf-8')) if 'error' in r))" "$f")
  [ -z "$ids" ] && continue
  echo "retrying $(echo "$ids" | tr ',' '\n' | wc -l) failed rows in $base"
  JEV_CONCURRENCY=1 JEV_ONLY_IDS="$ids" node --env-file-if-exists=.env.local --experimental-strip-types research/calibrate.ts "$set" "${tag}retry" 2>&1 | grep -v "done,"
done
