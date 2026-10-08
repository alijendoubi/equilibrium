"use client";

import Link from "next/link";
import { Fragment, useMemo, useState } from "react";
import { mapHref } from "@/lib/graph-map";
import { ExplainPanel } from "@/components/explain/ExplainPanel";
import { NodeChip } from "@/components/NodeChip";
import type { AtlasNode, Edge, Path } from "@/lib/api/types";
import { EVIDENCE_LABEL, formatConfidence, relationLabel } from "@/lib/format";
import { EdgePanel } from "./EdgePanel";

interface ConnectorProps {
  edge: Edge;
  left: AtlasNode;
  right: AtlasNode;
  selected: boolean;
  onSelect: () => void;
}

/** The link between two chips. Solid for observed or curated data, dashed and labelled for hypotheses. */
function Connector({ edge, left, right, selected, onSelect }: ConnectorProps) {
  const inferred = edge.evidence_type === "inferred";
  const forward = edge.source_id === left.id;
  const [from, to] = forward ? [left, right] : [right, left];
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      data-evidence={edge.evidence_type}
      aria-label={`${from.label} ${relationLabel(edge.relation)} ${to.label}. ${EVIDENCE_LABEL[edge.evidence_type]}, confidence ${formatConfidence(edge.confidence)}. Show evidence.`}
      className={`flex min-w-24 flex-col items-center gap-1 rounded-lg px-2 py-1 text-xs ${
        selected ? "bg-background ring-1 ring-focus" : "hover:bg-background"
      }`}
    >
      <span className="text-muted">
        {forward ? "" : "← "}
        {relationLabel(edge.relation)}
        {forward ? " →" : ""}
      </span>
      <span
        aria-hidden="true"
        data-testid="edge-line"
        className={`block w-full border-t-2 ${
          inferred ? "border-dashed border-muted" : "border-solid border-foreground"
        }`}
      />
      <span className={inferred ? "font-medium text-muted italic" : "text-muted"}>
        {inferred ? "hypothesis" : EVIDENCE_LABEL[edge.evidence_type].toLowerCase()} ·{" "}
        {formatConfidence(edge.confidence)}
      </span>
    </button>
  );
}

/** The map centred on the path's start, with every hop expanded and the route highlighted. */
export function pathMapHref(path: Path): string {
  const [first, ...rest] = path.nodes;
  return mapHref({
    center: first?.id ?? null,
    expand: rest.map((n) => n.id),
    highlight: path.edges.map((e) => e.id),
  });
}

export function PathExplorer({ paths }: { paths: Path[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(paths[0]?.edges[0]?.id ?? null);

  const nodesById = useMemo(
    () => new Map(paths.flatMap((p) => p.nodes).map((n) => [n.id, n])),
    [paths],
  );
  const selected = paths.flatMap((p) => p.edges).find((e) => e.id === selectedId) ?? null;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-6">
        {paths.map((path, index) => (
          <section
            key={path.edges.map((e) => e.id).join("-")}
            aria-label={`Route ${index + 1}`}
            className="rounded-2xl border border-border bg-surface p-5"
          >
            <h2 className="text-sm font-medium text-muted">
              Route {index + 1}
              {index === 0 && paths.length > 1 ? " (strongest)" : ""} · {path.edges.length}{" "}
              {path.edges.length === 1 ? "link" : "links"}
              {path.has_inferred ? " · includes a hypothesis" : " · all links are data"}
              {path.has_contradiction ? " · includes a contradicted link" : ""}
            </h2>
            <ol className="mt-4 flex flex-wrap items-center gap-2">
              {path.nodes.map((node, i) => {
                const edge = path.edges[i];
                const next = path.nodes[i + 1];
                return (
                  <Fragment key={`${node.id}-${i}`}>
                    <li>
                      <NodeChip node={node} />
                    </li>
                    {edge && next && (
                      <li>
                        <Connector
                          edge={edge}
                          left={node}
                          right={next}
                          selected={edge.id === selectedId}
                          onSelect={() => setSelectedId(edge.id)}
                        />
                      </li>
                    )}
                  </Fragment>
                );
              })}
            </ol>
            <p className="mt-4 text-sm">
              <Link
                href={pathMapHref(path)}
                className="font-medium text-cluster underline-offset-4 hover:underline"
              >
                Show this path on the map <span aria-hidden="true">→</span>
              </Link>
            </p>
            <div className="mt-4">
              <ExplainPanel
                edgeIds={path.edges.map((e) => e.id)}
                edges={path.edges}
                nodes={path.nodes}
                triggerLabel="Explain this path"
                title={`Route ${index + 1} in plain language`}
              />
            </div>
          </section>
        ))}
        <p className="text-xs text-muted">
          Solid line: data (observed or curated). Dashed line: hypothesis (inferred by our
          pipeline).
        </p>
      </div>
      <div className="lg:sticky lg:top-6 lg:self-start">
        <EdgePanel edge={selected} nodesById={nodesById} />
      </div>
    </div>
  );
}
