#!/usr/bin/env bash
# Age engine v2 -- the full synthetic-twin programme, every field, every step.
# Two venvs on purpose: OpenDrift never enters the project venv (requirements-opendrift.txt).
#
#   bash pipeline/drift/run_twins.sh [N_PER_FIELD] [JOBS]
#
# Resumable: `score` skips twins already in scored.json. Delete out/twins/<field>/ to redo one.
set -euo pipefail
N=${1:-24}
JOBS=${2:-5}
PY=venv/Scripts/python
OD=odenv/Scripts/python
FIELDS="case-farallones-2023 case-gulf-alaska-2023 case-huntington-2021 case-jacksonville-2024 case-jamnagar-2024 case-mumbai-2023"
for F in $FIELDS; do
  echo "=== $F  $(date -u +%H:%M:%S)"
  $PY pipeline/drift/age_twins.py make --field "$F" --n "$N"
  $OD -W ignore pipeline/drift/opendrift_twins.py --field "$F"
  $PY pipeline/drift/age_twins.py prepare --field "$F"
  $OD -W ignore pipeline/drift/opendrift_age.py --case "$F" --batch --members 1 --elements 150
  $PY pipeline/drift/age_twins.py score --field "$F" --jobs "$JOBS"
done
$PY pipeline/drift/age_twins.py calibrate
echo "=== done $(date -u +%H:%M:%S)"
