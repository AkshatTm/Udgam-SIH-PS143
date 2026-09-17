// D46 — per-spill-group colour palette, shared by MapView.tsx and ContextPanel.tsx so the map
// and the panel always name the same group with the same swatch (web/CLAUDE.md: "an interface
// colour is a map colour... a judge should not have to learn two vocabularies").
//
// Every entry stays in the SAME amber/drift hue family as the single-group colours that already
// existed (MapView.tsx's PARTICLE_FILL/PARTICLE_LINE/ORIGIN_RING_50/90, lib/origin.ts's
// ORIGIN_RGB) — varied lightness/saturation only, the same technique MapView.tsx's
// `forwardRingColor` already uses to tell a near ring from a far one. Inventing an unrelated hue
// per group would imply a new KIND of thing on a map that already assigns meaning to colour
// (blue = vessel, amber = particle/origin, red = oil, grey = look-alike/excluded, rose = dark
// vessel, violet = infrastructure) — a second spill is still a spill, not a new category.
//
// Index 0 is BYTE-IDENTICAL to the pre-D46 single-cloud colours, so the overwhelming majority of
// cases (exactly one spill group) render pixel-for-pixel as they always have.

export interface GroupPalette {
  /** deck.gl particle fill, [r,g,b,a] 0-255. */
  fill: [number, number, number, number];
  /** deck.gl particle stroke, [r,g,b,a] 0-255. */
  line: [number, number, number, number];
  /** deck.gl 50% origin ring colour, [r,g,b,a] 0-255. */
  ring50: [number, number, number, number];
  /** deck.gl 90% origin ring colour, [r,g,b,a] 0-255. */
  ring90: [number, number, number, number];
  /** origin-cloud BitmapLayer texel colour, [r,g,b] 0-255 — see lib/origin.ts buildOriginImage. */
  originRgb: readonly [number, number, number];
}

// Starting proposal only — Urooz (palette owner, per web/CLAUDE.md) should eyeball these against
// both the light and dark basemap before the demo, same as every other colour constant here.
export const GROUP_COLORS: readonly GroupPalette[] = [
  // group 0 — identical to the pre-D46 single amber cloud.
  {
    fill: [249, 115, 22, 220],
    line: [67, 20, 7, 160],
    ring50: [180, 83, 9, 240],
    ring90: [180, 83, 9, 150],
    originRgb: [251, 176, 59],
  },
  // group 1 — a deeper burnt orange.
  {
    fill: [234, 88, 12, 220],
    line: [67, 20, 7, 160],
    ring50: [154, 52, 18, 240],
    ring90: [154, 52, 18, 150],
    originRgb: [217, 119, 6],
  },
  // group 2 — a lighter, more yellow amber.
  {
    fill: [251, 191, 36, 220],
    line: [92, 64, 6, 160],
    ring50: [180, 130, 9, 240],
    ring90: [180, 130, 9, 150],
    originRgb: [252, 211, 77],
  },
  // group 3 — a darker rust.
  {
    fill: [194, 65, 12, 220],
    line: [67, 20, 7, 160],
    ring50: [124, 45, 18, 240],
    ring90: [124, 45, 18, 150],
    originRgb: [194, 100, 40],
  },
  // group 4 — a pale peach, for the rare 5th group.
  {
    fill: [252, 165, 90, 220],
    line: [92, 64, 6, 160],
    ring50: [217, 119, 6, 240],
    ring90: [217, 119, 6, 150],
    originRgb: [252, 165, 90],
  },
];

/** Cycles rather than throws past the defined palette — an unstyled sixth group is still a
 *  rendering bug worth seeing on screen, not a crash. */
export function groupColor(index: number): GroupPalette {
  return GROUP_COLORS[index % GROUP_COLORS.length];
}
