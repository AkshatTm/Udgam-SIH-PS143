#!/usr/bin/env python3
"""
sync_web_cases.py — copy case bundles into the frontend's static folder. Owner: Akshat.

    python scripts/sync_web_cases.py
    python scripts/sync_web_cases.py --clean        # drop cases no longer in index.json
    python scripts/sync_web_cases.py --dry-run

The frontend fetches `/cases/<id>/...` as static files and never calls Python (Master §4.1).
Next.js serves `web/public/`, so the bundles have to physically sit in `web/public/cases/`.
That folder is gitignored — it is build output, a copy of `cases/` which is the real artefact.

**This is the producer side of the seam, not the frontend.** It writes only into gitignored
build output and touches nothing in `web/` that anyone owns. Run it after any stage publishes
into a bundle, then reload the browser.

WHAT IT DOES NOT COPY: `sar_vv_vh.tif`. That file is Soum's 2-band float32 input and it is
~95% of the bytes in the repo (roughly 123 MB across the library). The browser never reads it —
the display raster is `sar.png`. Copying it would quadruple the dev server's static folder for
no pixels on screen.

It also skips `cases/_archive/` entirely: archived cases are not in `index.json`, not validated,
and must never appear in the gallery.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "cases"
DST = REPO / "web" / "public" / "cases"

# The browser reads these. Anything else in a bundle is for the pipeline, not the page.
COPY_SUFFIXES = {".json", ".geojson", ".png"}
SKIP_NAMES = {"sar_vv_vh.tif"}


def bundle_files(case_dir):
    for f in sorted(case_dir.iterdir()):
        if not f.is_file() or f.name in SKIP_NAMES:
            continue
        if f.suffix.lower() in COPY_SUFFIXES:
            yield f


def main():
    ap = argparse.ArgumentParser(description="Copy case bundles into web/public/cases/")
    ap.add_argument("--clean", action="store_true",
                    help="remove synced cases that are no longer listed in cases/index.json")
    ap.add_argument("--dry-run", action="store_true", help="print, copy nothing")
    a = ap.parse_args()

    index_path = SRC / "index.json"
    if not index_path.exists():
        raise SystemExit(f"{index_path} not found — nothing to sync.")
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"cases/index.json is not valid JSON: {e}")

    listed = index.get("cases") or []
    if not listed:
        raise SystemExit("cases/index.json lists no cases.")

    print(f"Syncing {len(listed)} case(s) -> {DST.relative_to(REPO)}")
    print("-" * 70)

    total_files = total_bytes = 0
    missing = []
    for cid in listed:
        case_dir = SRC / cid
        if not case_dir.is_dir():
            missing.append(cid)
            print(f"  {cid:<30} MISSING on disk — index.json lists a case that isn't there")
            continue
        out = DST / cid
        n = b = 0
        for f in bundle_files(case_dir):
            if not a.dry_run:
                out.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, out / f.name)
            n += 1
            b += f.stat().st_size
        total_files += n
        total_bytes += b
        has_det = (case_dir / "detections.geojson").exists()
        note = "" if has_det else "   (no detections yet — Stage 1 pending)"
        print(f"  {cid:<30} {n:2d} file(s)  {b/1e6:6.2f} MB{note}")

    if not a.dry_run:
        DST.mkdir(parents=True, exist_ok=True)
        shutil.copy2(index_path, DST / "index.json")

    if a.clean and not a.dry_run and DST.exists():
        keep = set(listed)
        for d in DST.iterdir():
            if d.is_dir() and d.name not in keep:
                shutil.rmtree(d)
                print(f"  removed stale {d.name}")

    print("-" * 70)
    print(f"{total_files} file(s), {total_bytes/1e6:.1f} MB"
          + ("  (dry run — nothing written)" if a.dry_run else ""))
    if missing:
        print(f"\n{len(missing)} case(s) in index.json are not on disk: {', '.join(missing)}")
        print("The gallery renders those as an error card rather than hiding them.")
        return 1
    print("\nNow:  cd web && npm run dev")
    print("Re-run this after any stage publishes into a bundle — the browser reads the copy,")
    print("not cases/, so an un-synced bundle looks stale rather than broken.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
