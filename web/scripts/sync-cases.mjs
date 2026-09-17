// Copies the case bundles from ../cases/ into public/cases/ — the Node twin of
// scripts/sync_web_cases.py, run automatically by the predev / prebuild npm hooks.
//
// Why it exists: public/cases/ is gitignored, and both app/case/[id] pages read
// public/cases/index.json at build time while the gallery fetches it at runtime. On a fresh
// clone that folder does not exist, so `npm run dev` showed an error screen and `npm run build`
// crashed with ENOENT unless you had first remembered to run the Python sync. Doing it here means
// the web app needs only Node — no venv just to see the demo.
//
// Same rules as the Python script: only what the browser reads (.json / .geojson / .png), never
// sar_vv_vh.tif, never cases/_archive/, and synced cases no longer in index.json are removed.
// Unchanged files (same size and mtime) are skipped, so repeat runs take milliseconds.

import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, utimesSync } from "node:fs";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const SRC = join(here, "..", "..", "cases");
const DST = join(here, "..", "public", "cases");
const COPY_SUFFIXES = new Set([".json", ".geojson", ".png"]);
const SKIP_NAMES = new Set(["sar_vv_vh.tif"]);

function copyIfChanged(src, dst) {
  const s = statSync(src);
  if (existsSync(dst)) {
    const d = statSync(dst);
    // 1 s tolerance: utimes round-trips mtime at a coarser precision than NTFS stores it.
    if (d.size === s.size && Math.abs(d.mtimeMs - s.mtimeMs) < 1000) return false;
  }
  copyFileSync(src, dst);
  utimesSync(dst, s.atime, s.mtime);
  return true;
}

const indexPath = join(SRC, "index.json");
if (!existsSync(indexPath)) {
  console.error(`sync-cases: ${indexPath} not found — nothing to sync.`);
  process.exit(1);
}
let listed;
try {
  listed = JSON.parse(readFileSync(indexPath, "utf-8")).cases ?? [];
} catch (e) {
  console.error(`sync-cases: cases/index.json is not valid JSON: ${e.message}`);
  process.exit(1);
}
if (!Array.isArray(listed) || listed.length === 0) {
  console.error("sync-cases: cases/index.json lists no cases.");
  process.exit(1);
}

let copied = 0;
const missing = [];
for (const id of listed) {
  const caseDir = join(SRC, id);
  if (!existsSync(caseDir) || !statSync(caseDir).isDirectory()) {
    missing.push(id);
    continue;
  }
  const out = join(DST, id);
  mkdirSync(out, { recursive: true });
  for (const name of readdirSync(caseDir)) {
    const f = join(caseDir, name);
    if (SKIP_NAMES.has(name) || !COPY_SUFFIXES.has(extname(name).toLowerCase())) continue;
    if (!statSync(f).isFile()) continue;
    if (copyIfChanged(f, join(out, name))) copied++;
  }
}
mkdirSync(DST, { recursive: true });
copyFileSync(indexPath, join(DST, "index.json"));

const keep = new Set(listed);
for (const d of readdirSync(DST, { withFileTypes: true })) {
  if (d.isDirectory() && !keep.has(d.name)) {
    rmSync(join(DST, d.name), { recursive: true, force: true });
    console.log(`sync-cases: removed stale ${d.name}`);
  }
}

console.log(`sync-cases: ${listed.length - missing.length} case(s) -> public/cases/ (${copied} file(s) updated)`);
if (missing.length) {
  // Not fatal: the gallery renders a missing case as an error card rather than hiding it.
  console.warn(`sync-cases: index.json lists case(s) not on disk: ${missing.join(", ")}`);
}
