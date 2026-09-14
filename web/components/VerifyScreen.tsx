"use client";

// Screen 4 — Verify. Two equal columns (what UDGAM concluded | what the investigation found),
// a verdict badge that reads the same for HIT and MISS, the official source as a real external
// link, and the human explanation rendered verbatim. Rendered as a full-cover layer over the
// (still-mounted) MapView by CaseWorkspace when the stage is `verify`; the ContextPanel and the
// Trace/Detect footer controls are suppressed for this stage. The bottom-right primary action
// ("Try another case →") is still CaseWorkspace's, unchanged.
//
// It renders ONLY what verification.json provides. It never generates prose, never enriches
// top_suspects from other bundles, and treats a malformed source_url as a contract issue to
// show (see ExternalLink), not to trust.

import { useAppStore } from "@/lib/store";
import ExternalLink from "./ExternalLink";
import VerdictBadge from "./VerdictBadge";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-white/35">
      {children}
    </div>
  );
}

function ColumnHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70">
      {children}
    </h2>
  );
}

export default function VerifyScreen() {
  const meta = useAppStore((s) => s.meta);
  const verification = useAppStore((s) => s.verification);
  const status = useAppStore((s) => s.verificationStatus);
  const error = useAppStore((s) => s.verificationError);

  const cover =
    "absolute inset-0 z-[5] overflow-y-auto bg-[#0b0f14] px-8 py-8";

  // Defensive — CaseWorkspace already redirects a /verify URL for a case without the act.
  if (meta && !meta.acts_available.includes("verify")) {
    return (
      <div className={cover}>
        <p className="text-[11px] text-white/40">Nothing to verify for this case.</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className={cover}>
        <div className="max-w-md rounded border border-[#ff4d4d]/30 bg-[#ff4d4d]/[0.08] p-4">
          <div className="text-[11px] font-semibold text-[#ff8a8a]">
            Verification bundle failed to load
          </div>
          <p className="mt-1 whitespace-pre-wrap text-[10px] text-[#ffb0b0]/70">{error}</p>
          <p className="mt-2 text-[10px] text-[#ffb0b0]/50">
            This is a contract bug — tell Akshat. The frontend does not patch bundle data.
          </p>
        </div>
      </div>
    );
  }

  if (!verification) {
    // idle / loading — never a blank screen (docs/team/harshita-frontend.md D4).
    return (
      <div className={cover}>
        <div className="mx-auto flex max-w-5xl gap-8">
          <div className="flex-1">
            <ColumnHeading>What UDGAM concluded</ColumnHeading>
          </div>
          <div className="w-px shrink-0 bg-white/[0.08]" />
          <div className="flex-1">
            <ColumnHeading>What the investigation found</ColumnHeading>
          </div>
        </div>
        <p className="mx-auto mt-6 max-w-5xl font-mono text-[11px] text-white/30">
          Loading the official finding…
        </p>
      </div>
    );
  }

  const { officialFinding: of, udgamResult: nr, assessment: a } = verification;

  const ko = meta?.known_origin;
  const knownOriginLabel =
    ko != null && !Array.isArray(ko) && typeof ko.label === "string" ? ko.label : null;
  const hasKnownOrigin = ko != null;

  return (
    <div className={cover}>
      <div className="mx-auto max-w-5xl">
        {/* ── Two equal columns ── */}
        <div className="flex gap-8">
          {/* UDGAM */}
          <section className="flex-1">
            <ColumnHeading>What UDGAM concluded</ColumnHeading>
            <p className="mt-3 text-[12px] leading-relaxed text-white/80">
              {nr.originSummary}
            </p>

            {hasKnownOrigin && (
              <p className="mt-3 rounded border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-[10px] leading-relaxed text-white/50">
                Origin seeded from a documented source, not a UDGAM detection
                {knownOriginLabel ? ` — ${knownOriginLabel}` : ""}.
              </p>
            )}

            <div className="mt-4">
              <SectionLabel>Vessel shortlist</SectionLabel>
              {nr.abstained ? (
                <p className="mt-1.5 text-[11px] text-white/70">
                  UDGAM named no vessel — attribution not possible at acceptable confidence.
                </p>
              ) : nr.topSuspects.length > 0 ? (
                <ul className="mt-1.5 space-y-0.5">
                  {nr.topSuspects.map((mmsi, i) => (
                    <li
                      key={`${mmsi}-${i}`}
                      className="font-mono text-[11px] text-white/75 tabular-nums"
                    >
                      MMSI {mmsi}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1.5 text-[11px] text-white/55">
                  UDGAM named no vessel.
                </p>
              )}
            </div>
          </section>

          <div className="w-px shrink-0 bg-white/[0.08]" />

          {/* Investigation */}
          <section className="flex-1">
            <ColumnHeading>What the investigation found</ColumnHeading>
            <p className="mt-3 text-[12px] leading-relaxed text-white/80">{of.summary}</p>

            {of.responsibleParties.length > 0 && (
              <div className="mt-4">
                <SectionLabel>Responsible parties</SectionLabel>
                <ul className="mt-1.5 space-y-1.5">
                  {of.responsibleParties.map((p, i) => (
                    <li key={`${p.name}-${i}`} className="text-[11px] text-white/75">
                      <span className="text-white/90">{p.name}</span>
                      {p.role ? <span className="text-white/45"> — {p.role}</span> : null}
                      <span className="ml-1 font-mono text-[10px] text-white/35">
                        (MMSI {p.mmsi ?? "—"}
                        {p.imo ? `, IMO ${p.imo}` : ""})
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {of.volumeReported && (
              <div className="mt-4">
                <SectionLabel>Volume reported</SectionLabel>
                <p className="mt-1.5 text-[11px] text-white/75">{of.volumeReported}</p>
              </div>
            )}

            {of.caveat && (
              <div className="mt-4">
                <SectionLabel>Caveat</SectionLabel>
                <p className="mt-1.5 text-[11px] leading-relaxed text-white/65">{of.caveat}</p>
              </div>
            )}

            <div className="mt-4">
              <SectionLabel>Source</SectionLabel>
              <p className="mt-1.5 text-[11px] leading-relaxed">
                <ExternalLink href={of.sourceUrl}>{of.sourceName}</ExternalLink>
              </p>
            </div>
          </section>
        </div>

        {/* ── Verdict ── */}
        <div className="mt-10 flex justify-center">
          <VerdictBadge verdict={a.verdict} />
        </div>

        {/* ── Human explanation, verbatim ── */}
        <p className="mx-auto mt-5 max-w-3xl text-center text-[12px] leading-relaxed text-white/75">
          {a.explanation}
        </p>

        {a.whatWouldHaveHelped && (
          <p className="mx-auto mt-4 max-w-3xl text-center text-[10px] leading-relaxed text-white/40">
            What would have helped: {a.whatWouldHaveHelped}
          </p>
        )}

        {/* Bottom padding so the last line clears CaseWorkspace's bottom-right primary action. */}
        <div className="h-16" />
      </div>
    </div>
  );
}
