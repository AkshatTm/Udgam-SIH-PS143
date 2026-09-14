"use client";

// Screen 4 — Verify. Two equal columns (what UDGAM concluded | what the record says), a verdict
// badge that reads the same for HIT and MISS, the official source as a real external link, and
// the human explanation rendered verbatim. Rendered as a full-cover layer over the (still
// mounted) MapView by CaseWorkspace when the stage is `verify`; the ContextPanel and the
// Trace/Detect footer controls are suppressed for this stage. The bottom-right primary action
// ("Try another case") is still CaseWorkspace's, unchanged.
//
// The two columns are deliberately identical in weight and width. This is the screen where the
// project is either right or wrong in front of a judge, and a layout that gave our own column
// more room — or dressed a MISS in red — would be arguing rather than reporting.
//
// It renders ONLY what verification.json provides. It never generates prose, never enriches
// top_suspects from other bundles, and treats a malformed source_url as a contract issue to
// show (see ExternalLink), not to trust.

import { useAppStore } from "@/lib/store";
import ExternalLink from "./ExternalLink";
import VerdictBadge from "./VerdictBadge";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="t-label">{children}</div>;
}

/** The right column's heading, which must match what the source actually is (§6.8, CLAUDE.md:
 *  "agreement with another algorithm is never called ground truth"). Only an
 *  `official_investigation` is an investigation; Cerulean is an algorithm with analyst review,
 *  and calling its output "the investigation" on screen would be the exact overclaim the caveats
 *  below spend a paragraph avoiding. */
const FINDING_HEADING: Record<string, string> = {
  official_investigation: "What the investigation found",
  algorithmic_attribution: "What the documented attribution says",
  press: "What was reported",
  none: "What the public record shows",
};

function ColumnHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="t-title text-ink">{children}</h2>;
}

const COVER = "absolute inset-0 z-[5] overflow-y-auto bg-abyss px-8 py-10";

export default function VerifyScreen() {
  const meta = useAppStore((s) => s.meta);
  const verification = useAppStore((s) => s.verification);
  const status = useAppStore((s) => s.verificationStatus);
  const error = useAppStore((s) => s.verificationError);

  // Defensive — CaseWorkspace already redirects a /verify URL for a case without the act.
  if (meta && !meta.acts_available.includes("verify")) {
    return (
      <div className={COVER}>
        <p className="t-body text-ink-3">Nothing to verify for this case.</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className={COVER}>
        <div className="max-w-lg rounded-lg border border-alert/30 bg-alert/[0.07] p-5">
          <div className="t-subtitle text-alert">
            The verification bundle would not load
          </div>
          <p className="mt-2 whitespace-pre-wrap font-mono text-[12px] text-ink-2">{error}</p>
          <p className="mt-3 t-small text-ink-3">
            This is a data problem, not a display one — the app does not patch bundle data.
          </p>
        </div>
      </div>
    );
  }

  if (!verification) {
    // idle / loading — never a blank screen (docs/team/harshita-frontend.md D4).
    return (
      <div className={COVER}>
        <div className="mx-auto grid max-w-5xl gap-10 md:grid-cols-2">
          <ColumnHeading>What UDGAM concluded</ColumnHeading>
          {/* The source type is not known until the bundle lands — stay neutral until it does. */}
          <ColumnHeading>What the documented record says</ColumnHeading>
        </div>
        <p className="mx-auto mt-8 max-w-5xl font-mono text-[13px] text-ink-3">
          Loading the documented finding…
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
    <div className={COVER}>
      <div className="anim-rise mx-auto max-w-5xl pb-24">
        {/* The verdict leads. It used to sit under both columns, which pushed the one thing a
            judge is waiting for below the fold on any case with a long caveat — and on a
            demo that means someone has to scroll to the answer. Stating it first and then
            showing both sides underneath is also the honest order: the claim, then the
            evidence for and against it. */}
        <div className="border-b border-line pb-10">
          <div className="flex justify-center">
            <VerdictBadge verdict={a.verdict} />
          </div>
          {/* The badge is centred; the reasoning is not. These explanations run to a couple of
              hundred words on a case we got wrong, and centred prose at that length is a wall
              — a ragged right edge and a fixed left margin is what makes it readable. */}
          <div className="mx-auto mt-8 max-w-[72ch]">
            <p className="t-subtitle text-pretty text-ink">{a.explanation}</p>
            {a.whatWouldHaveHelped && (
              <div className="mt-6">
                <SectionLabel>What would have helped</SectionLabel>
                <p className="mt-2 t-small text-pretty text-ink-2">
                  {a.whatWouldHaveHelped}
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="mt-10 grid gap-10 md:grid-cols-2">
          {/* ── UDGAM ── */}
          <section className="md:border-r md:border-line md:pr-10">
            <ColumnHeading>What UDGAM concluded</ColumnHeading>
            <p className="mt-4 t-body text-pretty text-ink-2">{nr.originSummary}</p>

            {hasKnownOrigin && (
              <p className="mt-4 rounded-lg border border-line bg-raised px-4 py-3 t-small text-pretty text-ink-3">
                Origin seeded from a documented source, not a UDGAM detection
                {knownOriginLabel ? ` — ${knownOriginLabel}` : ""}.
              </p>
            )}

            <div className="mt-7">
              <SectionLabel>Vessel shortlist</SectionLabel>
              {nr.abstained ? (
                <p className="mt-2 t-body text-ink">
                  UDGAM named no vessel — attribution not possible at acceptable confidence.
                </p>
              ) : nr.topSuspects.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {nr.topSuspects.map((mmsi, i) => (
                    <li
                      key={`${mmsi}-${i}`}
                      className="font-mono text-[14px] tabular-nums text-ink"
                    >
                      MMSI {mmsi}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 t-body text-ink-2">UDGAM named no vessel.</p>
              )}
            </div>
          </section>

          {/* ── The documented finding — an investigation, another algorithm's attribution,
                press, or an explicit absence. The heading says which. ── */}
          <section>
            <ColumnHeading>
              {FINDING_HEADING[of.sourceType] ?? "What the documented record says"}
            </ColumnHeading>
            <p className="mt-4 t-body text-pretty text-ink-2">{of.summary}</p>

            {of.responsibleParties.length > 0 && (
              <div className="mt-7">
                <SectionLabel>Responsible parties</SectionLabel>
                <ul className="mt-2 space-y-2">
                  {of.responsibleParties.map((p, i) => (
                    <li key={`${p.name}-${i}`} className="t-body">
                      <span className="text-ink">{p.name}</span>
                      {p.role ? <span className="text-ink-3"> — {p.role}</span> : null}
                      <span className="ml-1.5 font-mono text-[12px] text-ink-3">
                        (MMSI {p.mmsi ?? "—"}
                        {p.imo ? `, IMO ${p.imo}` : ""})
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {of.volumeReported && (
              <div className="mt-7">
                <SectionLabel>Volume reported</SectionLabel>
                <p className="mt-2 t-body text-ink">{of.volumeReported}</p>
              </div>
            )}

            {of.caveat && (
              <div className="mt-7">
                <SectionLabel>Caveat</SectionLabel>
                <p className="mt-2 t-small text-pretty text-ink-2">{of.caveat}</p>
              </div>
            )}

            <div className="mt-7">
              <SectionLabel>Source</SectionLabel>
              <p className="mt-2 t-body">
                <ExternalLink href={of.sourceUrl}>{of.sourceName}</ExternalLink>
              </p>
            </div>
          </section>
        </div>

      </div>
    </div>
  );
}
