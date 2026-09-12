"""
backfill_labels.py  -  Recover scenes missing from a label CSV.  Owner: Soum.

    python pipeline/detect/backfill_labels.py --parts 1,2 --out data/labels/features_train.csv

The Parts I+II label run was executed with 12 workers while the tile cache was
building on the same machine, and 55 of 2,570 scenes are absent from the CSV.
Each worker holds a full-scene bool mask per detected region, so a scene with
~100 regions needs ~400 MB in one worker; enough of those at once and the
allocator gives up. The failures were caught and logged, not silent.

Two different things produce an absent scene and this tells them apart:
  - the detector legitimately found NO regions        -> contributes no rows, correct
  - the scene errored (out of memory, unreadable)     -> rows were lost, a real gap

Re-runs only the missing scenes, with a low worker count, and APPENDS. The
existing rows are never rewritten, so a backfill cannot corrupt what is already
there. Idempotent: run it twice and the second run finds nothing to do.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd                                                    # noqa: E402
from pipeline.detect.make_labels import (                              # noqa: E402
    _build_jobs, _scene_rows, _init_worker, FIELDNAMES, CLASSES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="1,2")
    ap.add_argument("--out", default=os.path.join(_ROOT, "data", "labels",
                                                  "features_train.csv"))
    ap.add_argument("--overlap-threshold", type=float, default=0.25)
    ap.add_argument("--workers", type=int, default=4,
                    help="deliberately low — this is the failure being repaired")
    a = ap.parse_args()

    if not os.path.exists(a.out):
        raise SystemExit(f"{a.out} not found — run make_labels.py first")

    have = set(pd.read_csv(a.out)["scene_id"].unique())
    jobs = _build_jobs(a.parts)
    missing = [j for j in jobs if j[0] not in have]

    print(f"\n  CSV has {len(have)} of {len(jobs)} scenes — {len(missing)} missing")
    if not missing:
        print("  nothing to backfill.")
        return
    print("  by class:", dict(Counter(j[1] for j in missing)))
    print(f"  re-running with {a.workers} workers\n")

    added_rows = 0
    empty_scenes, errored = [], []
    pos = 0
    with open(a.out, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        with ProcessPoolExecutor(max_workers=a.workers, initializer=_init_worker,
                                 initargs=(a.overlap_threshold,)) as pool:
            for sid, rows, nreg, dropped, cols, err in pool.map(_scene_rows, missing,
                                                                chunksize=1):
                if err:
                    errored.append((sid, err.splitlines()[0]))
                    print(f"  [STILL FAILING] {sid}: {err.splitlines()[0]}")
                    continue
                if not rows:
                    empty_scenes.append(sid)
                    continue
                for r in rows:
                    w.writerow(r)
                    added_rows += 1
                    pos += int(r["label"] == 1)
                print(f"  [ok] {sid:<22} {nreg:>3} regions, {len(rows)} rows", flush=True)

    print()
    print("=" * 66)
    print("  BACKFILL COMPLETE")
    print("=" * 66)
    print(f"  rows appended            : {added_rows}  ({pos} label=1)")
    print(f"  scenes with no detections: {len(empty_scenes)}  (valid — not a failure)")
    print(f"  scenes still failing     : {len(errored)}")
    for sid, msg in errored:
        print(f"    {sid}: {msg}")

    df = pd.read_csv(a.out)
    print()
    print(f"  {a.out} now: {len(df)} rows, {int(df.label.sum())} positive, "
          f"{df.scene_id.nunique()} scenes")
    for c in CLASSES:
        sub = df[df["class"] == c]
        print(f"    {c:<12}: {len(sub):>6} rows  ({int(sub.label.sum())} label=1)")
    bad = [c for c in ("Lookalike", "No oil") if int(df[df['class'] == c].label.sum()) != 0]
    if bad:
        print(f"  [FAIL] {bad} gained label=1 rows — the hard-negative rule is broken.")
    else:
        print("  hard-negative rule intact: Lookalike and No oil carry 0 positives.")


if __name__ == "__main__":
    main()
