// Display formatters shared across every stage card (Detect/Trace/Attribute/Scene) in
// ContextPanel.tsx and the components under components/trace/. Moved out verbatim — no
// behaviour change — so the Trace card can live in its own file without duplicating them.

export const fmt = (x: number | undefined, digits: number): string =>
  typeof x === "number" && Number.isFinite(x)
    ? x.toFixed(digits).replace("-", "−") // real minus sign
    : "—";

// Coordinates render as magnitude + hemisphere, never a signed number beside a fixed "N"/"E"
// (that printed "−79.68° E" on every US case). Bundles stay signed [lon, lat]; this is display.
export const fmtLat = (v: number | undefined, digits: number): string =>
  typeof v === "number" && Number.isFinite(v)
    ? `${Math.abs(v).toFixed(digits)}° ${v < 0 ? "S" : "N"}`
    : "—";
export const fmtLon = (v: number | undefined, digits: number): string =>
  typeof v === "number" && Number.isFinite(v)
    ? `${Math.abs(v).toFixed(digits)}° ${v < 0 ? "W" : "E"}`
    : "—";

export const fmtDay = (iso: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d
    .toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    })
    .toUpperCase();
};

// HH:MM string only
export const fmtTime = (iso: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
};
