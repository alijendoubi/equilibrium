"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { EdgePanel } from "@/components/path/EdgePanel";
import type { EvidenceType, GraphMapResponse, NodeType } from "@/lib/api/types";
import { EVIDENCE_LABEL, NODE_TYPE_LABEL } from "@/lib/format";
import { ALL_NODE_TYPES, mapHref, type MapParams } from "@/lib/graph-map";
import { computeLayout } from "@/lib/map-layout";
import { MapCanvas } from "./MapCanvas";
import { MapLegend } from "./MapLegend";
import { MapNodePanel } from "./MapNodePanel";
import { MapTable } from "./MapTable";
import { NODE_TYPE_PLURAL } from "./map-style";

const EVIDENCE_ORDER: EvidenceType[] = ["curated", "observed", "inferred"];
const CHIP =
  "inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-focus";

export interface EvidenceMapProps {
  graph: GraphMapResponse;
  /** The /map URL state, used to build "Center here", "Expand" and "Show symptoms" links. */
  state?: MapParams;
  /** Embedded variant (disease page): smaller, no filter bar. */
  compact?: boolean;
}

/** Force-directed, explainable evidence map with filters, a legend, panels and a table view. */
export function EvidenceMap({ graph, state = {}, compact = false }: EvidenceMapProps) {
  const presentTypes = useMemo(
    () => ALL_NODE_TYPES.filter((t) => graph.nodes.some((n) => n.node.type === t)),
    [graph.nodes],
  );
  const [shownTypes, setShownTypes] = useState<ReadonlySet<NodeType>>(new Set(presentTypes));
  const [shownEvidence, setShownEvidence] = useState<ReadonlySet<EvidenceType>>(
    new Set(EVIDENCE_ORDER),
  );
  const [minConfidence, setMinConfidence] = useState(0);
  const [view, setView] = useState<"map" | "table">("map");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  const center = graph.center;
  const contradictionIds = useMemo(
    () => new Set(graph.contradiction_edge_ids),
    [graph.contradiction_edge_ids],
  );
  const highlight = useMemo(() => new Set(state.highlight ?? []), [state.highlight]);
  const nodesById = useMemo(
    () => new Map(graph.nodes.map((n) => [n.node.id, n.node])),
    [graph.nodes],
  );
  const labelOf = (id: string) => nodesById.get(id)?.label ?? id;

  const nodes = useMemo(
    () => graph.nodes.filter((n) => n.node.id === center || shownTypes.has(n.node.type)),
    [graph.nodes, center, shownTypes],
  );
  const nodeIds = useMemo(() => new Set(nodes.map((n) => n.node.id)), [nodes]);
  const structural = useMemo(
    () => graph.edges.filter((e) => nodeIds.has(e.source_id) && nodeIds.has(e.target_id)),
    [graph.edges, nodeIds],
  );
  const edges = useMemo(
    () =>
      structural.filter(
        (e) => shownEvidence.has(e.evidence_type) && e.confidence >= minConfidence - 1e-9,
      ),
    [structural, shownEvidence, minConfidence],
  );
  // The layout depends only on which nodes are shown, so evidence filters never move nodes.
  const layout = useMemo(
    () => computeLayout(nodes, structural, center),
    [nodes, structural, center],
  );

  const selectedNode = graph.nodes.find((n) => n.node.id === selectedNodeId) ?? null;
  const selectedEdge = graph.edges.find((e) => e.id === selectedEdgeId) ?? null;
  const selectNode = (id: string) => {
    setSelectedNodeId(id);
    setSelectedEdgeId(null);
  };

  const toggle = <T,>(set: ReadonlySet<T>, value: T): ReadonlySet<T> => {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  };

  const hidden = Object.entries(graph.truncated.by_type).filter(([, count]) => count > 0);
  const phenotypesShown = Boolean(state.phenotypes);
  const typeLegend = compact ? presentTypes : ALL_NODE_TYPES.filter((t) => t !== "variant");

  const panel = selectedEdge ? (
    <div className="space-y-2">
      {selectedNode && (
        <button
          type="button"
          onClick={() => setSelectedEdgeId(null)}
          className="text-xs text-muted underline-offset-4 hover:underline"
        >
          <span aria-hidden="true">←</span> Back to {selectedNode.node.label}
        </button>
      )}
      <EdgePanel edge={selectedEdge} nodesById={nodesById} />
    </div>
  ) : selectedNode ? (
    <MapNodePanel
      item={selectedNode}
      edges={edges}
      labelOf={labelOf}
      contradictionIds={contradictionIds}
      state={{ ...state, center }}
      onSelectEdge={setSelectedEdgeId}
      onClose={() => setSelectedNodeId(null)}
    />
  ) : (
    <aside
      aria-label="Map help"
      className="rounded-2xl border border-dashed border-border p-5 text-sm text-muted"
    >
      <p className="font-medium text-foreground">Select a node or a line.</p>
      <p className="mt-1">
        A node opens its summary and actions; a line opens its evidence: source, record, date,
        confidence and why. Drag to pan, scroll or use + and − to zoom, Tab and Enter to move by
        keyboard.
      </p>
    </aside>
  );

  return (
    <div className="space-y-4" data-testid="evidence-map">
      <div className="flex flex-wrap items-center gap-2">
        <div
          role="group"
          aria-label="View"
          className="inline-flex rounded-xl border border-border p-0.5"
        >
          {(["map", "table"] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className={`rounded-lg px-3 py-1 text-xs font-medium ${view === v ? "bg-foreground text-background" : "text-muted hover:text-foreground"}`}
            >
              {v === "map" ? "Map view" : "Table view"}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted" aria-live="polite">
          {nodes.length} nodes · {edges.length} links shown
        </p>
        {hidden.length > 0 && (
          <ul aria-label="Not drawn" className="flex flex-wrap gap-1.5">
            {hidden.map(([type, count]) => {
              const label = `+${count} ${NODE_TYPE_PLURAL[type as NodeType] ?? type}`;
              const canShow = type === "phenotype" && center && !phenotypesShown;
              return (
                <li key={type}>
                  {canShow ? (
                    <Link
                      href={mapHref({ ...state, center, phenotypes: true })}
                      className="inline-flex rounded-full border border-dashed border-cluster px-2.5 py-0.5 text-xs font-medium text-cluster hover:bg-surface"
                      title="Load the symptoms of the centred node"
                    >
                      {label}
                    </Link>
                  ) : (
                    <span
                      className="inline-flex rounded-full border border-dashed border-border px-2.5 py-0.5 text-xs text-muted"
                      title="Not drawn to keep the map readable; open a node page to see them all"
                    >
                      {label}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {!compact && (
        <div className="flex flex-wrap items-start gap-x-6 gap-y-3 rounded-2xl border border-border bg-surface p-4">
          <fieldset className="min-w-0">
            <legend className="text-[0.7rem] font-semibold tracking-wider text-muted uppercase">
              Node types
            </legend>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {presentTypes.map((type) => {
                const on = shownTypes.has(type);
                return (
                  <label
                    key={type}
                    className={`${CHIP} ${on ? "border-foreground/40 bg-background" : "border-border text-muted line-through"}`}
                  >
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={on}
                      onChange={() => setShownTypes((s) => toggle(s, type))}
                    />
                    {NODE_TYPE_LABEL[type]}
                    <span className="text-muted">{graph.legend.node_types[type] ?? 0}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>
          <fieldset>
            <legend className="text-[0.7rem] font-semibold tracking-wider text-muted uppercase">
              Evidence
            </legend>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {EVIDENCE_ORDER.map((type) => {
                const on = shownEvidence.has(type);
                return (
                  <label
                    key={type}
                    className={`${CHIP} ${on ? "border-foreground/40 bg-background" : "border-border text-muted line-through"}`}
                  >
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={on}
                      onChange={() => setShownEvidence((s) => toggle(s, type))}
                    />
                    {EVIDENCE_LABEL[type]}
                    <span className="text-muted">{graph.legend.evidence_types[type] ?? 0}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>
          <div>
            <label
              htmlFor="map-min-confidence"
              className="text-[0.7rem] font-semibold tracking-wider text-muted uppercase"
            >
              Min confidence {minConfidence.toFixed(2)}
            </label>
            <input
              id="map-min-confidence"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              className="mt-2 block w-40 accent-cluster"
            />
          </div>
          {center && (
            <div className="self-end">
              <Link
                href={mapHref({ ...state, center, phenotypes: !phenotypesShown })}
                className="inline-flex rounded-full border border-border px-3 py-1 text-xs font-medium hover:bg-background"
              >
                {phenotypesShown ? "Hide symptoms" : "Show symptoms"}
              </Link>
            </div>
          )}
        </div>
      )}

      <div className={compact ? "space-y-4" : "grid gap-4 lg:grid-cols-[minmax(0,1fr)_21rem]"}>
        <div className="min-w-0">
          {view === "map" ? (
            <div className="overflow-hidden rounded-2xl border border-border bg-surface">
              <MapCanvas
                key={nodes.map((n) => n.node.id).join("|")}
                nodes={nodes}
                edges={edges}
                center={center}
                layout={layout}
                contradictionIds={contradictionIds}
                highlight={highlight}
                selectedNodeId={selectedNodeId}
                selectedEdgeId={selectedEdgeId}
                onSelectNode={selectNode}
                onSelectEdge={setSelectedEdgeId}
                compact={compact}
              />
            </div>
          ) : (
            <MapTable
              nodes={nodes}
              edges={edges}
              labelOf={labelOf}
              contradictionIds={contradictionIds}
              onSelectNode={selectNode}
              onSelectEdge={setSelectedEdgeId}
            />
          )}
        </div>
        <div
          className={
            compact ? "grid gap-4 sm:grid-cols-2" : "space-y-4 lg:sticky lg:top-6 lg:self-start"
          }
        >
          {panel}
          <MapLegend types={typeLegend} showHighlight={highlight.size > 0} compact={compact} />
        </div>
      </div>
    </div>
  );
}
