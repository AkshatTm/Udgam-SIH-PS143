import fs from "node:fs";
import path from "node:path";
import { ALL_ACTS } from "@/lib/contracts";

// Static export has no server, so every (id, stage) pair this route can hit must be enumerated
// at build time — a nested dynamic segment does not inherit the parent's generateStaticParams.
// Stages come from ALL_ACTS rather than a per-case acts_available so an out-of-scope stage
// still resolves to a page (CaseWorkspace redirects it client-side; see the layout above).
export function generateStaticParams() {
  const indexPath = path.join(process.cwd(), "public", "cases", "index.json");
  const { cases } = JSON.parse(fs.readFileSync(indexPath, "utf-8")) as { cases: string[] };
  return cases.flatMap((id) => ALL_ACTS.map((stage) => ({ id, stage })));
}

// Route stub. The screen for every stage is rendered by the persistent workspace in
// ../layout.tsx (CaseWorkspace), which reads the active stage from the pathname. This page
// exists only to make /case/<id>/<stage> a routable URL.
export default function StagePage() {
  return null;
}
