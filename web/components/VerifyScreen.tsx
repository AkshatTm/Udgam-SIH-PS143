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
// It never generates prose. `assessment.explanation`, `official_finding.summary` and every
// caveat are hand-authored research, rendered verbatim, and nothing here writes a sentence
// about a result that a human did not write.
//
// It DOES read suspects.json, which an earlier version of this file refused to do. The rule it
// broke — "never enrich top_suspects from other bundles" — exists to stop this screen
// MANUFACTURING A CLAIM the research did not make. Rendering the measured score, the component
// breakdown and the funnel behind a claim verification.json already makes is the opposite of
// that: it is showing the evidence for a stated conclusion instead of asking a judge to take
// a bare MMSI on faith. The screen still names exactly the MMSIs `udgam_result.top_suspects`
// names, in that order, and adds, drops and reorders nothing. `suspects` is already in the
// store for every case that has `verify` (store.ts loads it with the `attribute` act), so this
// costs no extra fetch.

import { useAppStore } from "@/lib/store";
import type { Suspect } from "@/lib/suspects";
import { AIS_SAMPLING_LABEL, ComponentBars, FunnelBar } from "@/components/attribution";
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

const COVER = "absolute inset-0 z-[5] overflow-y-auto bg-abyss px-8 py-10";

/** One named vessel with the evidence that put it there. Rendering a bare MMSI — which is what
 *  this screen used to do — makes a 0.62 on a six-vessel pool and a 0.05 on a crowded one look
 *  identical, and leaves a reader unable to weigh our own result at all. */
function SuspectEvidence({ s, rank }: { s: Suspect; rank: number }) {
  return (
    <div className="rounded-lg border border-line bg-raised/40 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="t-label">Rank {String(rank).padStart(2, "0")}</div>
          <div className="mt-1 t-subtitle text-ink">{s.name}</div>
          <div className="mt-0.5 font-mono text-[12px] text-ink-3">
            MMSI {s.mmsi}
            {s.vesselType ? ` · ${s.vesselType}` : ""}
          </div>
        </div>
        {/* The score is the one number a reader needs to weigh the claim, so it is the one
            number set large. */}
        <div className="shrink-0 text-right">
          <div className="font-mono text-[26px] leading-none tabular-nums text-ink">
            {s.score.toFixed(2)}
          </div>
          <div className="mt-1 t-label">Score</div>
        </div>
      </div>

      <div className="mt-3 font-mono text-[12px] tabular-nums text-ink-3">
        Closest approach {s.closestKm.toFixed(2)} km
        {s.closestTime ? ` · ${s.closestTime}` : ""}
        {/* Surface it, don't hide it — closest_km may be understated at the box edge. */}
        {s.edgeTruncated ? " · at search-box edge" : ""}
      </div>

      {s.components && (
        <div className="mt-4">
          <SectionLabel>Score components</SectionLabel>
          <ComponentBars components={s.components} notes={s.componentNotes} />
        </div>
      )}

      {s.reasons.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {s.reasons.map((r, i) => (
            <li key={i} className="t-small text-pretty text-ink-2">
              {r}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function VerifyScreen() {
  const meta = useAppStore((s) => s.meta);
  const verification = useAppStore((s) => s.verification);
  const status = useAppStore((s) => s.verificationStatus);
  const error = useAppStore((s) => s.verificationError);
  const suspects = useAppStore((s) => s.suspects);
  const vessels = useAppStore((s) => s.vessels);

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

  // A named MMSI is matched to its scored record so the shortlist can show the evidence. The
  // ORDER is always verification.json's — this only looks up what each entry refers to.
  const scoredByMmsi = new Map((suspects?.suspects ?? []).map((s) => [s.mmsi, s]));
  const shortlist = nr.topSuspects.map((mmsi) => ({ mmsi, scored: scoredByMmsi.get(mmsi) }));

  // A4 — the fact that turns an unexplained miss into a diagnosed one. Derived per case from
  // two already-loaded bundles; never a hardcoded MMSI, never a hardcoded case id. A party
  // with a null MMSI (a dark vessel, an offshore structure) is not checked: there is no AIS
  // identity to look for, so its absence from an AIS feed says nothing.
  //
  // Only claimed when BOTH bundles are actually loaded. If vessels.geojson has not arrived we
  // cannot assert a vessel is missing from it, and asserting it anyway would be exactly the
  // kind of unbacked claim the rest of this screen refuses to make.
  const poolReady = suspects !== null && vessels !== null;
  const inPool = new Set<string>([
    ...(suspects?.suspects ?? []).map((s) => s.mmsi),
    ...(vessels?.tracks ?? []).map((t) => t.mmsi),
  ]);
  const missingFromFeed = poolReady
    ? of.responsibleParties.filter((p) => p.mmsi !== null && !inPool.has(p.mmsi))
    : [];

  const aisLabel = meta?.ais_source ? AIS_SAMPLING_LABEL[meta.ais_source] : null;

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

        {/* B — on a case with no record to check against, the caveat IS the finding. Leaving it
            at the foot of the right column (where it sits on every other case) buries the one
            paragraph that explains why there is no verdict to give. */}
        {of.sourceType === "none" && of.caveat && (
          <div className="mx-auto mt-10 max-w-[72ch] rounded-lg border border-[#fbbf24]/30 bg-[#fbbf24]/[0.07] p-5">
            <div className="t-label text-[#fcd34d]/80">Why there is nothing to check against</div>
            <p className="mt-2 t-small text-pretty text-[#fde68a]/85">{of.caveat}</p>
          </div>
        )}

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
              {/* B — where no record exists to confirm or refute it, a named vessel is a
                  candidate the funnel returned and nothing more. The heading has to say so:
                  "Vessel shortlist" next to a NOT APPLICABLE badge invites a reader to hear a
                  conclusion that nobody reached. */}
              <SectionLabel>
                {of.sourceType === "none" ? "Candidate surfaced — unconfirmed" : "Vessel shortlist"}
              </SectionLabel>

              {nr.abstained ? (
                <AbstainState />
              ) : shortlist.length > 0 ? (
                <>
                  {of.sourceType === "none" && (
                    <p className="mt-2 t-small text-pretty text-ink-3">
                      Surfaced by the attribution funnel. No investigation, no named party and no
                      enforcement exist for this slick, so nothing here confirms or refutes it.
                    </p>
                  )}
                  <div className="mt-3 space-y-3">
                    {shortlist.map(({ mmsi, scored }, i) =>
                      scored ? (
                        <SuspectEvidence key={`${mmsi}-${i}`} s={scored} rank={i + 1} />
                      ) : (
                        // The bundles disagree: verification.json names an MMSI that
                        // suspects.json does not score. Surfaced as a contract issue, the same
                        // way the rest of the web layer treats a mismatch — never silently
                        // dropped, and never filled in from somewhere else.
                        <div
                          key={`${mmsi}-${i}`}
                          className="rounded-lg border border-alert/30 bg-alert/[0.07] p-4"
                        >
                          <div className="font-mono text-[14px] tabular-nums text-ink">
                            MMSI {mmsi}
                          </div>
                          <p className="mt-2 t-small text-ink-2">
                            Named in verification.json but not scored in suspects.json — the two
                            bundles disagree. A contract issue to fix in the producing code.
                          </p>
                        </div>
                      ),
                    )}
                  </div>
                </>
              ) : (
                <p className="mt-2 t-body text-ink-2">UDGAM named no vessel.</p>
              )}
            </div>

            {/* A4 — stated plainly, because without it a reader has no way to tell a scoring
                failure from a coverage one, and will assume the first. */}
            {missingFromFeed.length > 0 && (
              <div className="mt-7 rounded-lg border border-line bg-raised px-4 py-3">
                <SectionLabel>Why the record&rsquo;s vessel is not in our shortlist</SectionLabel>
                {missingFromFeed.map((p, i) => (
                  <p key={i} className="mt-2 t-small text-pretty text-ink-2">
                    No position report for <span className="text-ink">{p.name}</span> (MMSI{" "}
                    <span className="font-mono tabular-nums">{p.mmsi}</span>) appears in this
                    case&rsquo;s AIS feed
                    {suspects ? ` — ${suspects.funnel.inRegion} vessels cover this scene` : ""}.
                    UDGAM ranked the vessels it could see.
                  </p>
                ))}
                {aisLabel && <p className="mt-2 t-small text-ink-3">{aisLabel}</p>}
              </div>
            )}

            {/* A3 — the candidate pool. Six vessels in region reads very differently from a
                hundred, and until now the screen showed neither. */}
            {suspects && (
              <div className="mt-7">
                <SectionLabel>Candidate pool</SectionLabel>
                {aisLabel && <p className="mt-1 t-small text-ink-3">{aisLabel}</p>}
                <div className="mt-3">
                  <FunnelBar funnel={suspects.funnel} />
                </div>
                {/* A side count, not a fifth narrowing stage. null (field absent) ≠ 0 (field
                    present and zero) — see Funnel.droppedShortTrack. */}
                {suspects.funnel.droppedShortTrack !== null && (
                  <p className="mt-2 t-small text-ink-2">
                    {suspects.funnel.droppedShortTrack} dropped — fewer than{" "}
                    {meta?.ais_source === "gfw_hourly" ? "2 hourly AIS positions" : "5 AIS reports"}
                  </p>
                )}
              </div>
            )}
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

            {/* Already rendered prominently above the columns when it IS the finding. */}
            {of.caveat && of.sourceType !== "none" && (
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

function ColumnHeading({ children }: { children: React.ReactNode }) {
  return <h2 className="t-title text-ink">{children}</h2>;
}

/** A5 — refusing to name a vessel is a result, and on three cases in this library it is the
 *  CORRECT one: the responsible party was a dark vessel or a fixed structure with no AIS
 *  identity, so there was no ship to name. One grey sentence made that look like the system
 *  had nothing to say. It gets the same weight as a named shortlist, with the reason and the
 *  scene-level contacts that were found instead. */
function AbstainState() {
  const suspects = useAppStore((s) => s.suspects);
  const nDark = suspects?.darkVessels.length ?? 0;
  const nInfra = suspects?.infrastructure.length ?? 0;

  return (
    <div className="mt-2 rounded-lg border border-line bg-raised/40 p-4">
      <p className="t-body text-ink">
        UDGAM named no vessel — attribution not possible at acceptable confidence.
      </p>
      {suspects?.abstainReason && (
        <p className="mt-3 t-small text-pretty text-ink-2">{suspects.abstainReason}</p>
      )}
      {(nDark > 0 || nInfra > 0) && (
        <div className="mt-4">
          <SectionLabel>Found in the scene instead</SectionLabel>
          <ul className="mt-2 space-y-1">
            {nDark > 0 && (
              <li className="t-small text-ink-2">
                {nDark} radar contact{nDark === 1 ? "" : "s"} with no AIS broadcast
              </li>
            )}
            {nInfra > 0 && (
              <li className="t-small text-ink-2">
                {nInfra} fixed structure{nInfra === 1 ? "" : "s"} scored against the origin
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
