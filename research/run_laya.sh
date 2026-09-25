#!/usr/bin/env bash
# Laya over the frozen tabular sets first (clean for every model), then the text sets (descriptive).
cd "$(dirname "$0")" || exit 1
PY=C:/Projects/_scratch/jev-open/.venv-laya/Scripts/python.exe
export HF_HUB_DISABLE_SYMLINKS_WARNING=1
for s in telco bank telco_hostile sst2 irony; do
  "$PY" calibrate_open.py laya "$s" "${LAYA_TAG:-laya1}" 2>&1 | grep -v -E "RuntimeWarning|return Agent|Fetching"
  echo "RC $s ${PIPESTATUS[0]}"
done
echo "LAYA-RUN-DONE"
