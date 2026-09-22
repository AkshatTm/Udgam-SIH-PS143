"use client";

// Screen 0 — the home page (docs/00_MASTER_PLAN.md §2.2, docs/team/harshita-frontend.md Screen 0).
//
// It does two jobs in one scroll: explain what UDGAM does before a judge has clicked anything,
// then hand them the case library. The explanation is three diagrams of the method, not a
// feature list; the library is the nine real scenes, each card carrying its own SAR thumbnail
// so the raw material is the first thing seen.
//
// Data discipline is unchanged from the first version: the list AND its order come from
// cases/index.json, every field is absent-safe, and a case whose meta.json will not load is
// surfaced as a broken card rather than hidden or invented.

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { formatAcquisitionDate, loadGallery, type GalleryCase } from "@/lib/cases";
import FlowField from "./FlowField";
import { DetectDiagram, TraceDiagram, AttributeDiagram } from "./home/StageDiagrams";
import UploadModal from "./UploadModal";

/** Case-type badge: the same colour the map draws that thing in. */
const CASE_TYPE: Record<
  NonNullable<GalleryCase["caseType"]>,
  { label: string; color: string }
> = {
  spill: { label: "Confirmed spill", color: "var(--oil)" },
  lookalike: { label: "Look-alike", color: "var(--reject)" },
  nospill: { label: "Clear water", color: "var(--contact)" },
};

const METHOD = [
  {
    n: "1",
    question: "Is that oil?",
    body: "Radar sees a dark patch wherever the sea surface is smooth. Oil is smooth — but so is calm water, so is rain, so is an algal bloom. The detector separates them on shape, contrast and edge sharpness, and shows its working for the ones it throws out.",
    reads: "Sentinel-1 SAR, 10 m",
    Diagram: DetectDiagram,
  },
  {
    n: "2",
    question: "Where did it start?",
    body: "A slick is only ever seen once, hours after it was made. UDGAM runs fifty perturbed simulations backwards through the currents and the wind that were actually there that day, and keeps the place they agree on.",
    reads: "HYCOM currents · ERA5 wind",
    Diagram: TraceDiagram,
  },
  {
    n: "3",
    question: "Who was there?",
    body: "Ships broadcast their position. Score every track against that origin on distance, timing, speed and silence — and when nothing scores well enough, name nobody and say why.",
    reads: "AIS tracks · radar contacts",
    Diagram: AttributeDiagram,
  },
];

/* ── Case card ───────────────────────────────────────────────────────────── */

function CaseThumb({ src, alt }: { src?: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#070d14]">
        <span className="t-label">No preview</span>
      </div>
    );
  }
  return (
    // A user-data image at a path the app does not control — a plain <img> with an onError
    // fallback keeps the "does it actually load" probe honest.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      className="h-full w-full object-cover transition-transform duration-[900ms] ease-out group-hover:scale-[1.06]"
      onError={() => setFailed(true)}
    />
  );
}

function CaseCard({ c, first }: { c: GalleryCase; first: boolean }) {
  // Listed in the index but its meta.json could not be read — surface it, do not hide it, do
  // not make it clickable, do not substitute a fabricated case.
  if (!c.ok) {
    return (
      <div className="flex min-h-[280px] flex-col justify-end rounded-lg border border-alert/30 bg-alert/[0.06] p-5">
        <div className="font-mono text-[13px] text-ink-2">{c.id}</div>
        <p className="mt-1 t-small text-alert/80">
          meta.json could not be loaded — {c.loadError}
        </p>
      </div>
    );
  }

  const date = c.detectionTime ? formatAcquisitionDate(c.detectionTime) : null;
  const type = c.caseType ? CASE_TYPE[c.caseType] : null;
  const ghosts = c.darkVesselCount ?? 0;

  return (
    <Link
      href={`/case/${c.id}/detect`}
      className="group relative flex min-h-[300px] flex-col overflow-hidden rounded-lg border border-line bg-hull transition-colors duration-300 hover:border-line-strong focus-visible:border-drift"
    >
      <div className="relative h-[172px] overflow-hidden">
        <CaseThumb src={c.thumbnailUrl} alt={c.title ?? c.id} />
        {/* Scrim: the thumbnail runs under the text rather than stopping at a hard edge. */}
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(to bottom, rgba(4,7,11,0.05) 0%, rgba(4,7,11,0.55) 62%, var(--hull) 100%)",
          }}
        />
        {first && (
          <span className="absolute left-4 top-4 rounded-full bg-drift px-2.5 py-1 text-[11px] font-semibold tracking-tight text-abyss">
            Start here
          </span>
        )}
        {type && (
          // Solid, not translucent: this badge sits on bright SAR speckle, where a tinted
          // backdrop leaves the text unreadable.
          <span className="absolute right-4 top-4 flex items-center gap-1.5 rounded-full bg-abyss/90 px-2.5 py-1 text-[11px] font-medium text-ink ring-1 ring-inset ring-line-strong">
            <span
              aria-hidden
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: type.color }}
            />
            {type.label}
          </span>
        )}
        {ghosts > 0 && (
          // Sits under the case-type badge, same solid treatment for the same reason. This is
          // the one thing a card can say that the title and blurb cannot: the answer on this
          // case is a ship that was not broadcasting. Rendered only when suspects.json actually
          // carries one — a detect-only case (darkVesselCount undefined) never shows it, and
          // neither does a case whose cross-check found none.
          <span className="absolute right-4 top-12 flex items-center gap-1.5 rounded-full bg-abyss/90 px-2.5 py-1 text-[11px] font-medium text-[#fda4af] ring-1 ring-inset ring-[#f43f5e]/40">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-dark-vessel" />
            {ghosts === 1 ? "Ghost ship" : `${ghosts} ghost ships`}
          </span>
        )}
      </div>

      <div className="relative flex flex-1 flex-col px-5 pb-5">
        <h3 className="t-subtitle text-ink transition-colors duration-200 group-hover:text-white">
          {c.title ?? c.id}
        </h3>

        {c.blurb && (
          <p className="mt-2 t-small text-pretty text-ink-2">{c.blurb}</p>
        )}

        <div className="mt-auto flex items-end justify-between gap-3 pt-4">
          <div className="min-w-0">
            {c.shortLocation && (
              <div className="truncate t-small text-ink-3">{c.shortLocation}</div>
            )}
            {date && (
              <div className="mt-0.5 font-mono text-[12px] text-ink-3">{date}</div>
            )}
          </div>
          {c.difficulty && (
            <span className="shrink-0 font-mono text-[11px] uppercase text-ink-3">
              {c.difficulty}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

/* ── Page ────────────────────────────────────────────────────────────────── */

type GalleryState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; cases: GalleryCase[] };

export default function Gallery() {
  const [state, setState] = useState<GalleryState>({ status: "loading" });
  const [uploadOpen, setUploadOpen] = useState(false);
  const casesRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let alive = true;
    loadGallery()
      .then((cases) => {
        if (alive) setState({ status: "ready", cases });
      })
      .catch((err: Error) => {
        if (alive) setState({ status: "error", message: err.message });
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="udgam-scroll relative min-h-full bg-abyss text-ink">
      {/* The moving ground. Fixed, so the whole scroll happens over one continuous current
          field rather than the field scrolling away with the hero. */}
      <FlowField className="pointer-events-none fixed inset-0 h-full w-full" />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 bottom-0 h-[45vh]"
        style={{ background: "linear-gradient(to bottom, transparent, var(--abyss) 82%)" }}
      />

      <div className="relative">
        {/* ── Hero ─────────────────────────────────────────────────────────── */}
        <header className="mx-auto flex min-h-[100svh] max-w-[1180px] flex-col px-6 sm:px-10">
          <div className="flex items-baseline gap-3 pt-8">
            <span className="text-[15px] font-semibold tracking-[0.16em] text-ink">
              UDGAM
            </span>
            <span className="t-small text-ink-3">Satellite oil-spill forensics</span>
          </div>

          <div className="flex flex-1 flex-col justify-center py-16">
            <h1 className="t-display max-w-[17ch] text-balance">
              <span className="block text-ink-2">A ship empties its tanks at night,</span>
              <span className="block text-ink-2">200 km from any coast.</span>
              <span className="block text-ink-2">Nobody is watching.</span>
              <span className="block text-ink">A radar satellite is.</span>
            </h1>

            <p className="mt-9 max-w-[62ch] t-subtitle text-pretty text-ink-2">
              UDGAM finds the slick in the radar image, runs the ocean backwards to where the oil
              entered the water, and matches that place and time against every ship that was
              there.
            </p>

            <div className="mt-10 flex flex-wrap items-center gap-x-4 gap-y-4">
              <button
                type="button"
                onClick={() =>
                  casesRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
                }
                className="rounded-full bg-drift px-6 py-3 text-[15px] font-semibold text-abyss transition-transform duration-200 ease-out hover:scale-[1.03]"
              >
                Open a case
              </button>
              <button
                type="button"
                onClick={() => setUploadOpen(true)}
                className="rounded-full border border-line-strong px-6 py-3 text-[15px] font-semibold text-ink transition-colors duration-200 ease-out hover:border-drift hover:text-drift"
              >
                Upload custom case
              </button>
              <span className="t-small text-ink-3">
                Nine real Sentinel-1 scenes, each with a documented outcome
              </span>
            </div>
          </div>

          <div aria-hidden className="pb-10 t-small text-ink-3">
            Scroll for the method
          </div>
        </header>

        {/* ── Method ───────────────────────────────────────────────────────── */}
        <section className="mx-auto max-w-[1180px] px-6 pb-24 sm:px-10">
          <h2 className="t-headline max-w-[20ch] text-balance text-ink">
            Three questions, answered in order.
          </h2>
          <p className="mt-4 max-w-[64ch] t-body text-pretty text-ink-2">
            Each one is a stage you can run yourself in any case below, and watch on the map as
            it lands.
          </p>

          <div className="mt-14 grid gap-x-10 gap-y-14 md:grid-cols-3">
            {METHOD.map(({ n, question, body, reads, Diagram }) => (
              <article key={n} className="border-t border-line pt-6">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-[13px] text-drift">{n}</span>
                  <h3 className="t-title text-ink">{question}</h3>
                </div>
                <div className="mt-5">
                  <Diagram />
                </div>
                <p className="mt-5 t-small text-pretty text-ink-2">{body}</p>
                <p className="mt-3 font-mono text-[12px] text-ink-3">{reads}</p>
              </article>
            ))}
          </div>

          <p className="mt-16 max-w-[70ch] border-l-2 border-drift/50 pl-5 t-body text-pretty text-ink-2">
            Every result in this app was computed offline by our own detector, drift model and
            scorer, then replayed here. Where UDGAM named the wrong ship, or refused to name one
            at all, the case says so.
          </p>
        </section>

        {/* ── Cases ────────────────────────────────────────────────────────── */}
        <section ref={casesRef} className="mx-auto max-w-[1180px] px-6 pb-28 sm:px-10">
          <div className="flex flex-wrap items-baseline justify-between gap-4 border-t border-line pt-8">
            <h2 className="t-headline text-ink">The case library</h2>
            {state.status === "ready" && state.cases.length > 0 && (
              <span className="font-mono text-[13px] text-ink-3">
                {state.cases.length} scenes · strongest first
              </span>
            )}
          </div>

          {state.status === "loading" && (
            <p className="mt-8 font-mono text-[13px] text-ink-3">Loading cases…</p>
          )}

          {state.status === "error" && (
            <div className="mt-8 max-w-lg rounded-lg border border-alert/30 bg-alert/[0.07] p-5">
              <div className="t-subtitle text-alert">
                The case index would not load
              </div>
              <p className="mt-2 whitespace-pre-wrap font-mono text-[12px] text-ink-2">
                {state.message}
              </p>
              <p className="mt-3 t-small text-ink-3">
                cases/index.json is missing or malformed — a data problem, not a display one. The
                app does not invent a fallback case.
              </p>
            </div>
          )}

          {state.status === "ready" &&
            (state.cases.length === 0 ? (
              <p className="mt-8 t-body text-ink-3">cases/index.json lists no cases.</p>
            ) : (
              <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {state.cases.map((c, i) => (
                  <CaseCard key={c.id} c={c} first={i === 0} />
                ))}
              </div>
            ))}
        </section>

        <footer className="mx-auto max-w-[1180px] px-6 pb-12 sm:px-10">
          <div className="border-t border-line pt-6 t-small text-ink-3">
            UDGAM · Team Verdict · Sentinel-1 imagery courtesy of ESA Copernicus
          </div>
        </footer>
      </div>

      <UploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} />
    </div>
  );
}
