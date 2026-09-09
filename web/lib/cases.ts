// Gallery data source. The case list AND its order come from cases/index.json — never
// hardcoded here (docs/00_MASTER_PLAN.md §6.9, docs/04 Phase 1.2). Each listed case's
// meta.json is fetched and normalised into an absent-safe shape: v1-shaped fixtures like
// case-000 carry almost nothing, real V3 bundles carry the gallery block. A field is only
// ever populated from data that is actually on disk — nothing is invented or defaulted.
//
// This module owns no selection state. Selection happens by navigating to /case/<id>/detect;
// the Zustand store (keyed off the URL [id] segment) is the single source of truth for the
// active case.

/** docs/00_MASTER_PLAN.md §6.1 — the closed vocabularies the Gallery renders. */
export type CaseType = "spill" | "lookalike" | "nospill";
export type Difficulty = "easy" | "medium" | "hard";

/** Store bootstrap value only. The active case always comes from the /case/[id] URL (see
 *  CaseWorkspace), so this is deliberately empty — it hardcodes no case. */
export const DEFAULT_CASE_ID = "";

export interface CaseIndex {
  /** Presentation order, strongest case first. */
  cases: string[];
  /** The id a bare "open the app" entry point would use. */
  default: string;
}

/** One case as the Gallery renders it. `id` is the only guaranteed field; every other field
 *  is present only when the case's meta.json actually carries it. */
export interface GalleryCase {
  id: string;
  /** false → listed in index.json but its meta.json could not be loaded. */
  ok: boolean;
  title?: string;
  shortLocation?: string;
  /** Raw UTC ISO 8601 — kept raw so the card can ignore a malformed value. */
  detectionTime?: string;
  caseType?: CaseType;
  blurb?: string;
  difficulty?: Difficulty;
  /** Resolved `/cases/<id>/<file>`. The card still probes that the image loads before showing it. */
  thumbnailUrl?: string;
  loadError?: string;
}

async function fetchJson(url: string): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch (err) {
    throw new Error(`Could not fetch ${url}: ${(err as Error).message}`);
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url}: HTTP ${res.status}`);
  }
  try {
    return await res.json();
  } catch {
    throw new Error(`${url} is not valid JSON`);
  }
}

function nonEmptyString(v: unknown): string | undefined {
  return typeof v === "string" && v.trim() !== "" ? v : undefined;
}

/**
 * Read + shape-check cases/index.json. Throws a descriptive Error on anything malformed — the
 * Gallery renders that as an error state and never invents a fallback case.
 */
export async function loadCaseIndex(): Promise<CaseIndex> {
  const raw = await fetchJson("/cases/index.json");
  if (!raw || typeof raw !== "object") {
    throw new Error("cases/index.json: not an object");
  }
  const obj = raw as Record<string, unknown>;
  const cases = obj.cases;
  if (
    !Array.isArray(cases) ||
    cases.length === 0 ||
    !cases.every((c) => typeof c === "string" && c.trim() !== "")
  ) {
    throw new Error('cases/index.json: "cases" must be a non-empty array of case ids');
  }
  return {
    cases: cases as string[],
    default: nonEmptyString(obj.default) ?? (cases[0] as string),
  };
}

function normaliseMeta(id: string, raw: unknown): GalleryCase {
  const m = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const g =
    m.gallery && typeof m.gallery === "object"
      ? (m.gallery as Record<string, unknown>)
      : {};

  const ct = nonEmptyString(m.case_type);
  const caseType: CaseType | undefined =
    ct === "spill" || ct === "lookalike" || ct === "nospill" ? ct : undefined;

  const df = nonEmptyString(g.difficulty);
  const difficulty: Difficulty | undefined =
    df === "easy" || df === "medium" || df === "hard" ? df : undefined;

  const thumb = nonEmptyString(g.thumbnail);

  return {
    id,
    ok: true,
    title: nonEmptyString(m.title),
    shortLocation: nonEmptyString(m.short_location),
    detectionTime: nonEmptyString(m.detection_time),
    caseType,
    blurb: nonEmptyString(g.blurb),
    difficulty,
    thumbnailUrl: thumb ? `/cases/${id}/${thumb}` : undefined,
  };
}

/**
 * Load one case's meta.json. A failure is captured on the returned object (`ok: false`)
 * rather than thrown, so one unreadable case never blanks the whole Gallery.
 */
export async function loadGalleryCase(id: string): Promise<GalleryCase> {
  try {
    return normaliseMeta(id, await fetchJson(`/cases/${id}/meta.json`));
  } catch (err) {
    return { id, ok: false, loadError: (err as Error).message };
  }
}

/**
 * The whole Gallery payload: cases in index.json order. Throws only when index.json itself is
 * unreadable; individual case failures come back as `ok: false` entries.
 */
export async function loadGallery(): Promise<GalleryCase[]> {
  const index = await loadCaseIndex();
  return Promise.all(index.cases.map(loadGalleryCase));
}
