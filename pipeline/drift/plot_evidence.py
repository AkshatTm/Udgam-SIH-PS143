"""Stage 2 evidence set, figures F2.1-F2.8 (Anushka final-day brief, P1).

Reads only files already on disk -- it runs no physics. Every caption prints its source path and n.

    python pipeline/drift/eval_growth.py --case <id>      # once per case, feeds F2.1
    python pipeline/drift/plot_evidence.py

Writes docs/evaluation/figures/stage2/F2.*.png (matplotlib, 200 dpi). Bundles are read, never written.
"""
import json, re, textwrap
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIG = REPO / "docs/evaluation/figures/stage2"
DATA = FIG / "data"

# presentation order (strongest first); colour follows the case in every figure
CASES = ["case-jacksonville-2024", "case-farallones-2023", "case-jamnagar-2024",
         "case-mumbai-2023", "case-gulf-alaska-2023", "case-huntington-2021"]
LABEL = {"case-jacksonville-2024": "Jacksonville", "case-farallones-2023": "Farallones",
         "case-jamnagar-2024": "Jamnagar", "case-mumbai-2023": "Mumbai",
         "case-gulf-alaska-2023": "Gulf of Alaska", "case-huntington-2021": "Huntington"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
COLOR = dict(zip(CASES, SERIES))
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0"
NULL_GREY = "#d9d8d3"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "legend.frameon": False,
})


def load(p):
    return json.loads((REPO / p).read_text(encoding="utf-8"))


def caption(fig, claim, source, n, y=0.02, width=150):
    body = textwrap.fill(claim, width)
    src = textwrap.fill(f"Source: {source}   ·   n = {n}", width)
    fig.text(0.02, y, body + "\n" + src, fontsize=8.2, color=INK2, va="bottom", ha="left",
             linespacing=1.45)


def save(fig, name):
    out = FIG / name
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print("wrote", out.relative_to(REPO))


def km_xy(lon, lat, lon0, lat0):
    return (np.asarray(lon) - lon0) * 111.32 * np.cos(np.radians(lat0)), (np.asarray(lat) - lat0) * 110.574


# ---------------------------------------------------------------- F2.1 uncertainty growth
def f21():
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.2), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.87, top=0.84, bottom=0.25, wspace=0.08)
    fig.suptitle("F2.1  The answer is a cloud, never a point — and it widens most where the ocean carries the slick furthest",
                 x=0.02, ha="left", fontsize=13, fontweight="bold")
    n_pts = None
    for key, ax, title in [("radius_50_km", axes[0], "r50 — half the ensemble endpoints lie within"),
                           ("radius_90_km", axes[1], "r90 — 90% of the ensemble endpoints lie within")]:
        for c in CASES:
            g = load(f"docs/evaluation/figures/stage2/data/growth_{c}.json")
            assert g["reproduces_shipped"], c
            n_pts = g["n_points_per_hour"]
            h = [r["hours_back"] for r in g["growth"]]
            v = [r[key] for r in g["growth"]]
            ax.plot(h, v, color=COLOR[c], lw=2)
            ax.plot(h[-1], v[-1], "o", ms=5, color=COLOR[c], mec=SURFACE, mew=1.5)
        ax.set_yscale("log")
        ax.set_ylim(0.3, 80)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 6))
        ax.set_xlabel("hours back from detection (t0 = 0)")
        ax.set_title(title, loc="left", fontsize=10.5, color=INK)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}"))
    axes[0].set_ylabel("radius around the cloud centroid (km, log scale)")
    ax = axes[1]
    ax.axhline(40, color=INK, lw=1.2, ls=(0, (5, 3)))
    ax.text(0.4, 44, "abstain trigger: r90 > 40 km  →  Stage 3 names no suspects", fontsize=8.5, color=INK)
    # direct labels at the right edge, nudged apart
    ends = []
    for c in CASES:
        g = load(f"docs/evaluation/figures/stage2/data/growth_{c}.json")
        ends.append([c, g["growth"][-1]["radius_90_km"]])
    ends.sort(key=lambda e: e[1])
    last = 0
    for c, v in ends:
        y = max(np.log10(v), last + 0.1)
        last = y
        ax.annotate(f"{LABEL[c]}  {v:.1f} km", xy=(24, v), xytext=(24.6, 10 ** y), fontsize=8.5,
                    color=INK, va="center", annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=COLOR[c], lw=1))
    handles = [plt.Line2D([], [], color=COLOR[c], lw=2) for c in CASES]
    fig.legend(handles, [LABEL[c] for c in CASES], loc="upper left", ncol=6, bbox_to_anchor=(0.02, 0.93),
               fontsize=9)
    caption(fig,
            "Across the 50 runs of our uncertainty budget, spread tracks distance travelled: Jacksonville (149 km of Gulf Stream) roughly doubles its r90 over 24 h, "
            "Gulf of Alaska and Mumbai grow steadily, and Farallones and Jamnagar stay nearly flat because the field does not stretch the cloud. It is not monotonic everywhere — Huntington dips after ~19 h. "
            "No case crosses the 40 km refusal line at the published 24 h span. Spread is precision, not accuracy: "
            "there is no ground truth for origin position. Hour 0 is the size of the seeded slick itself, not zero.",
            "docs/evaluation/figures/stage2/data/growth_<case>.json — re-run of run.py --real --particles 3000 --runs 50 "
            "(seed 143) with hourly frames kept; each 24 h value checked against cases/<case>/origin.json (all six reproduce)",
            f"6 cases × 50 runs × 3000 particles = {n_pts:,} endpoints per case per hour", y=0.02, width=165)
    save(fig, "F2.1_uncertainty_growth.png")


# ---------------------------------------------------------------- F2.2 integrator validation
def f22():
    txt = (DATA / "drift_tests_2026-09-16.txt").read_text(encoding="utf-8")
    passes = re.findall(r"^\s+PASS\s+(\w+)\s+(.*)$", txt, re.M)
    fails = re.findall(r"^\s+FAIL\s+(\w+)", txt, re.M)
    m = re.search(r"(\d+)/(\d+) tests passed\s+\((\d+)/(\d+) individual assertions\)", txt)
    suites_ok, suites, a_ok, a_n = map(int, m.groups())

    def detail(tid):
        mm = re.search(rf"PASS\s+{tid}\s+.*\n\s+(.*)", txt)
        return mm.group(1).strip()

    rows = [
        ("1a", "Straight-line advection, 0.5 m/s east, 10 h", "18.0000 km vs 18.0 km analytic", "0.000% error"),
        ("2a", "24 h forward then 24 h backward, varying field", "closes to 0.0001 km", "after 16.21 km outbound (2b)"),
        ("7f", "Same round trip at 59.56° N (Gulf of Alaska)", "closes to 0.0004 km", "after 21.00 km outbound"),
        ("7a", "Negative longitude: 0.5 m/s east at −118° E", "18.0000 km, 0.000% error", "stays west of Greenwich"),
        ("7c", "Antimeridian crossing", "179.90 → −179.907", "wraps in exactly one place"),
        ("3a", "Wind only, 10 m/s", "0.300000 m/s drift", "coefficient 0.0300"),
        ("1b", "u/v not swapped", "north component +0.000000 km", ""),
        ("4b", "Mis-scaled field (50 m/s) rejected", "raises: > 3.0 m/s limit", "the ÷1000 guard"),
        ("5d", "Origin grid row 0 is NORTH", "90.0% of mass in top half", "for a north-offset cloud"),
        ("10c", "Widened ensemble trips abstain", "r90 144.7 km → abstain = true", "honest σ: r90 22.9 km, no abstain (10d)"),
    ]
    for tid, *_ in rows:
        detail(tid)  # raises if the test line is missing -- figure refuses rather than inventing
    fig = plt.figure(figsize=(12, 6.6))
    fig.suptitle("F2.2  The integrator is exact — our uncertainty lives in the ocean data, not the code",
                 x=0.02, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.02, 0.885, f"{suites_ok}/{suites} test suites  ·  {a_ok}/{a_n} assertions PASS  ·  "
             f"{len(fails)} failures  ·  run 16 Sept 2026", fontsize=11, color=INK)
    ax = fig.add_axes([0.02, 0.2, 0.96, 0.65]); ax.axis("off")
    cols = [0.0, 0.06, 0.46, 0.73]
    heads = ["test", "what is checked", "measured", "note"]
    for x, h in zip(cols, heads):
        ax.text(x, 1.0, h.upper(), fontsize=8.5, color=MUTED, fontweight="bold", va="top")
    for i, (tid, what, meas, note) in enumerate(rows):
        y = 0.92 - i * 0.092
        ax.axhline(y + 0.045, color=GRID, lw=0.8)
        ax.text(cols[0], y, tid, fontsize=10, color=INK2, va="center", family="DejaVu Sans Mono")
        ax.text(cols[1], y, what, fontsize=10, color=INK, va="center")
        ax.text(cols[2], y, meas, fontsize=10, color=INK, va="center", fontweight="bold")
        ax.text(cols[3], y, "✓ PASS  " + note, fontsize=9, color=INK2, va="center")
    caption(fig,
            "RK2 at 15-minute steps closes a 24 h round trip to 0.1 metres. The integration scheme is not a "
            "meaningful error source; what limits the answer is the resolution of the freely available current field. "
            f"The brief's '5 suites / 20 assertions' is out of date — the suite has grown to {suites} suites, {a_n} assertions.",
            "docs/evaluation/figures/stage2/data/drift_tests_2026-09-16.txt (verbatim output of python pipeline/drift/tests.py)",
            f"{a_n} assertions in {suites} suites; 10 shown", y=0.03)
    save(fig, "F2.2_integrator_validation.png")


# ---------------------------------------------------------------- F2.3 error budget
OPENDRIFT = {  # docs/STAGE2_NUMBERS.md §8.4: travel km, origin centroid separation m, % of path
    "case-jacksonville-2024": (140.2, 550.3, 0.393), "case-farallones-2023": (35.5, 119.7, 0.345),
    "case-jamnagar-2024": (16.7, 113.4, 0.677), "case-mumbai-2023": (16.7, 79.7, 0.477),
    "case-gulf-alaska-2023": (12.0, 31.3, 0.261), "case-huntington-2021": (6.2, 104.3, 1.050),
}


def budget(c):
    z = np.load(REPO / f"pipeline/drift/out/ensemble_{c}.npz")
    E = z["endpoints"].reshape(len(z["wind_coeff"]), -1, 2)
    lat0, lon0 = E[..., 1].mean(), E[..., 0].mean()
    x, y = km_xy(E[..., 0], E[..., 1], lon0, lat0)
    P = np.stack([x, y], -1)
    total = P.reshape(-1, 2).var(0).sum()
    within = np.mean([P[r].var(0).sum() for r in range(P.shape[0])])
    C = P.mean(1)
    w, s = z["wind_coeff"], z["current_scale"]
    X = np.column_stack([np.ones(len(w)), w - w.mean(), s - s.mean()])
    beta = np.linalg.lstsq(X, C, rcond=None)[0]
    v_wind = np.outer(X[:, 1], beta[1]).var(0).sum()
    v_cur = np.outer(X[:, 2], beta[2]).var(0).sum()
    between = C.var(0).sum()
    other = max(between - v_wind - v_cur, 0.0)
    parts = np.array([v_cur, v_wind, within, other])
    return parts / parts.sum(), total, P.shape[0] * P.shape[1]


def f23():
    labels = ["Current field (±15% magnitude, σ = 0.15)", "Wind coefficient U(0.025, 0.035)",
              "Within-run: slick extent + seed jitter", "Unexplained / interaction"]
    colors = ["#2a78d6", "#eb6834", "#b9b8b2", "#e6e5e0"]
    fig, ax = plt.subplots(figsize=(12, 6.6))
    fig.subplots_adjust(left=0.13, right=0.74, top=0.80, bottom=0.33)
    fig.suptitle("F2.3  Where the spread comes from: the current field on two cases, the wind on one, the slick's own size on three",
                 x=0.02, ha="left", fontsize=12.5, fontweight="bold")
    n = None
    for i, c in enumerate(CASES):
        fr, total, n = budget(c)
        left = 0
        for j, f in enumerate(fr):
            ax.barh(i, f * 100, left=left, color=colors[j], height=0.62, edgecolor=SURFACE, linewidth=2)
            if f > 0.06:
                ax.text(left + f * 50, i, f"{f*100:.0f}%", ha="center", va="center", fontsize=8.5,
                        color="white" if j < 2 else INK)
            left += f * 100
        km, sep, pct = OPENDRIFT[c]
        o = load(f"cases/{c}/origin.json")
        ax.text(102, i, f"{sep:.0f} m  ({sep/1000/o['radius_50_km']*100:.1f}% of r50)", va="center", fontsize=8.5, color=INK2)
    ax.text(102, -0.75, "Integration scheme:\nRK2 vs OpenDrift RK4\norigin separation", fontsize=8.2, color=MUTED, va="bottom")
    ax.set_yticks(range(len(CASES)), [LABEL[c] for c in CASES])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of the pooled endpoint variance at 24 h (%)")
    ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=k) for k in colors]
    fig.legend(handles, labels, loc="upper left", ncol=2, bbox_to_anchor=(0.12, 0.925), fontsize=9)
    fig.text(0.13, 0.225, "Omitted physics (vertical mixing, weathering, Stokes drift) is not modelled, so it cannot appear in a measured bar. "
             "\nIt is ranked third and matters only past ~48 h; our rewind is 24 h.", fontsize=8.5, color=INK)
    caption(fig,
            "Variance of the pooled 24 h endpoints split into: the spread of each run's centroid explained by that run's current scale and "
            "wind coefficient (linear fit over the 50 runs), and the mean spread inside a run, which is mostly the slick's own length (Farallones 17 km). Averaged over the library the current term "
            "leads between runs; on Gulf of Alaska the wind term leads (53%), which independently agrees with its wind_share of 0.73 from a separate decomposition (F2.5). "
            "On three of six cases (Farallones, Jamnagar, Huntington) the largest block is how large the slick already is, and a finer current field would not tighten those. "
            "A finer regional current model tightens the cases where the current term leads (Jacksonville 91%, Mumbai 50%) — a data argument, not a code argument. "
            "The ±15% current perturbation is our proxy for current-field error.",
            "pipeline/drift/out/ensemble_<case>.npz (endpoints, wind_coeff, current_scale); integration column from docs/STAGE2_NUMBERS.md §8.4",
            f"6 cases × {n:,} endpoints (50 runs × 3000)", y=0.02, width=165)
    save(fig, "F2.3_error_budget.png")


# ---------------------------------------------------------------- F2.4 OpenDrift agreement
def f24():
    fig, ax = plt.subplots(figsize=(11, 6.6))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.86, bottom=0.25)
    fig.suptitle("F2.4  Single-run trajectory check: OpenDrift (RK4) puts the origin 31–550 m from our RK2",
                 x=0.02, ha="left", fontsize=12.5, fontweight="bold")
    xs = np.array([3, 300])
    ax.fill_between(xs, 1e-3, xs * 0.01, color="#2a78d6", alpha=0.08, lw=0)
    ax.plot(xs, xs * 0.01, color="#2a78d6", lw=1, ls=(0, (4, 3)))
    ax.text(200, 2.3, "1% of path travelled", color=INK2, fontsize=8.5, ha="right")
    for c in CASES:
        km, sep, pct = OPENDRIFT[c]
        r50 = load(f"cases/{c}/origin.json")["radius_50_km"]
        ax.plot([km, km], [sep / 1000, r50], color=COLOR[c], lw=1, alpha=0.5)
        ax.plot(km, sep / 1000, "o", ms=9, color=COLOR[c], mec=SURFACE, mew=2)
        ax.plot(km, r50, "o", ms=9, mfc=SURFACE, mec=COLOR[c], mew=2)
        off = {"case-mumbai-2023": (-10, -6, "right"), "case-jamnagar-2024": (10, 6, "left")}.get(c, (8, -4, "left"))
        ax.annotate(f"{LABEL[c]}\n{sep:.0f} m · {pct:.2f}% of path", (km, sep / 1000), xytext=off[:2],
                    textcoords="offset points", fontsize=8, color=INK, va="top", ha=off[2])
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(4, 260); ax.set_ylim(0.015, 40)
    fmt = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}")
    ax.xaxis.set_major_formatter(fmt); ax.yaxis.set_major_formatter(fmt)
    ax.set_xlabel("median distance travelled in the 24 h rewind (km, log)")
    ax.set_ylabel("km (log)")
    ax.legend([plt.Line2D([], [], marker="o", ls="", color=INK2, ms=8),
               plt.Line2D([], [], marker="o", ls="", mfc=SURFACE, mec=INK2, mew=2, ms=8)],
              ["origin centroid separation, one run each: our RK2 vs OpenDrift RK4", "our 50-run ensemble r50, for scale"],
              loc="upper left", fontsize=9)
    caption(fig,
            "Both models were fed the identical cached HYCOM + ERA5 field, 3000 particles, 24 h backward, pure advection, windage 0.03 on both. "
            "This is a single-run trajectory comparison of the origin centroid, not ensemble agreement: one run per model gives one endpoint set, "
            "so no OpenDrift spread exists and an r90 ratio is not computable. It shows the two integrators agree; the gap up to our ensemble r50 (hollow) "
            "comes from the uncertain inputs, not from the integrator. No bundle carries an opendrift_comparison block (absence is legal under §6.5).",
            "docs/STAGE2_NUMBERS.md §8.4 (python pipeline/drift/compare_opendrift.py --case <id>, OpenDrift 1.14.11); r50 from cases/<case>/origin.json",
            "6 spill cases × 3000 paired particles (t0 pairing residual 0.19–0.22 m)", y=0.02, width=160)
    save(fig, "F2.4_opendrift_agreement.png")


# ---------------------------------------------------------------- F2.5 wind share
def f25():
    fig, ax = plt.subplots(figsize=(11, 5.6))
    fig.subplots_adjust(left=0.14, right=0.95, top=0.84, bottom=0.27)
    fig.suptitle("F2.5  Which input each answer rests on: the same model, physically different regimes",
                 x=0.02, ha="left", fontsize=12.5, fontweight="bold")
    vals = [(c, load(f"cases/{c}/origin.json").get("wind_share")) for c in CASES]
    vals = [v for v in vals if v[1] is not None]
    vals.sort(key=lambda v: v[1])
    for i, (c, v) in enumerate(vals):
        ax.barh(i, v, color=COLOR[c], height=0.6, edgecolor=SURFACE, linewidth=2)
        ax.text(v + 0.012, i, f"{v:.2f}", va="center", fontsize=9.5, color=INK)
    ax.axvline(0.5, color=INK, lw=1.2, ls=(0, (5, 3)))
    ax.text(0.505, len(vals) - 0.45, "≥ 0.50 → run prints WIND-DOMINATED warning", fontsize=8.5, color=INK)
    ax.set_yticks(range(len(vals)), [LABEL[c] for c, _ in vals])
    ax.set_xlim(0, 1)
    ax.set_xlabel("wind_share = |0.03 × wind| / (|current| + |0.03 × wind|), mean over the 24 h control run  (fraction, 0–1)")
    ax.grid(axis="y", visible=False)
    ax.text(0.01, -0.95, "← current-driven: check against a current atlas", fontsize=8.5, color=INK2)
    ax.text(0.99, -0.95, "wind-driven: check against a wind reanalysis →", fontsize=8.5, color=INK2, ha="right")
    ax.set_ylim(-1.3, len(vals) - 0.2)
    caption(fig,
            "Jacksonville rides the Gulf Stream (0.04); Gulf of Alaska is set by a persistent easterly wind (0.73) with almost no resolved current. "
            "This is display-only — no Stage 3 component reads it — and it is omitted rather than zeroed on synthetic fields, "
            "because a 0 would claim a calm that was never measured.",
            "cases/<case>/origin.json → wind_share", f"{len(vals)} cases, each a mean over the 3000-particle control run, 97 frames",
            y=0.02, width=160)
    save(fig, "F2.5_wind_share.png")


# ---------------------------------------------------------------- F2.6 grid, not circle
def f26():
    c = "case-jacksonville-2024"
    o = load(f"cases/{c}/origin.json")
    b, (R, Cc) = o["bounds"], o["shape"]
    V = np.array(o["values"]).reshape(R, Cc)          # row 0 is NORTH
    clon, clat = o["centroid"]
    lon_e = np.linspace(b["west"], b["east"], Cc + 1)
    lat_e = np.linspace(b["north"], b["south"], R + 1)
    xe, _ = km_xy(lon_e, clat, clon, clat)
    _, ye = km_xy(clon, lat_e, clon, clat)
    lon_c = (lon_e[:-1] + lon_e[1:]) / 2; lat_c = (lat_e[:-1] + lat_e[1:]) / 2
    LON, LAT = np.meshgrid(lon_c, lat_c)
    X, Y = km_xy(LON, LAT, clon, clat)
    D = np.hypot(X, Y)
    pk = np.unravel_index(V.argmax(), V.shape)
    peak_km = D[pk]
    hp = V >= 0.5
    hp_out_cells = (D[hp] > o["radius_50_km"]).mean()
    hp_out_mass = V[hp & (D > o["radius_50_km"])].sum() / V[hp].sum()
    z = np.load(REPO / f"pipeline/drift/out/ensemble_{c}.npz")
    ex, ey = km_xy(z["endpoints"][:, 0], z["endpoints"][:, 1], clon, clat)
    ev = np.linalg.eigvalsh(np.cov(np.vstack([ex, ey])))
    aspect = np.sqrt(ev[1] / ev[0])

    fig, ax = plt.subplots(figsize=(9, 9.6))
    fig.subplots_adjust(left=0.1, right=0.72, top=0.9, bottom=0.2)
    fig.suptitle("F2.6  Why Stage 3 scores the grid, not the circle", x=0.02, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.02, 0.925, "Jacksonville origin grid at 24 h back, with the r50 and r90 rings the UI shows as a one-number summary",
             fontsize=9.5, color=INK2)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("seq", ["#fcfcfb", "#cfe0f5", "#6ea6e6", "#2a78d6", "#0d3c78"])
    ax.pcolormesh(xe, ye, V, cmap=cmap, shading="flat", vmin=0, vmax=1, rasterized=True)
    for r, lab in [(o["radius_50_km"], "r50"), (o["radius_90_km"], "r90")]:
        ax.add_patch(Circle((0, 0), r, fill=False, ec=INK, lw=1.3, ls="-" if lab == "r50" else (0, (5, 3))))
        ax.text(r * 0.71 + 0.8, -r * 0.71 - 0.8, f"{lab} {r:.1f} km", fontsize=9, color=INK)
    ax.plot(0, 0, "+", ms=14, mew=2, color=INK)
    ax.plot(X[pk], Y[pk], "o", ms=10, mfc="none", mec="#e34948", mew=2.2)
    ax.annotate(f"grid peak\n{peak_km:.1f} km from the centroid", (X[pk], Y[pk]), xytext=(18, 14),
                textcoords="offset points", fontsize=9, color=INK, arrowprops=dict(arrowstyle="-", color=INK2))
    ax.annotate("centroid", (0, 0), xytext=(-60, -24), textcoords="offset points", fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2))
    ax.set_aspect("equal")
    ax.set_xlim(xe.min(), xe.max()); ax.set_ylim(ye.min(), ye.max())
    ax.set_xlabel("km east of centroid"); ax.set_ylabel("km north of centroid")
    ax.grid(False)
    side = fig.add_axes([0.745, 0.35, 0.24, 0.5]); side.axis("off")
    stats = [(f"{aspect:.2f} : 1", "cloud aspect\n(PCA on 150,000 endpoints)"),
             (f"{peak_km:.1f} km", "grid peak to centroid"),
             (f"{hp_out_mass*100:.1f}%", "of high-probability mass\n(cells ≥ 0.5 of peak)\nlies outside r50")]
    for i, (big, small) in enumerate(stats):
        yy = 1 - i * 0.34
        side.text(0, yy, big, fontsize=20, fontweight="bold", color=INK, va="top")
        side.text(0, yy - 0.09, small, fontsize=8.5, color=INK2, va="top")
    caption(fig,
            "The cloud is a streak, so a circle around its centroid includes empty water and excludes part of the bright core. "
            "The grid is the object: Stage 3 scores vessels against the grid, and closest_km is measured to the peak (D36). "
            "One fifth of the high-probability mass outside the circle is enough to break a circle-based score. All numbers are measured on "
            "Jacksonville's shipped bundle, the hero case, not on the case-000 fixture.",
            f"cases/{c}/origin.json (grid {R}×{Cc}, row 0 = north) + pipeline/drift/out/ensemble_{c}.npz",
            f"{R*Cc:,} grid cells ({hp.sum():,} high-probability); 150,000 endpoints", y=0.02, width=120)
    save(fig, "F2.6_grid_not_circle.png")


# ---------------------------------------------------------------- F2.7 age estimators
def short_reason(est, d):
    if d is None:
        return "not run"
    s = d.get("skipped", "")
    if est in ("shear", "elongation") and "discharge_class is" in s:
        return f"gated off: discharge_class '{d.get('discharge_class')}'"
    if est == "fay" and "no independently reported release volume" in s:
        return "refused: no independent volume"
    if est == "fay" and d.get("regime") == "shear_dominated":
        return "refused: shear-dominated (3× area gap)"
    return "did not fire"


def f27():
    ests = [("shear", "C3.1  shear dispersion"), ("fay", "C3.2  Fay spreading"), ("elongation", "C3.3  elongation")]
    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.subplots_adjust(left=0.13, right=0.98, top=0.8, bottom=0.25)
    fig.suptitle("F2.7  Age: a designed capability, not triggered on these scenes — 0 of 18 estimator slots fire, each with its reason",
                 x=0.02, ha="left", fontsize=12.5, fontweight="bold")
    fired = 0
    for i, c in enumerate(CASES):
        o = load(f"cases/{c}/origin.json")
        a = load(f"pipeline/drift/out/age_{c}.json")
        for j, (k, _) in enumerate(ests):
            band = o["age_estimators"].get(k)
            if band is not None:
                fired += 1
                ax.barh(i, band[1] - band[0], left=j + band[0] / 72, color=COLOR[c], height=0.5)
            else:
                ax.add_patch(plt.Rectangle((j + 0.02, i - 0.3), 0.96, 0.6, fc=NULL_GREY, ec="none", hatch="////",
                                           alpha=0.55))
                ax.text(j + 0.5, i, "null — " + short_reason(k, a.get(k)), ha="center", va="center", fontsize=8.2, color=INK)
        ax.text(3.08, i, f"age_hours: {json.dumps(o['age_hours'])}\nage_method: '{o['age_method']}'", va="center", fontsize=8, color=INK2,
                family="DejaVu Sans Mono")
    ax.set_xlim(0, 3.7); ax.set_ylim(len(CASES) - 0.5, -0.5)
    ax.set_yticks(range(len(CASES)), [LABEL[c] for c in CASES])
    ax.set_xticks([0.5, 1.5, 2.5], [lab for _, lab in ests])
    ax.xaxis.tick_top(); ax.tick_params(length=0)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    caption(fig,
            "Age ships as designed capability, not as an output on these scenes, and there is no hit rate (same shape as natural_seep under D19). The acute-gated estimators cannot open on any slick in the library: "
            "discharge_class is set from shape alone, and 'acute' needs low elongation, which oil slicks do not have (0 of 13 detections). "
            "The gate reading elongation is circular and documented as such (ruled 13 Sept). Huntington is the one case with a documented release "
            "interval, and no estimator fires on it either — so there is no N = 1 to state. Every bundle reads age_method 'none'.",
            "cases/<case>/origin.json → age_estimators, age_hours, age_method; reasons from pipeline/drift/out/age_<case>.json",
            f"6 cases × 3 estimators = 18 slots, {fired} fired", y=0.02, width=165)
    save(fig, "F2.7_age_estimators.png")


# ---------------------------------------------------------------- F2.8 the 10x guard
def f28():
    txt = (DATA / "drift_tests_2026-09-16.txt").read_text(encoding="utf-8")
    assert re.search(r"PASS\s+4b\s+a mis-scaled field", txt)
    fig = plt.figure(figsize=(12, 6.6))
    fig.suptitle("F2.8  The ÷1000 guard: a 10× unit error caught before a single particle moved",
                 x=0.02, ha="left", fontsize=13, fontweight="bold")
    steps = [
        ("What our own docs said", "docs/TRAPS.md #2 (original):\nHYCOM velocity is cm/s → divide by 100"),
        ("What GEE actually serves", "HYCOM/sea_water_velocity:\nunits m/s, scale factor 0.001\n→ divide by 1000"),
        ("What fired", "permanent plausibility guard\n(speed < 3 m/s) on the FIRST real\nfetch — before integration"),
        ("How the fix was checked", "corrected field runs south along\nthe Coromandel coast at 0.3–1.1 m/s:\nthe East India Coastal Current,\nNE monsoon"),
    ]
    for i, (h, body) in enumerate(steps):
        x = 0.03 + i * 0.24
        fig.patches.append(matplotlib.patches.FancyBboxPatch((x, 0.6), 0.215, 0.24, boxstyle="round,pad=0.006,rounding_size=0.01",
                                                             transform=fig.transFigure, fc="#f1f0ec", ec=GRID))
        fig.text(x + 0.012, 0.815, f"{i+1}  {h}", fontsize=10.5, fontweight="bold", va="top")
        fig.text(x + 0.012, 0.755, body, fontsize=8.8, color=INK2, va="top", linespacing=1.4)
    ax = fig.add_axes([0.08, 0.26, 0.86, 0.22])
    ax.barh(1, 1.1 - 0.3, left=0.3, height=0.45, color="#2a78d6")
    ax.barh(0, 11 - 3, left=3, height=0.45, color="#e34948")
    ax.axvline(3, color=INK, lw=1.4, ls=(0, (5, 3)))
    ax.text(3.1, 1.35, "guard: 3 m/s", fontsize=9, color=INK)
    ax.text(3.3, 1, "◀  ÷1000 (correct): 0.3–1.1 m/s, passes", va="center", fontsize=9, color=INK)
    ax.text(11.2, 0, "÷100: same field read 10× too fast, 3–11 m/s → REFUSED", va="center", fontsize=9, color=INK)
    ax.set_yticks([]); ax.set_xlim(0, 20); ax.set_xlabel("surface current speed (m/s)")
    ax.grid(axis="y", visible=False)
    caption(fig,
            "Evidence of process, not of a result: the check sits between the data and the model, so a wrong unit cannot reach a particle. "
            "It is permanent — it runs on every real fetch, not only in tests (test 4b rejects a 50 m/s field). The ÷100 bar is derived "
            "(the corrected range × 10), not a separately logged reading.",
            "docs/TRAPS.md #2 (corrected 7 Sept); docs/STAGE2_NUMBERS.md §8.6; test 4b in docs/evaluation/figures/stage2/data/drift_tests_2026-09-16.txt",
            "1 guard event, first real fetch (Ennore field)", y=0.03, width=165)
    save(fig, "F2.8_unit_guard.png")

# ---------------------------------------------------------------- F2.9 both directions
def f29():
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 7.4), sharex=True)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.83, bottom=0.25, hspace=0.32, wspace=0.22)
    fig.suptitle("F2.9  One model, both directions: where it came from and where it goes, with the uncertainty stated the same way",
                 x=0.02, ha="left", fontsize=12.5, fontweight="bold")
    for ax, c in zip(axes.flat, CASES):
        g = load(f"docs/evaluation/figures/stage2/data/growth_{c}.json")
        f = load(f"docs/evaluation/figures/stage2/data/forward_{c}.json")
        assert g["reproduces_shipped"] and f["horizon_hours"] == 24
        hb = [-r["hours_back"] for r in g["growth"]]
        hf = [r["hours"] for r in f["envelope"]]
        for key, ls in [("radius_90_km", (0, (4, 2.5))), ("radius_50_km", "-")]:
            ax.plot(hb, [r[key] for r in g["growth"]], color=COLOR[c], lw=2, ls=ls)
            ax.plot(hf, [r[key] for r in f["envelope"]], color=COLOR[c], lw=2, ls=ls)
        ax.axvline(0, color=INK, lw=1)
        top = max(max(r["radius_90_km"] for r in g["growth"]), max(r["radius_90_km"] for r in f["envelope"]))
        ax.set_ylim(0, top * 1.25)
        ax.set_xlim(-24, 24); ax.set_xticks([-24, -12, 0, 12, 24])
        ax.set_title(LABEL[c], loc="left", fontsize=10.5)
        e = f["envelope"][-1]; b = g["growth"][-1]
        ax.text(0.02, 0.97, f"origin  r90 {b['radius_90_km']:.1f} km", transform=ax.transAxes, fontsize=8, color=INK2, va="top")
        ax.text(0.98, 0.97, f"+24 h  r90 {e['radius_90_km']:.1f} km", transform=ax.transAxes, fontsize=8, color=INK2, va="top", ha="right")
        land = "no landfall" if f["first_landfall_hours"] is None else f"first landfall {f['first_landfall_hours']:.1f} h"
        ax.text(0.98, 0.04, f"{f['stranded_fraction_at_horizon']*100:.0f}% stranded · {land}", transform=ax.transAxes,
                fontsize=8, color=INK2, ha="right")
    for ax in axes[1]:
        ax.set_xlabel("hours from detection  (← backward · forward →)")
    for ax in axes[:, 0]:
        ax.set_ylabel("km")
    fig.legend([plt.Line2D([], [], color=INK2, lw=2), plt.Line2D([], [], color=INK2, lw=2, ls=(0, (4, 2.5)))],
               ["r50 — half the endpoints within", "r90 — 90% of the endpoints within"], loc="upper left",
               bbox_to_anchor=(0.06, 0.93), ncol=2, fontsize=9)
    caption(fig,
            "The same 50-run ensemble (same seed particles, same stratified wind and current draws) run backward to the origin and forward from "
            "the slick. Spread is precision, not accuracy. Horizon is 24 h in both directions because the cached current and wind fields "
            "cover only ~24–26 h past detection; +48 h and +72 h need a wider fetch and are not extrapolated. Past 48 h omitted physics "
            "enters the budget, so a longer forecast would be a weaker claim. No particle reaches the GSHHG coastline within 24 h "
            "on any case, so first landfall is null, not 0.",
            "backward: docs/evaluation/figures/stage2/data/growth_<case>.json · forward: docs/evaluation/figures/stage2/data/forward_<case>.json "
            "(python pipeline/drift/eval_forward.py --case <id>)",
            "6 cases × 50 runs × 3000 particles = 150,000 endpoints per case, per hour, per direction", y=0.02, width=165)
    save(fig, "F2.9_both_directions.png")


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    for f in (f21, f22, f23, f24, f25, f26, f27, f28, f29):
        f()
