// maplibre-gl v6 ships its web worker as a separate ESM file (dist/maplibre-gl-worker.mjs).
// Next's webpack bundles the main entry but not that worker, and v6's built-in worker-URL
// resolver only works when import.meta.url is an http(s) URL — under webpack it becomes a
// build-time file:// path, so maplibre falls back to `new Worker("")` and the worker never
// starts. Result: raster/image layers render but every GeoJSON/vector source stays blank.
//
// Fix: serve the worker (and the shared chunk it imports) as static files and point maplibre
// at them with setWorkerUrl("/maplibre/maplibre-gl-worker.mjs"). This script copies both out
// of node_modules into public/. It runs automatically via the predev / prebuild npm hooks.

import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "node_modules", "maplibre-gl", "dist");
const dest = join(here, "..", "public", "maplibre");

mkdirSync(dest, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(src, f), join(dest, f));
  console.log(`copied ${f} -> public/maplibre/`);
}
