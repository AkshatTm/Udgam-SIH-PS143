import fs from "node:fs";
import path from "node:path";
import { redirect } from "next/navigation";

// Static export has no server, so every dynamic [id] this route can hit must be enumerated
// at build time. Source of truth is the synced public/cases/index.json (scripts/sync_web_cases.py
// must have run first) rather than a hardcoded list, so a case added to the gallery doesn't
// also require touching this file.
export function generateStaticParams() {
  const indexPath = path.join(process.cwd(), "public", "cases", "index.json");
  const { cases } = JSON.parse(fs.readFileSync(indexPath, "utf-8")) as { cases: string[] };
  return cases.map((id) => ({ id }));
}

// /case/<id> with no stage → enter the flow at the first stage.
export default function CaseIndex({ params }: { params: { id: string } }) {
  redirect(`/case/${params.id}/detect`);
}
