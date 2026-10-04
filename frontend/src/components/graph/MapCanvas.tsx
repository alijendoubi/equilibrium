"use client";

import { useEffect, useId, useMemo, useRef, useState, type PointerEvent } from "react";
import type { Edge, MapNode } from "@/lib/api/types";
import { EVIDENCE_LABEL, NODE_TYPE_LABEL, formatConfidence, relationLabel } from "@/lib/format";
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

const MIN_ZOOM = 0.4;
const MAX_ZOOM = 4;
const ZOOM_STEP = 1.3;
const DRAG_THRESHOLD = 3;
/** Above this many nodes only the bigger, selected or hovered nodes carry a label. */
const LABEL_ALL_LIMIT = 90;

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

function svgPoint(svg: SVGSVGElement | null, clientX: number, clientY: number): Point | null {
  const ctm = svg?.getScreenCTM?.();
  if (!ctm) return null;
  const p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
  return { x: p.x, y: p.y };
}

const clampZoom = (k: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, k));

/** The SVG drawing: zoom (wheel or buttons), pan (drag the background), drag nodes, hover tips. */
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

  const [vx, vy, vw, vh] = layout.viewBox;
  const pos = (id: string): Point => moved.get(id) ?? layout.positions.get(id) ?? { x: 0, y: 0 };
  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.node.id, n])), [nodes]);
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

  // Wheel zoom around the pointer (full map only; the compact map keeps page scrolling).
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || compact) return;
    const onWheel = (event: WheelEvent) => {
      const p = svgPoint(svg, event.clientX, event.clientY);
      if (!p) return;
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
      setTransform((t) => {
        const k = clampZoom(t.k * factor);
        return { k, x: p.x - ((p.x - t.x) * k) / t.k, y: p.y - ((p.y - t.y) * k) / t.k };
      });
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, [compact]);

  const zoomBy = (factor: number) =>
    setTransform((t) => {
      const cx = vx + vw / 2;
      const cy = vy + vh / 2;
      const k = clampZoom(t.k * factor);
      return { k, x: cx - ((cx - t.x) * k) / t.k, y: cy - ((cy - t.y) * k) / t.k };
    });
  const reset = () => {
    setTransform({ k: 1, x: 0, y: 0 });
    setMoved(new Map());
  };

  const startGesture = (event: PointerEvent, kind: "pan" | "node", id?: string) => {
    const p = svgPoint(svgRef.current, event.clientX, event.clientY);
    if (!p || event.button !== 0) return;
    gesture.current = { kind, id, start: p, origin: transform, dragged: false };
    svgRef.current?.setPointerCapture?.(event.pointerId);
  };
  const onPointerMove = (event: PointerEvent) => {
    const g = gesture.current;
    if (!g) return;
    const p = svgPoint(svgRef.current, event.clientX, event.clientY);
    if (!p) return;
    const dx = p.x - g.start.x;
    const dy = p.y - g.start.y;
    if (!g.dragged && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    g.dragged = true;
    if (g.kind === "pan") {
      setTransform({ ...g.origin, x: g.origin.x + dx, y: g.origin.y + dy });
    } else if (g.id) {
      const world = { x: (p.x - transform.x) / transform.k, y: (p.y - transform.y) / transform.k };
      const id = g.id;
      setMoved((m) => new Map(m).set(id, world));
      setHover(null);
    }
  };
  const endGesture = () => {
    suppressClick.current = Boolean(gesture.current?.dragged);
    gesture.current = null;
  };

  const showTip = (event: PointerEvent, kind: Hover["kind"], id: string) => {
    if (gesture.current?.dragged) return;
    const box = wrapRef.current?.getBoundingClientRect();
    setHover({
      kind,
      id,
      left: event.clientX - (box?.left ?? 0) + 14,
      top: event.clientY - (box?.top ?? 0) + 14,
    });
  };

  const labelled = (n: MapNode) =>
    nodes.length <= LABEL_ALL_LIMIT ||
    n.degree >= 3 ||
    n.node.id === center ||
    n.node.id === focusId ||
    Boolean(neighbours?.has(n.node.id)) ||
    highlightNodes.has(n.node.id);

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
    <div ref={wrapRef} className="evidence-map relative">
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
        viewBox={`${vx} ${vy} ${vw} ${vh}`}
        preserveAspectRatio="xMidYMid meet"
        className={`block w-full touch-none select-none ${compact ? "h-[380px]" : "h-[min(72vh,680px)] min-h-[420px]"}`}
        onPointerMove={onPointerMove}
        onPointerUp={endGesture}
        onPointerCancel={endGesture}
        onKeyDown={(event) => {
          if (event.key === "Escape") setHover(null);
        }}
      >
        <defs>
          {(["data", "contradiction", "highlight"] as const).map((kind) => (
            <marker
              key={kind}
              id={`arrow-${kind}-${uid}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="9"
              markerHeight="9"
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
          x={vx}
          y={vy}
          width={vw}
          height={vh}
          fill="transparent"
          className="cursor-grab active:cursor-grabbing"
          onPointerDown={(e) => startGesture(e, "pan")}
          onClick={() => setHover(null)}
        />
        <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.k})`}>
          <g aria-hidden="true">
            {edges.map((edge) => {
              const s = pos(edge.source_id);
              const t = pos(edge.target_id);
              const len = Math.hypot(t.x - s.x, t.y - s.y) || 1;
              const trim = radius(edge.target_id) + 4;
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
              const marker = lit
                ? "highlight"
                : style === "contradiction"
                  ? "contradiction"
                  : "data";
              return (
                <g
                  key={edge.id}
                  data-edge-id={edge.id}
                  data-style={style}
                  className="cursor-pointer"
                  opacity={dimEdge(edge) ? 0.15 : style === "data" && !lit && !selected ? 0.6 : 1}
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
                    strokeWidth={
                      edgeWidth(edge.confidence) + (lit ? 2.5 : 0) + (selected ? 1.5 : 0)
                    }
                    strokeDasharray={style === "hypothesis" ? DASH : undefined}
                    strokeLinecap="round"
                    markerEnd={`url(#arrow-${marker}-${uid})`}
                  />
                  {style === "contradiction" && (
                    <g transform={`translate(${(s.x + ex) / 2} ${(s.y + ey) / 2})`}>
                      <rect
                        x={-32}
                        y={-9}
                        width={64}
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
                  )}
                </g>
              );
            })}
          </g>
          <g>
            {nodes.map((n) => {
              const { node } = n;
              const p = pos(node.id);
              const r = radius(node.id);
              const isCenter = node.id === center;
              const selected = node.id === selectedNodeId;
              const lit = highlightNodes.has(node.id);
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
                  opacity={dimNode(node.id) ? 0.25 : 1}
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
                      r={r + 6}
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
                  {labelled(n) && (
                    <text
                      className="node-label"
                      y={r + 13}
                      textAnchor="middle"
                      fontSize={isCenter ? 13 : 11}
                      fontWeight={isCenter || selected ? 600 : 500}
                    >
                      {truncateLabel(node.label)}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
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
