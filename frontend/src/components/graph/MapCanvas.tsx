"use client";

import { useEffect, useId, useMemo, useRef, useState, type PointerEvent } from "react";
import type { Edge, MapNode } from "@/lib/api/types";
import { EVIDENCE_LABEL, NODE_TYPE_LABEL, formatConfidence, relationLabel } from "@/lib/format";
import { type Box, LABEL_FONT_PX, placeLabels } from "@/lib/map-labels";
import { nodeRadius, type MapLayout, type Point } from "@/lib/map-layout";
import {
  DASH,
  contradictionBadge,
  edgeStyle,
  edgeWidth,
  nodeColor,
  shapePath,
  truncateLabel,
} from "./map-style";

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 5;
const ZOOM_STEP = 1.35;
const DRAG_THRESHOLD = 3;
/** Small maps are spread out, but never more than this many pixels per layout unit. */
const MAX_FIT_SCALE = 1.6;
/** One axis may be stretched up to this much more than the other to use the whole canvas. */
const MAX_STRETCH = 1.5;
/** Room around the drawing for labels and the zoom buttons, in pixels. */
const PAD = { x: 90, top: 44, bottom: 36 };

interface Transform {
  k: number;
  x: number;
  y: number;
}

interface Hover {
  kind: "node" | "edge";
  id: string;
  left: number;
  top: number;
}

export interface MapCanvasProps {
  nodes: MapNode[];
  edges: Edge[];
  center: string | null;
  layout: MapLayout;
  contradictionIds: ReadonlySet<string>;
  highlight: ReadonlySet<string>;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onSelectNode: (id: string) => void;
  onSelectEdge: (id: string) => void;
  compact?: boolean;
}

const clampZoom = (k: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, k));

/** Tracks the rendered size of an element (falls back to `initial` without ResizeObserver). */
function useSize(ref: React.RefObject<HTMLElement | null>, initial: { w: number; h: number }) {
  const [size, setSize] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const box = entry?.contentRect;
      if (box && box.width > 0 && box.height > 0) setSize({ w: box.width, h: box.height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return size;
}

/**
 * The SVG drawing, in screen pixels: layout positions are projected to fit the canvas, while
 * shapes, lines and labels keep a constant pixel size. Zoom (wheel or buttons) spreads nodes
 * apart so more labels fit; drag the background to pan, drag a node to move it.
 */
export function MapCanvas({
  nodes,
  edges,
  center,
  layout,
  contradictionIds,
  highlight,
  selectedNodeId,
  selectedEdgeId,
  onSelectNode,
  onSelectEdge,
  compact = false,
}: MapCanvasProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const size = useSize(wrapRef, { w: 880, h: compact ? 380 : 640 });
  const [transform, setTransform] = useState<Transform>({ k: 1, x: 0, y: 0 });
  const [moved, setMoved] = useState<ReadonlyMap<string, Point>>(new Map());
  const [hover, setHover] = useState<Hover | null>(null);
  const gesture = useRef<{
    kind: "pan" | "node";
    id?: string;
    start: Point;
    origin: Transform;
    dragged: boolean;
  } | null>(null);
  const suppressClick = useRef(false);

  const fit = useMemo(() => {
    const [x0, y0, x1, y1] = layout.bounds;
    // Each axis fills the canvas, but the stretch between them stays below MAX_STRETCH.
    const wx = Math.min((size.w - 2 * PAD.x) / Math.max(x1 - x0, 1), MAX_FIT_SCALE);
    const wy = Math.min((size.h - PAD.top - PAD.bottom) / Math.max(y1 - y0, 1), MAX_FIT_SCALE);
    const sx = Math.min(wx, wy * MAX_STRETCH);
    const sy = Math.min(wy, wx * MAX_STRETCH);
    return {
      sx,
      sy,
      ox: size.w / 2 - ((x0 + x1) / 2) * sx,
      oy: PAD.top + (size.h - PAD.top - PAD.bottom) / 2 - ((y0 + y1) / 2) * sy,
    };
  }, [layout.bounds, size]);

  const project = (p: Point): Point => ({
    x: (p.x * fit.sx + fit.ox) * transform.k + transform.x,
    y: (p.y * fit.sy + fit.oy) * transform.k + transform.y,
  });
  const unproject = (q: Point): Point => ({
    x: ((q.x - transform.x) / transform.k - fit.ox) / fit.sx,
    y: ((q.y - transform.y) / transform.k - fit.oy) / fit.sy,
  });
  const local = (clientX: number, clientY: number): Point => {
    const box = svgRef.current?.getBoundingClientRect();
    return { x: clientX - (box?.left ?? 0), y: clientY - (box?.top ?? 0) };
  };

  const screen = new Map(
    nodes.map((n) => [
      n.node.id,
      project(moved.get(n.node.id) ?? layout.positions.get(n.node.id) ?? { x: 0, y: 0 }),
    ]),
  );
  const at = (id: string) => screen.get(id) ?? { x: 0, y: 0 };
  const nodeById = new Map(nodes.map((n) => [n.node.id, n]));
  const radius = (id: string) => nodeRadius(nodeById.get(id)?.degree ?? 0, id === center);

  const focusId = hover?.kind === "node" ? hover.id : selectedNodeId;
  const neighbours = useMemo(() => {
    if (!focusId) return null;
    const set = new Set([focusId]);
    for (const e of edges) {
      if (e.source_id === focusId) set.add(e.target_id);
      if (e.target_id === focusId) set.add(e.source_id);
    }
    return set;
  }, [edges, focusId]);
  const highlightNodes = useMemo(
    () =>
      new Set(edges.filter((e) => highlight.has(e.id)).flatMap((e) => [e.source_id, e.target_id])),
    [edges, highlight],
  );
  const hasHighlight = highlightNodes.size > 0;

  const badgeBoxes: Box[] = edges
    .filter((e) => edgeStyle(e, contradictionIds) === "contradiction")
    .map((e) => {
      const a = at(e.source_id);
      const b = at(e.target_id);
      const mx = (a.x + b.x) / 2;
      const my = (a.y + b.y) / 2;
      return [mx - 35, my - 11, mx + 35, my + 11];
    });
  const labelled = placeLabels(
    nodes.map((n) => {
      const id = n.node.id;
      const p = at(id);
      return {
        id,
        text: truncateLabel(n.node.label),
        x: p.x,
        y: p.y,
        r: radius(id),
        forced: id === center || id === focusId || highlightNodes.has(id),
        priority: (neighbours?.has(id) ? 1000 : 0) + n.degree,
      };
    }),
    badgeBoxes,
    [4, 4, size.w - 4, size.h - 4],
  );

  // Wheel zoom around the pointer (full map only; the compact map keeps page scrolling).
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || compact) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const box = svg.getBoundingClientRect();
      const q = { x: event.clientX - box.left, y: event.clientY - box.top };
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      setTransform((t) => {
        const k = clampZoom(t.k * factor);
        return { k, x: q.x - ((q.x - t.x) * k) / t.k, y: q.y - ((q.y - t.y) * k) / t.k };
      });
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, [compact]);

  const zoomBy = (factor: number) =>
    setTransform((t) => {
      const q = { x: size.w / 2, y: size.h / 2 };
      const k = clampZoom(t.k * factor);
      return { k, x: q.x - ((q.x - t.x) * k) / t.k, y: q.y - ((q.y - t.y) * k) / t.k };
    });
  const reset = () => {
    setTransform({ k: 1, x: 0, y: 0 });
    setMoved(new Map());
  };

  const startGesture = (event: PointerEvent, kind: "pan" | "node", id?: string) => {
    if (event.button !== 0) return;
    suppressClick.current = false;
    const start = local(event.clientX, event.clientY);
    gesture.current = { kind, id, start, origin: transform, dragged: false };
  };
  const onPointerMove = (event: PointerEvent) => {
    const g = gesture.current;
    if (!g) return;
    const q = local(event.clientX, event.clientY);
    const dx = q.x - g.start.x;
    const dy = q.y - g.start.y;
    if (!g.dragged && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    if (!g.dragged) svgRef.current?.setPointerCapture?.(event.pointerId);
    g.dragged = true;
    setHover(null);
    if (g.kind === "pan") {
      setTransform({ ...g.origin, x: g.origin.x + dx, y: g.origin.y + dy });
    } else if (g.id) {
      const id = g.id;
      const world = unproject(q);
      setMoved((m) => new Map(m).set(id, world));
    }
  };
  const endGesture = () => {
    suppressClick.current = Boolean(gesture.current?.dragged);
    gesture.current = null;
  };

  const showTip = (event: PointerEvent, kind: Hover["kind"], id: string) => {
    if (gesture.current?.dragged) return;
    const box = wrapRef.current?.getBoundingClientRect();
    const left = event.clientX - (box?.left ?? 0) + 14;
    setHover({
      kind,
      id,
      left: Math.min(left, Math.max(size.w - 300, 0)),
      top: event.clientY - (box?.top ?? 0) + 14,
    });
  };

  const dimNode = (id: string) =>
    (neighbours !== null && !neighbours.has(id)) ||
    (hasHighlight && neighbours === null && !highlightNodes.has(id));
  const dimEdge = (e: Edge) =>
    (neighbours !== null && !(e.source_id === focusId || e.target_id === focusId)) ||
    (hasHighlight && neighbours === null && !highlight.has(e.id));

  const tipNode = hover?.kind === "node" ? nodeById.get(hover.id) : undefined;
  const tipEdge = hover?.kind === "edge" ? edges.find((e) => e.id === hover.id) : undefined;
  const label = (id: string) => nodeById.get(id)?.node.label ?? id;

  return (
    <div
      ref={wrapRef}
      className={`evidence-map relative ${compact ? "h-[380px]" : "h-[min(82vh,860px)] min-h-[480px]"}`}
    >
      <div className="absolute top-3 right-3 z-10 flex gap-1" role="group" aria-label="Zoom">
        {[
          { text: "+", name: "Zoom in", act: () => zoomBy(ZOOM_STEP) },
          { text: "−", name: "Zoom out", act: () => zoomBy(1 / ZOOM_STEP) },
          { text: "Reset", name: "Reset view", act: reset },
        ].map((b) => (
          <button
            key={b.name}
            type="button"
            onClick={b.act}
            aria-label={b.name}
            className="min-w-8 rounded-lg border border-border bg-surface/90 px-2 py-1 text-xs font-medium shadow-sm backdrop-blur hover:bg-background"
          >
            {b.text}
          </button>
        ))}
      </div>
      <svg
        ref={svgRef}
        role="group"
        aria-label={`Evidence map: ${nodes.length} nodes and ${edges.length} links. Use Tab to move between nodes and Enter to open one.`}
        viewBox={`0 0 ${size.w} ${size.h}`}
        className="block h-full w-full touch-none select-none"
        onPointerMove={onPointerMove}
        onPointerUp={endGesture}
        onPointerCancel={endGesture}
      >
        <defs>
          {(["data", "contradiction", "highlight"] as const).map((kind) => (
            <marker
              key={kind}
              id={`arrow-${kind}-${uid}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="8"
              markerHeight="8"
              markerUnits="userSpaceOnUse"
              orient="auto"
            >
              <path
                d="M0,0 L10,5 L0,10 Z"
                style={{
                  fill:
                    kind === "contradiction"
                      ? "var(--contradiction)"
                      : kind === "highlight"
                        ? "var(--focus)"
                        : "var(--muted)",
                }}
              />
            </marker>
          ))}
        </defs>
        <rect
          width={size.w}
          height={size.h}
          fill="transparent"
          className="cursor-grab active:cursor-grabbing"
          onPointerDown={(e) => startGesture(e, "pan")}
        />
        <g aria-hidden="true">
          {edges.map((edge) => {
            const s = at(edge.source_id);
            const t = at(edge.target_id);
            const len = Math.hypot(t.x - s.x, t.y - s.y) || 1;
            const trim = radius(edge.target_id) + 3;
            const ex = t.x - ((t.x - s.x) / len) * trim;
            const ey = t.y - ((t.y - s.y) / len) * trim;
            const style = edgeStyle(edge, contradictionIds);
            const lit = highlight.has(edge.id);
            const selected = edge.id === selectedEdgeId;
            const stroke = lit
              ? "var(--focus)"
              : style === "contradiction"
                ? "var(--contradiction)"
                : selected
                  ? "var(--foreground)"
                  : "var(--muted)";
            const marker = lit ? "highlight" : style === "contradiction" ? "contradiction" : "data";
            const resting = style === "data" && !lit && !selected ? 0.55 : 1;
            return (
              <g
                key={edge.id}
                data-edge-id={edge.id}
                data-style={style}
                className="cursor-pointer"
                opacity={dimEdge(edge) ? 0.12 : resting}
                onClick={() => onSelectEdge(edge.id)}
                onPointerEnter={(e) => showTip(e, "edge", edge.id)}
                onPointerLeave={() => setHover(null)}
              >
                <line x1={s.x} y1={s.y} x2={ex} y2={ey} stroke="transparent" strokeWidth={12} />
                <line
                  className="edge-line"
                  x1={s.x}
                  y1={s.y}
                  x2={ex}
                  y2={ey}
                  style={{ stroke }}
                  strokeWidth={edgeWidth(edge.confidence) + (lit ? 2.5 : 0) + (selected ? 1.5 : 0)}
                  strokeDasharray={style === "hypothesis" ? DASH : undefined}
                  strokeLinecap="round"
                  markerEnd={`url(#arrow-${marker}-${uid})`}
                />
              </g>
            );
          })}
        </g>
        <g>
          {nodes.map((n) => {
            const { node } = n;
            const p = at(node.id);
            const r = radius(node.id);
            const isCenter = node.id === center;
            const selected = node.id === selectedNodeId;
            const lit = highlightNodes.has(node.id);
            const spot = labelled.get(node.id);
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                data-node-id={node.id}
                data-type={node.type}
                aria-label={`${NODE_TYPE_LABEL[node.type]}: ${node.label}. ${n.degree} ${n.degree === 1 ? "link" : "links"} on this map.${isCenter ? " Map center." : ""} Press Enter for details.`}
                aria-pressed={selected}
                className="map-node cursor-pointer outline-none"
                transform={`translate(${p.x} ${p.y})`}
                opacity={dimNode(node.id) ? 0.22 : 1}
                onPointerDown={(e) => {
                  e.stopPropagation();
                  startGesture(e, "node", node.id);
                }}
                onClick={() => {
                  if (suppressClick.current) {
                    suppressClick.current = false;
                    return;
                  }
                  onSelectNode(node.id);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectNode(node.id);
                  }
                }}
                onPointerEnter={(e) => showTip(e, "node", node.id)}
                onPointerLeave={() => setHover(null)}
              >
                {(isCenter || selected || lit) && (
                  <circle
                    r={r + 5}
                    fill="none"
                    style={{ stroke: lit && !selected ? "var(--focus)" : "var(--foreground)" }}
                    strokeWidth={selected ? 2.5 : 1.5}
                    strokeDasharray={isCenter && !selected ? "3 3" : undefined}
                  />
                )}
                <path
                  className="node-shape"
                  d={shapePath(node.type, r)}
                  style={{ fill: nodeColor(node.type), stroke: "var(--surface)" }}
                  strokeWidth={1.5}
                />
                {spot && (
                  <text
                    className="node-label"
                    x={spot.dx}
                    y={spot.dy}
                    textAnchor={spot.anchor}
                    fontSize={isCenter ? LABEL_FONT_PX + 1.5 : LABEL_FONT_PX}
                    fontWeight={isCenter || selected ? 650 : 500}
                  >
                    {truncateLabel(node.label)}
                  </text>
                )}
              </g>
            );
          })}
        </g>
        <g aria-hidden="true">
          {edges
            .filter((edge) => edgeStyle(edge, contradictionIds) === "contradiction")
            .map((edge) => {
              const a = at(edge.source_id);
              const b = at(edge.target_id);
              return (
                <g
                  key={`badge-${edge.id}`}
                  data-edge-badge={edge.id}
                  transform={`translate(${(a.x + b.x) / 2} ${(a.y + b.y) / 2})`}
                >
                  <rect
                    x={-33}
                    y={-9}
                    width={66}
                    height={18}
                    rx={9}
                    style={{ fill: "var(--surface)", stroke: "var(--contradiction)" }}
                    strokeWidth={1.5}
                  />
                  <text
                    textAnchor="middle"
                    dy="0.35em"
                    fontSize={10}
                    fontWeight={600}
                    style={{ fill: "var(--contradiction)" }}
                  >
                    {contradictionBadge(edge)}
                  </text>
                </g>
              );
            })}
        </g>
      </svg>
      {(tipNode || tipEdge) && hover && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-20 max-w-xs rounded-xl border border-border bg-surface px-3 py-2 text-xs shadow-lg"
          style={{ left: hover.left, top: hover.top }}
        >
          {tipNode && (
            <>
              <p className="font-semibold">{tipNode.node.label}</p>
              <p className="text-muted">
                {NODE_TYPE_LABEL[tipNode.node.type]} · {tipNode.degree} on map ·{" "}
                {tipNode.total_degree} in the atlas
              </p>
              <p className="mt-1 text-muted">Click for details and actions</p>
            </>
          )}
          {tipEdge && (
            <>
              <p className="font-semibold">
                {label(tipEdge.source_id)}{" "}
                <span className="font-normal text-muted">{relationLabel(tipEdge.relation)}</span>{" "}
                {label(tipEdge.target_id)}
              </p>
              <p className="text-muted">
                {EVIDENCE_LABEL[tipEdge.evidence_type]} · confidence{" "}
                {formatConfidence(tipEdge.confidence)} · {tipEdge.provenance.source}
              </p>
              <p className="mt-1 text-muted">Click to see the evidence</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
