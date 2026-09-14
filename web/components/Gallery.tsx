"use client";

// Screen 0 — the case picker (docs/00_MASTER_PLAN.md §2.2, docs/team/harshita-frontend.md Screen 0).
// Data-driven: cases/index.json → each case's meta.json → cards, in index order. Every card
// field is absent-safe — a v1-shaped fixture (case-000) renders a valid but minimal card;
// a real V3 bundle fills in the badge / location / blurb / difficulty / thumbnail. Nothing
// is invented to make a sparse case look fuller.

import { useEffect, useState } from "react";
import Link from "next/link";
import { formatAcquisitionDate, loadGallery, type GalleryCase } from "@/lib/cases";

const TAGLINE =
  "Satellite forensics: we find oil spills from space, run the ocean backwards to find where they started, and identify the ship responsible.";

const CASE_TYPE_BADGE: Record<NonNullable<GalleryCase["caseType"]>, string> = {
  spill: "SPILL",
  lookalike: "LOOK-ALIKE",
  nospill: "NO SPILL",
};

/** Thumbnail with a neutral placeholder — used both when no thumbnail is declared and when a
 *  declared one fails to load. Never a broken-image icon. */
function CaseThumb({ src, alt }: { src?: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="relative h-14 w-20 shrink-0 overflow-hidden rounded bg-white/[0.03]">
      {src && !failed ? (
        // A user-data image at a path the app does not control — a plain <img> with an
        // onError fallback is the right tool here (no build-time optimisation of a bundle
        // asset), so the "does it actually load" probe is honest.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={alt}
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-[8px] font-mono uppercase tracking-[0.15em] text-white/20">
          no preview
        </div>
      )}
    </div>
  );
}

function CaseCard({ c, emphasised }: { c: GalleryCase; emphasised: boolean }) {
  // Listed in the index but its meta.json could not be read — surface it, do not hide it,
  // do not make it clickable, do not substitute a fabricated case.
  if (!c.ok) {
    return (
      <div className="rounded border border-[#ff4d4d]/25 bg-[#ff4d4d]/[0.05] px-4 py-3">
        <div className="font-mono text-[11px] text-white/70">{c.id}</div>
        <p className="mt-0.5 text-[10px] leading-snug text-[#ffb0b0]/60">
          meta.json could not be loaded — {c.loadError}
        </p>
      </div>
    );
  }

  const date = c.detectionTime ? formatAcquisitionDate(c.detectionTime) : null;
  const showTagRow = emphasised || !!c.caseType;

  return (
    <Link
      href={`/case/${c.id}/detect`}
      className={`group flex items-stretch gap-3 rounded border px-4 py-3 transition-colors ${
        emphasised
          ? "border-[#f97316]/40 bg-[#f97316]/[0.06] hover:bg-[#f97316]/[0.10]"
          : "border-white/[0.08] hover:bg-white/[0.04]"
      }`}
    >
      <CaseThumb src={c.thumbnailUrl} alt={c.title ?? c.id} />

      <div className="flex min-w-0 flex-1 flex-col justify-center">
        {showTagRow && (
          <div className="flex items-center gap-2">
            {emphasised && (
              <span className="text-[8px] font-semibold uppercase tracking-[0.2em] text-[#f97316]">
                Start here
              </span>
            )}
            {c.caseType && (
              <span className="rounded-sm border border-white/15 px-1.5 py-px text-[8px] font-semibold uppercase tracking-[0.12em] text-white/55">
                {CASE_TYPE_BADGE[c.caseType]}
              </span>
            )}
          </div>
        )}

        <div className="mt-0.5 truncate text-[13px] font-medium text-white/85">
          {c.title ?? c.id}
        </div>

        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[10px] text-white/35">
          <span className="font-mono">{c.id}</span>
          {c.shortLocation && (
            <>
              <span className="text-white/20">·</span>
              <span>{c.shortLocation}</span>
            </>
          )}
          {date && (
            <>
              <span className="text-white/20">·</span>
              <span className="font-mono">{date}</span>
            </>
          )}
        </div>

        {c.blurb && (
          <p className="mt-1.5 line-clamp-2 text-[11px] leading-snug text-white/50">
            {c.blurb}
          </p>
        )}

        {c.difficulty && (
          <div className="mt-1.5">
            <span className="rounded-sm bg-white/[0.06] px-1.5 py-px text-[8px] font-semibold uppercase tracking-[0.12em] text-white/40">
              {c.difficulty}
            </span>
          </div>
        )}
      </div>

      <span
        aria-hidden
        className="flex shrink-0 items-center pl-2 text-white/25 transition-colors group-hover:text-white/60"
      >
        →
      </span>
    </Link>
  );
}

type GalleryState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; cases: GalleryCase[] };

export default function Gallery() {
  const [state, setState] = useState<GalleryState>({ status: "loading" });

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
    <div className="h-full overflow-y-auto bg-[#0b0f14] text-white">
      <div className="mx-auto max-w-3xl px-6 py-14">
        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/90">
          UDGAM
        </div>
        <p className="mt-3 max-w-xl text-[13px] leading-relaxed text-white/55">
          {TAGLINE}
        </p>

        <div className="mt-10 text-[9px] font-semibold uppercase tracking-[0.16em] text-white/30">
          Cases
        </div>

        {state.status === "loading" && (
          <p className="mt-4 font-mono text-[11px] text-white/30">Loading cases…</p>
        )}

        {state.status === "error" && (
          <div className="mt-4 max-w-md rounded border border-[#ff4d4d]/30 bg-[#ff4d4d]/[0.08] p-4">
            <div className="text-[11px] font-semibold text-[#ff8a8a]">
              Case index failed to load
            </div>
            <p className="mt-1 whitespace-pre-wrap text-[10px] text-[#ffb0b0]/70">
              {state.message}
            </p>
            <p className="mt-2 text-[10px] text-[#ffb0b0]/50">
              cases/index.json is missing or malformed — a data/contract issue for Akshat.
              The frontend does not invent a fallback case.
            </p>
          </div>
        )}

        {state.status === "ready" &&
          (state.cases.length === 0 ? (
            <p className="mt-4 text-[11px] text-white/35">
              cases/index.json lists no cases.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {state.cases.map((c, i) => (
                <li key={c.id}>
                  <CaseCard c={c} emphasised={i === 0} />
                </li>
              ))}
            </ul>
          ))}
      </div>
    </div>
  );
}
