#!/usr/bin/env bash
# Age engine v2 -- OpenDrift's two models for every published case (D45, plan Part C).
#   bash pipeline/drift/run_opendrift_all.sh [JOBS] [CASE ...]
# Writes out/opendrift_age_<case>.npz and out/opendrift_origin_<case>.npz, which run.py and
# pool_models.py pick up. Members run in parallel inside each script.
set -euo pipefail
JOBS=${1:-4}
shift || true
CASES=${*:-"case-jacksonville-2024 case-farallones-2023 case-gulf-alaska-2023 case-huntington-2021 case-jamnagar-2024 case-mumbai-2023"}
for C in $CASES; do
  echo "=== $C  $(date -u +%H:%M:%S)"
  if [ ! -f "pipeline/drift/out/opendrift_age_$C.npz" ]; then
    venv/Scripts/python pipeline/drift/age.py --case "$C" --real --request-only
    odenv/Scripts/python -W ignore pipeline/drift/opendrift_age.py --case "$C" --jobs "$JOBS"
  fi
  odenv/Scripts/python -W ignore pipeline/drift/opendrift_origin.py --case "$C" --jobs "$JOBS"
done
echo "=== done $(date -u +%H:%M:%S)"
