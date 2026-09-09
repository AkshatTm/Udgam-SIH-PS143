#!/usr/bin/env python3
"""
Stage 3 — Phase 1 checkpoint plot. Owner: Jaiveer.

    python pipeline/attribute/plot_tracks.py --parquet data/ais/gulf.parquet

Draws the longest reconstructed tracks so you can judge them with your eyes.
This is the checkpoint in docs/05_JAIVEER_AIS.md: post the picture in the group.

**What you are looking for.** Real shipping is smooth. Tracks should run as clean
lines along lanes and into ports, curving gently, bunching into corridors.

**What means something is wrong:**
  - teleporting zigzags, or a track that jumps across the map and back — usually a
    lat/lon swap somewhere, or two vessels sharing one MMSI
  - everything crammed into a tiny blob — your bbox is too small
  - a handful of lonely lines in open water — your bbox caught empty ocean
  - tracks that all start and stop at the box edge with nothing inside — the box
    is sitting between shipping lanes rather than on one

Long gaps are drawn as dotted segments. That is not a rendering flourish: a gap
is the `gap` scoring component, and seeing where they fall tells you whether the
30-minute interpolation ceiling is set sensibly for this data.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tracks import MAX_INTERP_GAP_MIN, load_tracks

HERE = Path(__file__).resolve().parent

TYPE_COLOR = {
    "tanker": "#d1495b",
    "cargo": "#0f7173",
    "fishing": "#e3a008",
    "passenger": "#6247aa",
    "other": "#8d99ae",
}


def pick_sample(tracks, n):
    """Spread the sample across vessel types, longest first within each.

    Taking the n longest tracks outright looks tidy and lies: the longest tracks are
    the ones reporting most often, which in a ship channel means tugs and pilot boats.
    You end up with a one-colour picture of a mixed fleet. Round-robin across the
    types present so the plot shows the traffic you actually filtered.
    """
    by_type = {}
    for t in tracks.values():
        by_type.setdefault(t.vessel_type, []).append(t)
    for group in by_type.values():
        group.sort(key=len, reverse=True)

    order = sorted(by_type, key=lambda k: -len(by_type[k]))
    chosen, i = [], 0
    while len(chosen) < n and any(len(by_type[k]) > i for k in order):
        for k in order:
            if len(by_type[k]) > i and len(chosen) < n:
                chosen.append(by_type[k][i])
        i += 1
    return chosen


def main():
    ap = argparse.ArgumentParser(description="Plot reconstructed AIS tracks.")
    ap.add_argument("--parquet", required=True, help="output of ingest.py")
    ap.add_argument("--n", type=int, default=50, help="how many tracks (default 50)")
    ap.add_argument("--out", default=str(HERE / "out" / "tracks_check.png"))
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    tracks = load_tracks(args.parquet)
    if not tracks:
        raise SystemExit("no tracks — check the ingest output")

    chosen = pick_sample(tracks, args.n)

    fig, ax = plt.subplots(figsize=(11, 9))
    ax.set_facecolor("#0e1117")
    fig.patch.set_facecolor("#0e1117")

    gap_count = 0
    for t in chosen:
        colour = TYPE_COLOR.get(t.vessel_type, TYPE_COLOR["other"])
        # split the track at every long silence so we never draw a line we can't justify
        seg_lon, seg_lat = [t.lon[0]], [t.lat[0]]
        for i, mins in enumerate(t.gaps_minutes, start=1):
            if mins > MAX_INTERP_GAP_MIN:
                ax.plot(seg_lon, seg_lat, color=colour, lw=1.1, alpha=0.9, solid_capstyle="round")
                ax.plot([t.lon[i - 1], t.lon[i]], [t.lat[i - 1], t.lat[i]],
                        color=colour, lw=0.7, alpha=0.35, ls=":")
                gap_count += 1
                seg_lon, seg_lat = [], []
            seg_lon.append(t.lon[i])
            seg_lat.append(t.lat[i])
        if seg_lon:
            ax.plot(seg_lon, seg_lat, color=colour, lw=1.1, alpha=0.9, solid_capstyle="round")

    for t in chosen:
        ax.plot(t.lon[0], t.lat[0], "o", ms=2.5,
                color=TYPE_COLOR.get(t.vessel_type, TYPE_COLOR["other"]), alpha=0.8)

    present = {t.vessel_type for t in chosen}
    ax.legend(handles=[plt.Line2D([], [], color=TYPE_COLOR[k], lw=2, label=k)
                       for k in TYPE_COLOR if k in present],
              loc="upper right", facecolor="#161b22", edgecolor="#30363d",
              labelcolor="#c9d1d9", fontsize=9)

    span = max(t.end for t in chosen) - min(t.start for t in chosen)
    title = args.title or (f"{len(chosen)} AIS tracks, sampled across vessel types · "
                           f"{min(t.start for t in chosen):%Y-%m-%d %H:%MZ} "
                           f"+{span.total_seconds() / 3600:.0f} h")
    ax.set_title(title, color="#c9d1d9", fontsize=11, pad=12)
    ax.set_xlabel("longitude", color="#8b949e", fontsize=9)
    ax.set_ylabel("latitude", color="#8b949e", fontsize=9)
    ax.tick_params(colors="#8b949e", labelsize=8)
    for s in ax.spines.values():
        s.set_color("#30363d")
    ax.grid(color="#21262d", lw=0.5)
    ax.set_aspect("equal", adjustable="datalim")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())

    mix = {}
    for t in chosen:
        mix[t.vessel_type] = mix.get(t.vessel_type, 0) + 1
    print(f"wrote {out}")
    print("  mix: " + ", ".join(f"{k} {v}" for k, v in
                                sorted(mix.items(), key=lambda kv: -kv[1])))
    print(f"  {len(chosen)} tracks drawn, {gap_count} gaps > {MAX_INTERP_GAP_MIN} min shown dotted")
    print("  look at it before you post it: smooth lines along lanes = good,")
    print("  teleporting zigzags = a lat/lon swap or one MMSI shared by two vessels")


if __name__ == "__main__":
    main()
