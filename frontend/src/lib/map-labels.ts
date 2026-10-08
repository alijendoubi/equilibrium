/**
 * Greedy label placement for the evidence map: labels never overlap each other.
 *
 * Candidates are taken in order (forced ones first, then by priority). Each label tries four
 * spots (below, above, right, left of its node) and is drawn in the first free one. Labels
 * avoid other nodes and edge badges (obstacles); only forced labels (centre, selection) may not. Zooming in spreads nodes apart in
 * pixels, so more labels fit: semantic zoom for free. Everything here is in screen pixels.
 */

export const LABEL_FONT_PX = 11;
const CHAR_PX = 6.1;
const LINE_PX = 14;
const GAP_PX = 3;

export interface LabelCandidate {
  id: string;
  text: string;
  x: number;
  y: number;
  /** Node radius in pixels. */
  r: number;
  /** Center, selected, hovered and highlighted nodes always get a label. */
  forced: boolean;
  /** Higher first among the rest (e.g. degree). */
  priority: number;
}

export type LabelSpot = "below" | "above" | "right" | "left";

export interface LabelPlacement {
  spot: LabelSpot;
  /** Text anchor point (baseline) relative to the node centre. */
  dx: number;
  dy: number;
  anchor: "middle" | "start" | "end";
}

export type Box = [number, number, number, number];

const SPOTS: LabelSpot[] = ["below", "above", "right", "left"];
const overlaps = (a: Box, b: Box) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];

export function placement(c: LabelCandidate, spot: LabelSpot): LabelPlacement {
  switch (spot) {
    case "below":
      return { spot, dx: 0, dy: c.r + GAP_PX + 10, anchor: "middle" };
    case "above":
      return { spot, dx: 0, dy: -(c.r + GAP_PX + 3), anchor: "middle" };
    case "right":
      return { spot, dx: c.r + GAP_PX + 2, dy: 4, anchor: "start" };
    case "left":
      return { spot, dx: -(c.r + GAP_PX + 2), dy: 4, anchor: "end" };
  }
}

export function labelBox(c: LabelCandidate, spot: LabelSpot = "below"): Box {
  const width = c.text.length * CHAR_PX + 4;
  const p = placement(c, spot);
  const x = c.x + p.dx;
  const baseline = c.y + p.dy;
  const left = p.anchor === "middle" ? x - width / 2 : p.anchor === "start" ? x : x - width;
  return [left, baseline - LINE_PX + 3, left + width, baseline + 3];
}

/** Where each label goes; candidates without a free spot are left out. */
export function placeLabels(
  candidates: LabelCandidate[],
  obstacles: readonly Box[] = [],
  bounds?: Box,
): Map<string, LabelPlacement> {
  const inside = (b: Box) =>
    !bounds || (b[0] >= bounds[0] && b[1] >= bounds[1] && b[2] <= bounds[2] && b[3] <= bounds[3]);
  const nodeBoxes = candidates.map(
    (c) => [c.id, [c.x - c.r, c.y - c.r, c.x + c.r, c.y + c.r] as Box] as const,
  );
  const placed: Box[] = [...obstacles];
  const shown = new Map<string, LabelPlacement>();
  const order = [...candidates].sort(
    (a, b) =>
      Number(b.forced) - Number(a.forced) || b.priority - a.priority || a.id.localeCompare(b.id),
  );
  for (const c of order) {
    const mayCoverNodes = c.forced;
    const spot = SPOTS.find((s) => {
      const box = labelBox(c, s);
      if (!inside(box) || placed.some((p) => overlaps(p, box))) return false;
      return mayCoverNodes || !nodeBoxes.some(([id, n]) => id !== c.id && overlaps(n, box));
    });
    const chosen = spot ?? (c.forced ? "below" : undefined);
    if (chosen) {
      placed.push(labelBox(c, chosen));
      shown.set(c.id, placement(c, chosen));
    }
  }
  return shown;
}
