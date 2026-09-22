"use client";

// Screen 4 — Verify. Two equal sections (what UDGAM concluded, then what the record says), a
// verdict badge that reads the same for HIT and MISS, the official source as a real external
// link, and the human explanation rendered verbatim. Rendered as a full-cover layer over the
// (still mounted) MapView by CaseWorkspace when the stage is `verify`; the ContextPanel and the
// Trace/Detect footer controls are suppressed for this stage. The bottom-right primary action
// ("Try another case") is still CaseWorkspace's, unchanged.
//
// The two sections are full-width and identically styled, stacked UDGAM-first rather than side
// by side — the ordering states our own conclusion before the reader is handed a record to
// check it against, but neither section gets more width, more emphasis, or different card
// treatment. This is the screen where the project is either right or wrong in front of a judge,
// and a layout that gave our own section more room — or dressed a MISS in red — would be
// arguing rather than reporting.
//
// The verdict's reasoning and each suspect's score-component breakdown are collapsed by
// default (VerdictSection, SuspectEvidence) — both toggled by a click, not by anything that
// runs on a timer or a scroll position. That is the "interactivity" this screen has: nothing
// here is decorative motion, and nothing collapses information a judge hasn't chosen to hide.
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

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import type { Suspect } from "@/lib/suspects";
import type { Assessment } from "@/lib/verification";
import { AIS_SAMPLING_LABEL, ComponentBars, FunnelBar } from "@/components/attribution";
import ExternalLink from "./ExternalLink";
import VerdictBadge from "./VerdictBadge";

/** First sentence (or a hard clip) of a hand-authored explanation, for the collapsed teaser
 *  under the verdict badge. Never runs on anything the app itself wrote — `a.explanation` is
 *  always human prose, so clipping it can shorten but never misrepresent it. */
function leadSentence(text: string, max = 160): string {
  const stop = text.search(/[.!?](\s|$)/);
  const cut = stop > 0 && stop < max ? stop + 1 : max;
  return text.length <= cut ? text : `${text.slice(0, cut).trimEnd()}…`;
}

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
function SuspectEvidence({ s, rank, defaultOpen = false }: { s: Suspect; rank: number; defaultOpen?: boolean }) {
  // The seven-row component breakdown is the single bulkiest thing on this screen, repeated
  // once per candidate — collapsed by default is what keeps a 3-4 vessel shortlist from
  // reading as a wall of bars. The name, score, closest approach and reasons (the parts a
  // reader needs to weigh the claim without digging) stay visible either way.
  const [open, setOpen] = useState(defaultOpen);
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

      {s.reasons.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {s.reasons.map((r, i) => (
            <li key={i} className="t-small text-pretty text-ink-2">
              {r}
            </li>
          ))}
        </ul>
      )}

      {s.components && (
        <div className="mt-4 border-t border-line/60 pt-3">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="flex w-full items-center justify-between text-left"
          >
            <SectionLabel>Score components</SectionLabel>
            <span className="t-label text-ink-3">
              {open ? "Hide ▴" : "Show ▾"}
            </span>
          </button>
          {open && <ComponentBars components={s.components} notes={s.componentNotes} />}
        </div>
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
        <div className="mx-auto max-w-5xl space-y-3">
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
  //
  // `suspects` loads independently of `verification`, so `?? []` made a not-yet-arrived bundle
  // indistinguishable from an arrived-and-missing one: every shortlist entry rendered the red
  // "the two bundles disagree" card for the whole of the fetch. This is the same guard the A4
  // block below already applies, for the same reason.
  const suspectsReady = suspects !== null;
  const scoredByMmsi = new Map((suspects?.suspects ?? []).map((s) => [s.mmsi, s]));
  const shortlist = nr.topSuspects.map((mmsi) => ({
    mmsi,
    scored: scoredByMmsi.get(mmsi),
    pending: !suspectsReady,
  }));

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
        <VerdictSection assessment={a} />

        {/* B — on a case with no record to check against, the caveat IS the finding. Always
            visible regardless of the reasoning toggle above — it explains why there is no
            verdict to give, which is not something to fold away. */}
        {of.sourceType === "none" && of.caveat && (
          <div className="mx-auto mt-8 max-w-[72ch] rounded-lg border border-[#fbbf24]/30 bg-[#fbbf24]/[0.07] p-5">
            <div className="t-label text-[#fcd34d]/80">Why there is nothing to check against</div>
            <p className="mt-2 t-small text-pretty text-[#fde68a]/85">{of.caveat}</p>
          </div>
        )}

        {/* Both sections below are full-width and identically styled — stacked, not columned,
            so putting UDGAM's own conclusion first is ordering, not extra weight. The
            documented record still gets the same card treatment underneath, unchanged in
            substance from the version that used to sit beside it. */}
        <section className="mt-12">
          <ColumnHeading>What UDGAM concluded</ColumnHeading>
          <p className="mt-4 max-w-[72ch] t-body text-pretty text-ink-2">{nr.originSummary}</p>

          {hasKnownOrigin && (
            <p className="mt-4 max-w-[72ch] rounded-lg border border-line bg-raised px-4 py-3 t-small text-pretty text-ink-3">
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
                  <p className="mt-2 max-w-[72ch] t-small text-pretty text-ink-3">
                    Surfaced by the attribution funnel. No investigation, no named party and no
                    enforcement exist for this slick, so nothing here confirms or refutes it.
                  </p>
                )}
                {/* Full width now buys room for two cards per row instead of one long stack —
                    each card is short by default since its score breakdown collapses. */}
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {shortlist.map(({ mmsi, scored, pending }, i) =>
                    pending ? (
                      // Still in flight. Not a disagreement, and must not be drawn as one.
                      <div
                        key={`${mmsi}-${i}`}
                        className="rounded-lg border border-line bg-raised p-4"
                      >
                        <div className="font-mono text-[14px] tabular-nums text-ink-2">
                          MMSI {mmsi}
                        </div>
                        <p className="mt-2 t-small text-ink-3">Loading the scored evidence…</p>
                      </div>
                    ) : scored ? (
                      <SuspectEvidence key={`${mmsi}-${i}`} s={scored} rank={i + 1} defaultOpen={i === 0} />
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

          {/* A4 and A3 side by side on the width this section now has — two short facts about
              the shortlist rather than two full-width blocks stacked one under the other. */}
          {(missingFromFeed.length > 0 || suspects) && (
            <div className="mt-7 grid gap-4 sm:grid-cols-2">
              {/* A4 — stated plainly, because without it a reader has no way to tell a scoring
                  failure from a coverage one, and will assume the first. */}
              {missingFromFeed.length > 0 && (
                <div className="rounded-lg border border-line bg-raised px-4 py-3">
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
                <div className={missingFromFeed.length > 0 ? "" : "sm:col-span-2 sm:max-w-[360px]"}>
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
            </div>
          )}
        </section>

        {/* ── The documented finding — an investigation, another algorithm's attribution,
              press, or an explicit absence. The heading says which. ── */}
        <section className="mt-12 border-t border-line pt-12">
          <ColumnHeading>
            {FINDING_HEADING[of.sourceType] ?? "What the documented record says"}
          </ColumnHeading>
          <p className="mt-4 max-w-[72ch] t-body text-pretty text-ink-2">{of.summary}</p>

          {(of.responsibleParties.length > 0 || of.volumeReported) && (
            <div className="mt-7 grid gap-6 sm:grid-cols-2">
              {of.responsibleParties.length > 0 && (
                <div>
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
                <div>
                  <SectionLabel>Volume reported</SectionLabel>
                  <p className="mt-2 t-body text-ink">{of.volumeReported}</p>
                </div>
              )}
            </div>
          )}

          {/* Already rendered prominently above the sections when it IS the finding. */}
          {of.caveat && of.sourceType !== "none" && (
            <div className="mt-7 max-w-[72ch]">
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
  );
}

/** The verdict badge and the reasoning behind it. Collapsed by default — the badge states the
 *  claim on its own; the paragraph or two of hand-authored reasoning underneath was, on any
 *  case with a real caveat, the single largest block on the screen and the first thing that
 *  made this screen feel like a wall of text rather than a verdict. Clicking the badge (or the
 *  teaser line under it) reveals it. Nothing here shortens or rewrites `a.explanation` itself —
 *  the teaser is a clip of the same human sentence, never a summary this app wrote. */
function VerdictSection({ assessment: a }: { assessment: Assessment }) {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen((v) => !v);
  return (
    <div className="border-b border-line pb-10">
      <div className="flex justify-center">
        <VerdictBadge verdict={a.verdict} expanded={open} onToggle={toggle} />
      </div>
      {/* The badge is centred; the reasoning is not. These explanations run to a couple of
          hundred words on a case we got wrong, and centred prose at that length is a wall
          — a ragged right edge and a fixed left margin is what makes it readable. */}
      <div className="mx-auto mt-6 max-w-[72ch]">
        {open ? (
          <>
            <p className="t-subtitle text-pretty text-ink">{a.explanation}</p>
            {a.whatWouldHaveHelped && (
              <div className="mt-6">
                <SectionLabel>What would have helped</SectionLabel>
                <p className="mt-2 t-small text-pretty text-ink-2">
                  {a.whatWouldHaveHelped}
                </p>
              </div>
            )}
            {/* A `miss` against Cerulean's algorithmic attribution and a reasoned disagreement
                with it are not the same claim — Cerulean runs no drift engine, we do, and when
                the evidence genuinely points elsewhere that is worth saying plainly rather than
                folding into a verdict badge that reads the same as "we found nothing". Blue,
                not amber: this is an active counter-claim, not a caveat about missing data. */}
            {a.disputesReference?.disputed && (
              <div className="mt-6 rounded-lg border border-[#60a5fa]/30 bg-[#60a5fa]/[0.07] p-5">
                <div className="t-label text-[#93c5fd]/80">We disagree with the reference</div>
                <p className="mt-2 t-small text-pretty text-[#bfdbfe]/90">
                  {a.disputesReference.ourClaim}
                </p>
                <p className="mt-3 t-small text-pretty text-[#bfdbfe]/70">
                  {a.disputesReference.basis}
                </p>
              </div>
            )}
            <button
              type="button"
              onClick={toggle}
              className="mt-4 t-label text-ink-3 underline decoration-dotted underline-offset-4 hover:text-ink-2"
            >
              Hide reasoning
            </button>
          </>
        ) : (
          <button type="button" onClick={toggle} className="block w-full text-center">
            <p className="t-body text-pretty text-ink-2">{leadSentence(a.explanation)}</p>
            <span className="mt-2 inline-block t-label text-ink-3 underline decoration-dotted underline-offset-4">
              Read the full assessment
            </span>
          </button>
        )}
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
