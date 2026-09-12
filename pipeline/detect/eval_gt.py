"""
eval_gt.py — run the v2 detector over every Part III scene and report what a
judge would ask: on how many Oil scenes did we produce a region on the oil,
and how many candidate regions do Lookalike / No-oil scenes generate.

Usage:
  python eval_gt.py data            # data/Images/{Oil,Lookalike,No oil}, data/Mask/...
  python eval_gt.py data --limit 20 # first 20 scenes per class (quick)
  python eval_gt.py data --t-high 2.5 --k-high 3.5   # try a tuning

Writes eval_summary.csv (one row per scene). Tune on Oil scenes 0-74, report
numbers on 75-149 — never tune and report on the same scenes.
"""
import argparse, csv, glob, os, time
import numpy as np
import rasterio
from darkspot_v2 import load_scene, detect_array

ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("--limit", type=int, default=None)
ap.add_argument("--t-high", type=float, default=2.0)
ap.add_argument("--t-low", type=float, default=1.0)
ap.add_argument("--k-high", type=float, default=3.0)
ap.add_argument("--k-low", type=float, default=1.5)
ap.add_argument("--out", default="eval_summary.csv")
a = ap.parse_args()
kw = dict(t_high_db=a.t_high, t_low_db=a.t_low, k_high=a.k_high, k_low=a.k_low)

rows = []
for cls in ("Oil", "Lookalike", "No oil"):
    imgs = sorted(glob.glob(os.path.join(a.root, "Images", cls, "*.tif")))[: a.limit]
    t0 = time.time()
    for p in imgs:
        sid = os.path.splitext(os.path.basename(p))[0]
        mp = os.path.join(a.root, "Mask", cls, f"{sid}_segmentation.tif")
        db, px = load_scene(p)
        regions, dbg = detect_array(db, px, return_debug=True, **kw)
        row = {"class": cls, "scene": sid, "n_regions": len(regions), "land_frac": round(dbg["land_frac"], 3),
               "t_high": round(dbg["t_high"], 2), "noise_mad": round(dbg["noise_mad"], 2),
               "gt_px": 0, "gt_recall": "", "hit_regions": "", "best_overlap": ""}
        if cls == "Oil" and os.path.exists(mp):
            with rasterio.open(mp) as m:
                gt = m.read(1) > 0
            row["gt_px"] = int(gt.sum())
            if gt.any():
                row["gt_recall"] = round(float(dbg["mask"][gt].mean()), 3)
                ov = [(r["mask"] & gt).sum() / r["area_px"] for r in regions]
                row["hit_regions"] = int(sum(o >= 0.3 for o in ov))
                row["best_overlap"] = round(max(ov), 2) if ov else 0
        rows.append(row)
        print(f"{cls:9s} {sid}  regions={row['n_regions']:3d}  recall={row['gt_recall']}  hits={row['hit_regions']}  land={row['land_frac']:.0%}")
    print(f"--- {cls}: {len(imgs)} scenes in {time.time()-t0:.0f}s")

with open(a.out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

oil = [r for r in rows if r["class"] == "Oil" and r["gt_recall"] != ""]
if oil:
    rec = np.array([r["gt_recall"] for r in oil]); hit = np.array([r["hit_regions"] > 0 for r in oil])
    print(f"\nOIL scenes ({len(oil)}): scene-level hit rate (>=1 region on the oil) = {hit.mean():.1%}; "
          f"median pixel recall = {np.median(rec):.1%}; scenes with recall<10% = {(rec < 0.1).sum()}")
for cls in ("Lookalike", "No oil"):
    n = [r["n_regions"] for r in rows if r["class"] == cls]
    if n:
        print(f"{cls}: median candidate regions/scene = {np.median(n):.0f}, max = {max(n)}  (these are the classifier's hard negatives)")
print(f"wrote {a.out}")
